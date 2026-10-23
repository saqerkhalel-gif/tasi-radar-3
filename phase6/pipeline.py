"""Bind authenticated daily artifacts to one-way, prospective-only measurement events."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,shutil,tempfile
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from radar import session_calendar
from phase3.experiment import SectorProxy
from phase4.engines import generate as generate4
from phase5.hypotheses import generate as generate5,CORE
from phase6.ledger import Ledger,sha,derived,write_exclusive
from phase6.quality import acquire,inspect,FIELDS
from phase6.calendar import prospective_source,close_utc
from phase6.engine import project,prediction,advance
from phase6.report import make_reports

def load_snapshot(root,identity):
    root=Path(root);inputs=root/'research_inputs';p=json.loads((root/'output/latest.json').read_text())
    if p.get('schema_version')!=3 or str(p['run_id'])!=str(identity['id']) or p['source_commit']!=identity['head_sha'] or identity['conclusion']!='success' or identity['name']!='TASI Radar 3.0' or identity['head_branch']!='main':raise ValueError('INVALID_SOURCE_IDENTITY')
    if p['universe_count']!=254:raise ValueError('UNIVERSE_CHANGED')
    cfg=json.loads((inputs/'config.json').read_text());meta=json.loads((inputs/'stock_metadata.json').read_text())
    universe=pd.read_csv('data/tasi_symbols.csv',dtype={'symbol':str})
    if len(universe)!=254 or universe.symbol.duplicated().any():raise ValueError('UNIVERSE_CHANGED')
    if p['universe_sha256']!=hashlib.sha256(Path('data/tasi_symbols.csv').read_bytes()).hexdigest():raise ValueError('UNIVERSE_SNAPSHOT_MISMATCH')
    frozen=json.loads((root/'output/backtest.json').read_text());data={}
    for symbol,m in meta.items():
        d=pd.read_csv(inputs/(symbol+'.csv.gz'),index_col='Date',parse_dates=True,float_precision='round_trip');d.attrs.update(m)
        if hashlib.sha256(d.to_csv().encode()).hexdigest()!=frozen['data_hashes'][symbol]:raise ValueError('INPUT_DATA_HASH_MISMATCH:'+symbol)
        data[symbol]=d
    if str(p.get('run_attempt'))!=str(identity['run_attempt']):raise ValueError('SOURCE_ATTEMPT_MISMATCH')
    if any(len(d) and d.index[-1]>pd.Timestamp(p['expected_session']) for d in data.values()):raise ValueError('FUTURE_BAR_IN_SOURCE')
    if len(data)!=p['scanned_successfully']:raise ValueError('FETCH_DENOMINATOR_MISMATCH')
    benchmark=pd.read_csv(inputs/'benchmark.csv',index_col='Date',parse_dates=True,float_precision='round_trip');benchmark.attrs.update(json.loads((inputs/'benchmark_metadata.json').read_text()))
    start=datetime.fromisoformat(p['run_utc']);end=datetime.fromisoformat(p['completed_utc'])
    if not datetime.fromisoformat(identity['created_at'])<=start<=end<=datetime.fromisoformat(identity['updated_at']):raise ValueError('SOURCE_TIMESTAMP_MISMATCH')
    source={'run_id':str(identity['id']),'run_attempt':identity['run_attempt'],'event':identity['event'],'workflow_name':identity['name'],'conclusion':identity['conclusion'],
      'head_branch':identity['head_branch'],'head_sha':identity['head_sha'],'run_url':identity['html_url'],'run_utc':p['run_utc'],'completed_utc':p['completed_utc'],
      'expected_session':p['expected_session'],'session_close_utc':close_utc(p['expected_session']).isoformat(),'source_schema':p['schema_version']}
    return data,benchmark,cfg,p,source,universe

def strategy_versions(protocol):
    common={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('phase6/engine.py','phase6/quality.py','phase6/calendar.py','phase6/protocol.json')}
    specific={'production_radar':['radar.py','config.json'],'phase4_early_reversal':['phase4/engines.py','phase4/plan.json']}
    for strategy in protocol['strategies']:
        if strategy not in specific:specific[strategy]=['phase5/hypotheses.py','phase5/protocol.json']
    return {name:sha({'common_execution_and_quality':common,'generator':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}}) for name,paths in specific.items()}

def generators(data,benchmark,sessions,cfg,report,universe):
    p4=json.loads(Path('phase4/plan.json').read_text());p5=json.loads(Path('phase5/protocol.json').read_text());p3=json.loads(Path('phase3/plan.json').read_text())
    proxy=SectorProxy(data,universe,sessions,p3['sector_proxy'])
    _,_,_,records4=generate4(data,benchmark,sessions,p4,latest_only=True)
    _,prepared,reject5,records5,_=generate5(data,benchmark,sessions,p5,proxy,latest_only=True)
    records=[]
    for r in report['results']:
        if r['classification'] not in ('Entry','Partial Entry'):continue
        obs=r.get('observations',{});q=copy.deepcopy(r)
        q.update(strategy='production_radar',production_classification=r['classification'],classification='PRODUCTION_OBSERVATION',
                 entry_context={'market_regime':'SOURCE_PRODUCTION','sector':r.get('sector')})
        q['observations']={**obs,'price_confirmed':bool(obs.get('price_breakout20') or obs.get('reclaim_ema20_with_volume')),'volume_ratio':obs.get('volume_ratio20')}
        records.append(q)
    for r in records4:
        if r['variant']=='early_reversal':records.append({**r,'strategy':'phase4_early_reversal','observations':{**r['observations'],'volume_ratio':r['features']['volume_ratio']}})
    for r in records5:
        if r['variant'] in CORE:records.append({**r,'strategy':'phase5_'+r['variant']})
        elif r['variant']=='simple_momentum20':records.append({**r,'strategy':'equal_risk_momentum20'})
    # Store ex-ante reason context for all symbols; never reconstruct it from future bars.
    screens={}
    production={r['symbol']:r for r in report['results']}
    for symbol,d in prepared.items():
        last=d.iloc[-1];screens[symbol]={'price_date':str(d.index[-1].date()),'volume_ratio':float(last.volume_ratio) if pd.notna(last.volume_ratio) else None,
          'gain5_pct':float(last.gain5) if pd.notna(last.gain5) else None,'rs20':float(last.RS20) if pd.notna(last.RS20) else None,
          'production_classification':production.get(symbol,{}).get('classification'),'production_blockers':production.get(symbol,{}).get('entry_blockers',[]),
          'registered_hypotheses_recorded':[r['strategy'] for r in records if r['symbol']==symbol],
          'no_hypothesis_reason':'No registered price/volume/pattern/target combination confirmed at this first-seen snapshot if the list is empty.'}
    return records,screens

def revisions(ledger,thin,raw,source,now,protocol):
    all_prior=[e for e in ledger.events if e['kind']=='SESSION_RECORDED'];revisions_count=0
    for old in all_prior[-65:]:
        snapshot=ledger.read_object(old['payload']['snapshot_object']);date=old['payload']['session']
        for symbol,previous in snapshot['stocks'].items():
            before=previous.get('raw');after=raw.get('records',{}).get(symbol,{}).get('bars',{}).get(date)
            if not before or not after or sha(before)==sha(after):continue
            key='data-revision:'+sha([symbol,date,sha(before),sha(after)])
            if key in ledger.ids:continue
            ledger.append(key,'DATA_REVISION',{'symbol':symbol,'session':date,'before':before,'after':after,'original_source_run':old['payload']['source_run_id'],'observed_source_run':source['run_id']},now)
            revisions_count+=1;candidates,_=project(ledger.events,protocol)
            for cid,c in candidates.items():
                if c['symbol']==symbol and c['session']<=date and c['status'] not in ('REJECTED','NOT_EXECUTABLE','DATA_UNVERIFIABLE') and (not c.get('exit') or date<=c['exit']['session']):
                    ledger.append('revision-invalidates:'+cid+':'+key,'DATA_UNVERIFIABLE',{'prediction_id':cid,'session':source['expected_session'],'reason':'previously_sealed_raw_bar_revised','revision_event':key},now)
    return revisions_count

def missed_review(ledger,out):
    sessions=[e['payload'] for e in ledger.events if e['kind']=='SESSION_RECORDED'];events=[];pending=0
    snapshots=[ledger.read_object(x['snapshot_object']) for x in sessions]
    for i,old in enumerate(sessions):
        future=snapshots[i+1:i+21]
        if len(future)<20:pending+=1;continue
        snap=snapshots[i]
        from phase6.calendar import next_session
        cfg=json.loads(Path('config.json').read_text())
        dates=[s['session'] for s in sessions[i:i+21]]
        if any(next_session(a,cfg)!=b for a,b in zip(dates,dates[1:])):continue
        for symbol,stock in snap['stocks'].items():
            if not stock['eligibility']['signal_eligible'] or not stock.get('raw'):continue
            bars=[s['stocks'].get(symbol,{}).get('raw') for s in future]
            if any(not r or not all(r['ohlcv'].get(k) is not None for k in FIELDS) or r['ohlcv']['Volume']<=0 for r in bars):continue
            entry=stock['raw']['ohlcv']['Close'];gain=100*(max(r['ohlcv']['High'] for r in bars)/entry-1)
            if gain<8:continue
            events.append({'symbol':symbol,'prior_session':old['session'],'outcome_end':sessions[i+20]['session'],'max_observed_high_gain_pct':gain,'threshold10':gain>=10,
              'prior_first_seen_screens':snap['screens'].get(symbol),'prior_signal_eligibility':stock['eligibility'],'recorded_prior_predictions':[e['event_id'] for e in ledger.events if e['kind']=='PREDICTION_RECORDED' and e['payload']['symbol']==symbol and e['payload']['session']==old['session']],
              'observational_vendor_only':True,'guaranteed_profit':False,'future_labels_used_for_entry':False})
    derived(Path(out)/'current/missed_opportunities.json',{'events':events,'pending_20_session_windows':pending,'backfilled_predictions':0,'only_sealed_post_registration_sessions':True})
    pd.json_normalize(events).to_csv(Path(out)/'current/missed_opportunities.csv',index=False)

def _run(snapshot,identity,output='output/phase6',offline=False,raw_override=None,now=None):
    now=now or datetime.now(timezone.utc);at=now.isoformat();out=Path(output);out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads(Path('phase6/protocol.json').read_text());registration=json.loads(Path('phase6/registration.json').read_text());ledger=Ledger(out/'ledger');initial_event_count=len(ledger.events)
    data,b,cfg,p,source,universe=load_snapshot(snapshot,identity)
    eligible,sessions,current_expected=prospective_source(source,now,registration['registered_utc'],cfg)
    versions=strategy_versions(protocol);bootstrap='protocol:'+sha(protocol)
    if bootstrap in ledger.ids:
        if ledger.ids[bootstrap]['payload']['versions']!=versions:raise ValueError('EXECUTION_OR_STRATEGY_VERSION_CHANGED_REQUIRES_NEW_REGISTERED_COHORT')
    else:
        object_id=ledger.object({'protocol':protocol,'registration':registration,'versions':versions})
        ledger.append(bootstrap,'PROTOCOL_REGISTERED',{'protocol_sha':sha(protocol),'registration':registration,'versions':versions},at,[object_id])
    raw=raw_override if raw_override is not None else acquire(universe.symbol.tolist(),source['expected_session'],out/'current',b,offline)
    quality,thin=inspect(data,b,sessions,source,raw);byquality={x['symbol']:x for x in quality['symbols']}
    for symbol,row in thin.items():row['eligibility']=byquality[symbol]
    # Avoid future-prefix generation: all calculations see only the source's own completed calendar.
    source_sessions=sessions[sessions<=source['expected_session']]
    records,screens=generators(data,b,source_sessions,cfg,p,universe)
    benchmark_close=float(b.loc[source['expected_session'],'Close']) if pd.Timestamp(source['expected_session']) in b.index else None
    benchmark={'close':benchmark_close,'independently_corroborated':False,'source':'Archived production benchmark'}
    snapshot_value={'source':source,'observed_utc':at,'stocks':thin,'screens':screens,'quality':quality,'benchmark':benchmark}
    content_identity=sha({'inputs':{s:r['full_input_hash'] for s,r in thin.items()},'raw_current':{s:r.get('raw') for s,r in thin.items()},'benchmark':b.to_csv(),
      'production_signals':[{k:r[k] for k in ('symbol','classification','date','scenario') if k in r} for r in p['results']],'versions':versions})
    source_key='source:'+source['run_id'];existing=ledger.ids.get(source_key)
    if existing:
        if existing['payload']['content_identity']!=content_identity:
            ledger.append('source-revision:'+source['run_id']+':'+content_identity,'SOURCE_DATA_REVISION',{'source_run_id':source['run_id'],'original_identity':existing['payload']['content_identity'],'new_identity':content_identity,'processing_blocked':True},at)
            eligible=False
            candidates,_=project(ledger.events,protocol)
            for cid,c in candidates.items():
                if c['source_run_id']==source['run_id'] and c['status'] not in ('REJECTED','NOT_EXECUTABLE','DATA_UNVERIFIABLE'):
                    ledger.append('source-revision-invalidates:'+cid+':'+content_identity,'DATA_UNVERIFIABLE',{'prediction_id':cid,'session':source['expected_session'],'reason':'source_rerun_changed_sealed_input'},at)
        # No re-recording or state advance for an already handled source/rerun.
        snapshot_key=existing['payload']['snapshot_object']
    else:
        snapshot_key=ledger.object(snapshot_value)
        ledger.append(source_key,'SOURCE_SEALED',{'source_run_id':source['run_id'],'session':source['expected_session'],'content_identity':content_identity,'snapshot_object':snapshot_key,'prospective_clock_eligible':eligible},at,[snapshot_key])
        if eligible and 'session:'+source['expected_session'] not in ledger.ids:
            revisions(ledger,thin,raw,source,at,protocol)
            raws={s:r['raw'] for s,r in thin.items() if r.get('raw')}
            advance(ledger,source['expected_session'],raws,raw.get('references',[]),protocol,cfg,at)
            accepted=0
            for rank,record in enumerate(sorted(records,key=lambda r:(r['strategy'],-float(r.get('technical_score',0)),r['symbol']))):
                symbol=record['symbol'];record=copy.deepcopy(record);record['rank']=rank
                record['source_last_bar']=thin[symbol]['raw'];record['source_input_hash']=thin[symbol]['full_input_hash']
                prefix=data[symbol].loc[:source['expected_session']].tail(200)
                vintage=ledger.object({'symbol':symbol,'session':source['expected_session'],'basis':'adjusted values actually available at observation, not a historical PIT claim','csv':prefix.to_csv()})
                record['object_refs']=[snapshot_key,vintage]
                key='prediction:'+sha([source['expected_session'],record['strategy'],versions[record['strategy']],symbol])
                accepted+=prediction(ledger,key,record,source,byquality[symbol],versions[record['strategy']],at,cfg,protocol)
            payload={'session':source['expected_session'],'source_run_id':source['run_id'],'source_run_attempt':source['run_attempt'],'snapshot_object':snapshot_key,'eligible_signal_count':accepted,'all_predictions_including_rejections':len(records),
              'no_eligible_signal_day':accepted==0,'eligibility_counts':quality['denominators'],'benchmark':benchmark,'source_event':source['event']}
            ledger.append('session:'+source['expected_session'],'SESSION_RECORDED',payload,at,[snapshot_key])
        else:
            ledger.append('audit-only:'+source['run_id'],'SOURCE_AUDIT_ONLY',{'source_run_id':source['run_id'],'session':source['expected_session'],'snapshot_object':snapshot_key,'eligible_for_prospective':False,
              'reason':'Manual/old/pre-registration/late/non-current session or session already sealed; no retrospective predictions','existing_generated_hypotheses':len(records)},at,[snapshot_key])
    if not existing:ledger.append('source-complete:'+source['run_id'],'SOURCE_COMPLETE',{'source_run_id':source['run_id'],'snapshot_object':snapshot_key},at,[snapshot_key])
    info={'run_id':os.getenv('GITHUB_RUN_ID','local'),'run_attempt':os.getenv('GITHUB_RUN_ATTEMPT','1'),'run_url':None,'source_run_id':source['run_id'],'source_run_url':source['run_url'],'source_session':source['expected_session'],'source_commit':os.getenv('GITHUB_SHA'),'observed_utc':at,'new_prediction_ids':[e['event_id'] for e in ledger.events[initial_event_count:] if e['kind']=='PREDICTION_RECORDED']}
    if info['run_id']!='local':info['run_url']='https://github.com/saqerkhalel-gif/tasi-radar-3/actions/runs/'+info['run_id']
    result=make_reports(ledger,quality,protocol,out,info);missed_review(ledger,out)
    checkpoint=ledger.manifest();write_exclusive(out/'ledger/checkpoints'/('source_'+source['run_id']+'.json'),checkpoint) if not (out/'ledger/checkpoints'/('source_'+source['run_id']+'.json')).exists() else None
    derived(out/'current/manifest.json',{'ledger':ledger.manifest(),'source_snapshot':snapshot_key,'run':info,'original_predictions_append_only':True})
    print(json.dumps({'run_id':info['run_id'],'prospective_sessions':result['prospective_session_count'],'audit_only':result['audit_only_snapshots'],'event_count':result['ledger']['event_count'],'data':quality['denominators'],'adopted':False}))
    return result

def run(snapshot,identity,output='output/phase6',offline=False,raw_override=None,now=None):
    # Runner-local transaction staging: a failed batch never replaces the accepted durable ledger.
    target=Path(output)
    with tempfile.TemporaryDirectory() as temp:
        staged=Path(temp)/'phase6'
        if target.exists():shutil.copytree(target,staged)
        result=_run(snapshot,identity,staged,offline,raw_override,now)
        checked=Ledger(staged/'ledger')
        for event in checked.events:
            if event['kind']=='SOURCE_SEALED' and 'source-complete:'+event['payload']['source_run_id'] not in checked.ids:raise ValueError('INCOMPLETE_SOURCE_TRANSACTION')
        for path in sorted(staged.rglob('*')):
            if not path.is_file() or path.name.startswith('.'):continue
            rel=path.relative_to(staged);destination=target/rel
            if rel.parts[0] in ('ledger','history') and path.suffix=='.json':write_exclusive(destination,json.loads(path.read_text()))
            else:
                destination.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as stream:stream.write(path.read_bytes());temporary=stream.name
                os.replace(temporary,destination)
        return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',required=True);parser.add_argument('--source-info',required=True);parser.add_argument('--output',default='output/phase6');parser.add_argument('--offline',action='store_true');args=parser.parse_args()
    try:run(args.snapshot,json.loads(Path(args.source_info).read_text()),args.output,args.offline)
    except Exception as exc:
        error={'run_id':os.getenv('GITHUB_RUN_ID','local'),'error_type':type(exc).__name__,'reason':str(exc)[:500],'stock_opportunity':False,'external_notifications_sent':0}
        derived(Path(args.output)/'current/OPERATIONAL_FAILURE.json',error)
        raise
