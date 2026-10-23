"""Actual post-registration observations; no orders, no production Entry."""
import argparse,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from radar import session_calendar
from phase3.experiment import SectorProxy
from phase3.quality_recheck import valid_daily_row
from phase4.shadow import advance
from phase4.research import dump
from phase5.hypotheses import generate,CORE
from phase5.missed import review

def load_daily(root):
    root=Path(root);inputs=root/'research_inputs';p=json.loads((root/'output/latest.json').read_text())
    assert str(p['run_id'])==os.getenv('SOURCE_RUN_ID',str(p['run_id'])) and p['universe_count']==254
    cfg=json.loads((inputs/'config.json').read_text());meta=json.loads((inputs/'stock_metadata.json').read_text());assert len(meta)==254
    data={}
    for s,m in meta.items():
        d=pd.read_csv(inputs/(s+'.csv.gz'),index_col='Date',parse_dates=True,float_precision='round_trip');d.attrs.update(m);data[s]=d
    b=pd.read_csv(inputs/'benchmark.csv',index_col='Date',parse_dates=True,float_precision='round_trip');b.attrs.update(json.loads((inputs/'benchmark_metadata.json').read_text()))
    return data,b,cfg,p

def update(snapshot,output,now=None):
    data,b,cfg,p=load_daily(snapshot);now=now or datetime.now(timezone.utc);sessions,_=session_calendar(now,cfg)
    plan=json.loads(Path('phase5/protocol.json').read_text());p3=json.loads(Path('phase3/plan.json').read_text())
    universe=pd.read_csv('data/tasi_symbols.csv',dtype={'symbol':str});proxy=SectorProxy(data,universe,sessions,p3['sector_proxy'])
    signals,prepared,rejected,observations,_=generate(data,b,sessions,plan,proxy,latest_only=True)
    out=Path(output);ledgerfile=out/'ledger.json';ledger=json.loads(ledgerfile.read_text()) if ledgerfile.exists() else {'schema_version':1,'observations':[]}
    for item in ledger['observations']:
        d=data[item['symbol']].copy();invalid=[str(date.date()) for date,row in d.iterrows() if not valid_daily_row(row)[0]]
        d.attrs['quarantine']=sorted(set(d.attrs.get('quarantine',[]))|set(invalid));advance(item,d,sessions)
    known={r['id'] for r in ledger['observations']};changes=[]
    benchmark_ok=p.get('benchmark_quality',{}).get('entry_eligible',False) and b.attrs.get('historical_integrity_ok',False)
    for r in observations:
        if r['variant'] not in CORE:continue
        key=r['variant']+':'+r['symbol']+':'+r['date']
        if key in known:continue
        prospective=(r['date']>='2026-10-23' and r['date']==p['expected_session']==str(sessions[-1].date()) and benchmark_ok)
        active=any(x['engine']==r['engine'] and x['symbol']==r['symbol'] and x['status'] in ('pending','open') for x in ledger['observations'])
        status='pending' if prospective and not active else ('observed_while_active' if active else 'historical_seed')
        # Non-executable repeated observations never become parallel paper trades.
        item={'id':key,'engine':r['engine'],'symbol':r['symbol'],'signal_date':r['date'],'recorded_utc':now.isoformat(),
          'source_run_id':p['run_id'],'source_run_url':p['run_url'],'source_price_date':p['expected_session'],'scenario':r['scenario'],
          'hypothesis':r['hypothesis'],'features':r['features'],'entry_context':r['entry_context'],'status':status,
          'eligible_prospective':prospective and not active,'live_order_authorized':False,
          'source_last_bar':{k:float(data[r['symbol']].loc[r['date'],k]) for k in ('Open','High','Low','Close','Volume')},
          'source_history_sha256':hashlib.sha256(data[r['symbol']].to_csv().encode()).hexdigest(),'independent_history_validated':False}
        ledger['observations'].append(item)
        if status=='pending':changes.append({'id':key,'event':'newly_confirmed_shadow_hypothesis','production_actionable':False,'delivery':'file_only_no_external_channel'})
    # advance() recognizes historical_seed, not observed_while_active: normalize the latter to expired immediately.
    for item in ledger['observations']:
        if item['status']=='observed_while_active':item.update(status='expired',reason='duplicate_active_hypothesis_no_parallel_paper_trade')
    ledger.update(updated_utc=now.isoformat(),source_run_id=p['run_id'],source_price_date=p['expected_session'],live_strategy_changed=False,
      outcome_method='Individual unit-notional hypothetical trades only; not an investable portfolio; no promotion evidence without independent provenance.')
    closed=[x for x in ledger['observations'] if x['eligible_prospective'] and x['status']=='closed' and not x.get('outcome_data_quality_blocked')]
    summary={'run_id':os.getenv('GITHUB_RUN_ID','local'),'source_run_id':p['run_id'],'source_price_date':p['expected_session'],'updated_utc':now.isoformat(),
      'prospective_closed_trades':len(closed),'adopted':False,'independent_evidence_sufficient':False,'new_shadow_changes':len(changes),'signals_not_production_entries':True,
      'per_engine':{e:{'completed':sum(x['engine']==e for x in closed),'wins':sum(x['engine']==e and x['net_return_pct']>0 for x in closed)} for e in CORE}}
    dump(ledgerfile,ledger);dump(out/'latest.json',summary);dump(out/'changes.json',{'events':changes,'external_notifications_sent':0})
    recorded=signals.copy()
    for item in ledger['observations']:
        recorded.setdefault(item['engine'],{}).setdefault(pd.Timestamp(item['signal_date']),[]).append((item['symbol'],{'date':item['signal_date']}))
    review(data,prepared,sessions,recorded,out,start=str(sessions[max(0,len(sessions)-61)].date()),end=p['expected_session'],latest_review=True)
    stamp=os.getenv('GITHUB_RUN_ID','local')+'_'+os.getenv('GITHUB_RUN_ATTEMPT','1')
    for name,value in [('ledger',ledger),('latest',summary),('changes',{'events':changes})]:dump(out/'history'/stamp/(name+'.json'),value)
    (out/'README.md').write_text('# Phase5 prospective shadow\n\nSource '+p['run_url']+'; prices '+p['expected_session']+'. Existing daily strategy/cron unchanged. Repeated active hypotheses do not create parallel paper trades. Source bars, hashes, trigger/invalidation/target and timestamps retained. No external alerts, no orders, no production Entry. Expired/stale/pre-registration observations never enter the prospective denominator. Individual outcomes are not a portfolio return claim. Missed-move review uses prior-session features and later outcome bounds only.\n')
    print(json.dumps(summary));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',default='output/phase5/shadow');a=p.parse_args();update(a.snapshot,a.output)
