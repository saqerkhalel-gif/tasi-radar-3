"""Append-only prospective observations; isolated paper outcomes, never live orders.
Paper trades here are unit-notional observations, not a portfolio equity curve.
Portfolio risk evidence remains the separately capped registered simulation.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from research import trade_exit
from radar import session_calendar
from phase4.engines import generate,ENGINES
from phase4.research import dump

REGISTRATION_DATE='2026-10-23'

def before_next_open(recorded,execution):
    open_time=pd.Timestamp(execution).tz_localize('Asia/Riyadh')+pd.Timedelta(hours=10)
    return pd.Timestamp(recorded)<open_time

def advance(item,df,sessions):
    if item['status'] in ('closed','expired','historical_seed'):return item
    signal=pd.Timestamp(item['signal_date']);grid=sessions[sessions>signal];q=set(df.attrs.get('quarantine',[]));cost=.00205
    if not len(grid):return item
    execution=grid[0]
    if item['status']=='pending':
        if not before_next_open(item['recorded_utc'],execution):item.update(status='expired',reason='recorded_after_next_open');return item
        if execution not in df.index:
            if len(df) and df.index[-1]>execution:item.update(status='expired',reason='missing_execution_bar')
            return item
        if str(execution.date()) in q:item.update(status='expired',reason='quarantined_execution_bar');return item
        p=float(df.loc[execution,'Open']);stop=item['scenario']['invalidation'];target=item['scenario']['conditional_target']
        if not 0<stop<p<target or 100*(target/p-1)<10 or (target-p)/(p-stop)<2 or (p-stop)/p>.08:
            item.update(status='expired',reason='next_open_invalidates_entry_gates');return item
        item.update(status='open',entry_date=str(execution.date()),entry_price=p)
    entry=pd.Timestamp(item['entry_date']);elapsed=sessions[sessions>=entry]
    for age,date in enumerate(elapsed,1):
        if str(date.date()) in q:
            item['outcome_data_quality_blocked']=True;return item
        if date not in df.index:
            if date<=df.index[-1]:item['outcome_data_quality_blocked']=True
            return item
        bar=df.loc[date];price,reason=trade_exit(bar,item['scenario']['invalidation'],item['scenario']['conditional_target'])
        if price is None and age>=20:price=float(bar.Close);reason='time_exit'
        if price is not None:
            item.update(status='closed',exit_date=str(date.date()),exit_price=price,exit_reason=reason,
                        net_return_pct=100*(price*(1-cost)/(item['entry_price']*(1+cost))-1),outcome_data_quality_blocked=False);return item
    return item

def update(snapshot,output,now=None):
    root=Path(snapshot);inputs=root/'research_inputs';latest=json.loads((root/'output/latest.json').read_text())
    expected_run=os.getenv('SOURCE_RUN_ID',latest['run_id']);assert str(latest['run_id'])==str(expected_run)
    assert latest['universe_count']==254
    cfg=json.loads((inputs/'config.json').read_text());meta=json.loads((inputs/'stock_metadata.json').read_text());assert len(meta)==254
    histories={}
    for s,m in meta.items():
        d=pd.read_csv(inputs/(s+'.csv.gz'),index_col='Date',parse_dates=True,float_precision='round_trip');d.attrs.update(m);histories[s]=d
    bench=pd.read_csv(inputs/'benchmark.csv',index_col='Date',parse_dates=True,float_precision='round_trip');bench.attrs.update(json.loads((inputs/'benchmark_metadata.json').read_text()))
    now=now or datetime.now(timezone.utc);sessions,_=session_calendar(now,cfg);current_expected=str(sessions[-1].date())
    out=Path(output);ledgerfile=out/'ledger.json';ledger=json.loads(ledgerfile.read_text()) if ledgerfile.exists() else {'schema_version':1,'observations':[]}
    for item in ledger['observations']:advance(item,histories[item['symbol']],sessions)
    plan=json.loads(Path('phase4/plan.json').read_text());_,_,reject,records=generate(histories,bench,sessions,plan,latest_only=True)
    known={r['id'] for r in ledger['observations']};added=0
    benchmark_ok=latest.get('benchmark_quality',{}).get('entry_eligible',False) and bench.attrs.get('historical_integrity_ok',False)
    for r in records:
        if r['variant'] not in ENGINES:continue
        id=r['variant']+':'+r['symbol']+':'+r['date']
        if id in known:continue
        prospective=(r['date']>=REGISTRATION_DATE and r['date']==current_expected==latest['expected_session'] and benchmark_ok)
        ledger['observations'].append({'id':id,'engine':r['variant'],'symbol':r['symbol'],'signal_date':r['date'],'recorded_utc':now.isoformat(),
          'source_run_id':latest['run_id'],'source_run_url':latest['run_url'],'source_price_date':latest['expected_session'],'status':'pending' if prospective else 'historical_seed',
          'scenario':r['scenario'],'features':r['features'],'reasons':r['reasons'],'eligible_prospective':prospective,
          'input_close_sha256':hashlib.sha256(histories[r['symbol']].to_csv().encode()).hexdigest(),'live_order_authorized':False})
        added+=1
    ledger.update(updated_utc=now.isoformat(),source_run_id=latest['run_id'],source_price_date=latest['expected_session'],live_strategy_changed=False,
                  paper_outcome_method='Unit-notional after-cost hypothetical trades, no portfolio return claim; simultaneous names are not an investable capped portfolio.',
                  new_observations=added)
    dump(ledgerfile,ledger)
    closed=[x for x in ledger['observations'] if x['status']=='closed' and x['eligible_prospective'] and not x.get('outcome_data_quality_blocked')]
    summary={'source_run_id':latest['run_id'],'source_price_date':latest['expected_session'],'current_expected_session':current_expected,'benchmark_entry_eligible':bool(benchmark_ok),
             'updated_utc':now.isoformat(),'prospective_closed_trade_count':len(closed),'adopted':False,'signal_rejections':reject,
             'engines':{e:{'recorded_prospective':sum(x['engine']==e and x['eligible_prospective'] for x in ledger['observations']),
                          'closed_trades':sum(x['engine']==e for x in closed),'win_rate_pct':100*sum(x['engine']==e and x['net_return_pct']>0 for x in closed)/sum(x['engine']==e for x in closed) if any(x['engine']==e for x in closed) else None} for e in ENGINES}}
    dump(out/'latest.json',summary);stamp=os.getenv('GITHUB_RUN_ID','local')+'_'+os.getenv('GITHUB_RUN_ATTEMPT','1');dump(out/'history'/stamp/'latest.json',summary);dump(out/'history'/stamp/'ledger.json',ledger)
    (out/'README.md').write_text('# Prospective shadow observations\n\nUpdated '+now.isoformat()+'. Source daily run '+latest['run_url']+'. Price session '+latest['expected_session']+'.\n\nNo live signals changed; no orders. Pre-registration/stale snapshots never enter the prospective denominator. Paper outcomes are individual unit-notional observations, not a capital-constrained portfolio or adoption evidence. Insufficient history and quarantined bars block outcomes. Repeated workflow executions do not duplicate signals.\n')
    print(json.dumps(summary,default=str));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',default='output/phase4/shadow');a=p.parse_args();update(a.snapshot,a.output)
