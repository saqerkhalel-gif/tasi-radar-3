"""Reproduce known cohorts; harmonize comparisons and report every registered case."""
from __future__ import annotations
import argparse,copy,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from phase3.experiment import load_snapshot,causal_signals,SectorProxy,assert_baseline_reproduction,add_metrics,bootstrap_excess
from phase4.execution import simulate as legacy_simulate
from phase4.engines import generate as phase4_generate
from phase4.research import dump,metrics_table as legacy_metrics_table
from phase5.execution import simulate
from phase5.hypotheses import generate,specifications,CORE,context
from phase5.data import historical_window

def metrics_table(results):
    table=legacy_metrics_table(results).splitlines()
    table[0]+=' Execution comparison valid | Unusable holding-bar days |'
    table[1]+='---|---:|'
    for i,(name,r) in enumerate(results.items(),2):
        table[i]+=' '+('YES' if r['comparison_valid'] else 'NO — descriptive only')+' | '+str(r['stale_mark_position_days'])+' |'
    return '\n'.join(table)

def wilson(wins,n):
    if not n:return {'lower_pct':None,'upper_pct':None,'confidence':.95}
    z=1.95996398454;p=wins/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return {'lower_pct':100*(center-half),'upper_pct':100*(center+half),'confidence':.95,'method':'Wilson; overlapping correlated trades mean interval is descriptive.'}

def walk_forward(sessions,period,plan):
    tests=list(np.array_split(period,3));answer=[];excluded=set()
    for test in tests:
        before=sessions[sessions<test[0]];purge=before[-20:];train=before[:-20];train=train[~train.isin(list(excluded))]
        assert len(train)>=60 and len(purge)==20 and train[-1]<purge[0]<test[0]
        answer.append((train,purge,test))
        end=sessions.searchsorted(test[-1]);excluded.update(sessions[(sessions>=test[0])&(sessions<=sessions[min(len(sessions)-1,end+20)])])
    return answer

def enrich(r,signals,prepared,benchmark,proxy,sessions):
    bykey={(s,item['date']):item for rows in signals.values() for s,item in rows};trades=r['trades'];wins=sum(t['net_return_pct']>0 for t in trades)
    r['wins']=wins;r['win_rate_uncertainty']=wilson(wins,len(trades))
    r['payoff_ratio']=abs(r['average_win_pct']/r['average_loss_pct']) if r['average_win_pct'] is not None and r['average_loss_pct'] not in (None,0) else None
    holds=[];regimes={}
    for t in trades:
        item=bykey[(t['symbol'],t['signal_date'])];d=prepared[t['symbol']]
        ctx=item.get('entry_context') or context(t['symbol'],d.loc[:item['date']],benchmark,proxy)
        regimes.setdefault(ctx['market_regime'],[]).append(t['net_return_pct'])
        holds.append(sessions.get_loc(pd.Timestamp(t['exit_date']))-sessions.get_loc(pd.Timestamp(t['entry_date']))+1)
    r['median_holding_sessions']=float(np.median(holds)) if holds else None
    r['performance_by_regime']={k:{'trades':len(v),'win_rate_pct':100*sum(x>0 for x in v)/len(v),'expectancy_pct':float(np.mean(v))} for k,v in regimes.items()}
    return r

def screened(signals,data,sessions):
    out={};rejected=0
    for date,rows in signals.items():
        for s,r in rows:
            if not historical_window(data[s].loc[:r['date']],sessions[sessions<=r['date']])['eligible']:rejected+=1;continue
            item=copy.deepcopy(r);item['_original_stop']=item['scenario']['invalidation'];out.setdefault(date,[]).append((s,item))
    return out,rejected

def evaluate(snapshot,p4root,output):
    out=Path(output);audit=json.loads((out/'data_provenance.json').read_text());diagnostics=json.loads((out/'trade_diagnostics.json').read_text())
    assert len(audit['symbols'])==254 and diagnostics['cohort_counts']=={'baseline':25,'phase4_early_reversal':31}
    plan=json.loads(Path('phase5/protocol.json').read_text());p3=json.loads(Path('phase3/plan.json').read_text());p4plan=json.loads(Path('phase4/plan.json').read_text())
    data,b,sessions,cfg,p,frozen=load_snapshot(snapshot);p4=json.loads((Path(p4root)/'comparison.json').read_text());dates=sessions[(sessions>=plan['period'][0])&(sessions<=plan['period'][1])]
    orig,_=causal_signals(data,b,sessions,cfg);original_exact=add_metrics(legacy_simulate(data,orig,b,dates,cfg));assert_baseline_reproduction(original_exact,frozen['full_period'])
    print('Reconstruct phase4 independent signals',flush=True);p4signals,_,_,_=phase4_generate(data,b,sessions,p4plan)
    limits={'stop_variants':{'maximum_stop_distance_pct':8,'maximum_equity_risk_per_trade_pct':.5,'maximum_aggregate_open_equity_risk_pct':3}}
    early_exact=add_metrics(legacy_simulate(data,p4signals['early_reversal'],b,dates,cfg,limits,risk_sized=True));assert early_exact['trades_count']==31
    old=p4['variants']['early_reversal']['full_period']
    for key in ('win_rate_pct','expectancy_pct','portfolio_return_pct','maximum_drawdown_pct'):assert abs(early_exact[key]-old[key])<2e-5
    for a,c in zip(early_exact['trades'],old['trades']):
        assert all(a[k]==c[k] for k in ('symbol','signal_date','entry_date','exit_date','exit_reason'))
        assert abs(a['net_return_pct']-c['net_return_pct'])<2e-5
    universe=pd.read_csv('data/tasi_symbols.csv',dtype={'symbol':str});proxy=SectorProxy(data,universe,sessions,p3['sector_proxy'])
    print('Generate all registered independent hypotheses and neighborhoods',flush=True)
    variants,prepared,reject,observations,eligibles=generate(data,b,sessions,plan,proxy)
    for name,signals in [('original_risk_matched',orig),('phase4_early_reversal',p4signals['early_reversal'])]:
        variants[name],number=screened(signals,data,sessions);reject[name]={'historical_window_screen':number};eligibles[name]=len({s for rows in variants[name].values() for s,_ in rows})
    def run(name,period,stress=False):
        c=copy.deepcopy(cfg);c['backtest'].update(slippage_bps_per_side=15 if stress else 5,max_positions=10,max_hold_sessions=20)
        return enrich(add_metrics(simulate(data,variants[name],b,period,c,limits,risk_sized=True)),variants[name],prepared,b,proxy,sessions)
    split=walk_forward(sessions,dates,plan);results={};registry=[]
    bootstrap={**p3,'daily_bootstrap_block_sessions':5,'bootstrap_samples':2000,'familywise_alpha':.05,'random_seed':20261023}
    for name in variants:
        print(name,flush=True);full=run(name,dates);stress=run(name,dates,True);temporal=[]
        for i,(train,purge,test) in enumerate(split):
            temporal.append({'fold':i+1,'training_sessions':len(train),'training_start':str(train[0].date()),'training_end':str(train[-1].date()),
              'training_dates_sha256':hashlib.sha256(train.to_series().to_csv().encode()).hexdigest(),'purge_start':str(purge[0].date()),'purge_end':str(purge[-1].date()),'purge_sessions':20,
              'prior_test_and_post_test20_labels_excluded_from_training':True,'parameters_fitted':False,'test':run(name,test),'stress_test':run(name,test,True),'virgin_OOS':False})
        results[name]={'full_period':full,'stress_costs':stress,'walk_forward':temporal,'signal_count':sum(len(rows) for day,rows in variants[name].items() if day in dates),
          'causal_screened_candidate_symbols_all_history':eligibles.get(name,0),'shared_causal_eligible_universe_by_session':{date:n for date,n in audit['causal_eligibility_by_session'].items() if plan['period'][0]<=date<=plan['period'][1]},'rejected':reject[name]}
        registry.append({'variant':name,'specification':specifications(plan).get(name,{'reference':name}),'status':'evaluated','cost_cases':['base','stress'],'folds':3,'optimized':False})
    ref=results['phase4_early_reversal']['full_period'];decisions={}
    for name,r in results.items():
        ci=bootstrap_excess(r['full_period'],ref,bootstrap,len(results)-1);ci['note']='Descriptive paired block bootstrap on REUSED full-period daily returns; no virgin independent evidence.'
        r['paired_daily_excess_vs_phase4_ci']=ci;full=r['full_period'];stress=r['stress_costs'];counts=[f['test']['trades_count'] for f in r['walk_forward']]
        r['evidence_checks']={'valid_execution_comparison':full['comparison_valid'] and stress['comparison_valid'],'minimum50trades':full['trades_count']>=50,'minimum10eachfold':all(x>=10 for x in counts),
          'base_stress_positive_expectancy':all(x['expectancy_pct'] is not None and x['expectancy_pct']>0 for x in (full,stress)),
          'two_profitable_folds':sum(f['test']['portfolio_return_pct']>0 for f in r['walk_forward'])>=2,
          'risk_adjusted_improvement':full['daily_sharpe_annualized'] is not None and ref['daily_sharpe_annualized'] is not None and full['daily_sharpe_annualized']>ref['daily_sharpe_annualized'] and abs(full['maximum_drawdown_pct'])<=abs(ref['maximum_drawdown_pct']),
          'multiplicity_adjusted_daily_excess_positive':ci['lower_mean_daily_excess_pct'] is not None and ci['lower_mean_daily_excess_pct']>0,
          'independent_source_history_validated':False,'fresh30_completed_trades':False}
        if name in CORE:
            neighbors=[v for n,v in results.items() if n.startswith(name+'__')]
            stable=all(v['full_period']['trades_count']>=10 and v['full_period']['expectancy_pct'] is not None and v['full_period']['expectancy_pct']>0 and v['stress_costs']['expectancy_pct'] is not None and v['stress_costs']['expectancy_pct']>0 for v in neighbors)
            r['evidence_checks']['neighborhood_stability']=stable
            decisions[name]={'decision':'KEEP SHADOW','evidence_status':'INCONCLUSIVE','promoted':False,'failed_checks':[k for k,v in r['evidence_checks'].items() if not v]}
    run_id=os.getenv('GITHUB_RUN_ID','local')
    report={'schema_version':1,'run_id':run_id,'run_url':None if run_id=='local' else 'https://github.com/saqerkhalel-gif/tasi-radar-3/actions/runs/'+run_id,
      'source_commit':os.getenv('GITHUB_SHA'),'protocol_registration_commit':json.loads(Path('phase5/registration.json').read_text())['commit'],
      'quality_review_revision':'2; execution-validity trace and stricter missed-outcome OHLCV; hypothesis parameters unchanged','protocol_sha256':hashlib.sha256(Path('phase5/protocol.json').read_bytes()).hexdigest(),'created_utc':datetime.now(timezone.utc).isoformat(),
      'source_snapshot_run_id':p['run_id'],'phase4_comparison_run_id':p4['run_id'],'legacy_reproductions':{'original25':original_exact,'phase4_early31':early_exact},
      'variants':results,'registry':registry,'decisions':decisions,'benchmarks':{'tasi_buy_hold_net_pct':next(iter(results.values()))['full_period']['tasi_buy_hold_net_return_pct'],'cash_pct':0},
      'period':plan['period'],'all24_cases_reported':len(results)==24,'reused_historical_evidence':True,'fresh_completed_trades':0,'adopted':False,'live_files_changed':False,
      'limitations':['Current254 universe, no complete delisted/PIT membership; survivorship unresolved.','Adjusted history lacks PIT corporate-action vintages; independent series validation zero.','Legacy exact reproductions differ from harmonized references with stricter screens/zero-volume execution refusal.','Reused2026 folds/neighborhoods cannot be virgin independent evidence.']}
    dump(out/'comparison.json',report);dump(out/'experiment_registry.json',{'protocol_registration_commit':report['protocol_registration_commit'],'protocol_sha256':report['protocol_sha256'],'experiments':registry,'familywise_trials':23,'selection':'No winning configuration selected; all24 reported including zero-trade cases.'})
    keys=('trades_count','wins','win_rate_pct','average_win_pct','average_loss_pct','payoff_ratio','expectancy_pct','portfolio_return_pct','maximum_drawdown_pct','daily_sharpe_annualized','comparison_valid','stale_mark_position_days','turnover_pct_initial_nav','mean_gross_exposure_pct','median_holding_sessions')
    pd.DataFrame([{'variant':n,'signal_count':v['signal_count'],'eligible_candidate_symbols':v['causal_screened_candidate_symbols_all_history'],**{k:v['full_period'][k] for k in keys},**{'wilson_'+k:v['full_period']['win_rate_uncertainty'][k] for k in ('lower_pct','upper_pct')}} for n,v in results.items()]).to_csv(out/'COMPARISON.csv',index=False)
    issue_rows=[]
    for name,v in results.items():
        sections=[('full_base',v['full_period']),('full_stress',v['stress_costs'])]+[(f'fold{f["fold"]}_{case}',f[case]) for f in v['walk_forward'] for case in ('test','stress_test')]
        for label,result in sections:
            issue_rows.extend({'variant':name,'period':label,**item} for item in result['execution_data_issues'])
    pd.DataFrame(issue_rows,columns=['variant','period','symbol','date','reason']).to_csv(out/'EXECUTION_DATA_ISSUES.csv',index=False)
    merged={}
    for n in CORE:
        for day,rows in variants[n].items():merged.setdefault(str(day.date()),[]).extend(r for _,r in rows)
    dump(out/'candidate_signals.json',merged)
    summary='# WALK FORWARD — Phase 5\n\n'+str(report['run_url'])+'\n\n**Validity warning:** NO rows encountered missing, quarantined or zero-volume/invalid holding bars. Their displayed returns/win rates are exploratory calculations, NOT reliable execution evidence or promotion evidence. Exact symbol/date/reason is exported in execution_data_issues. YES only passes internal execution checks, not independent provenance.\n\nAll24 registered variants use identical254-stock universe, fixed dates, sizing, fees and gap handling. Each signal has a causal historical-window screen. Legacy25/31 cohorts are separately reproduced exactly; harmonized references may contain fewer trades.\n\n## Full reused period\n\n'+metrics_table({n:v['full_period'] for n,v in results.items()})+'\n\n## Higher-cost sensitivity\n\n'+metrics_table({n:v['stress_costs'] for n,v in results.items()})+'\n'
    for i,(train,purge,test) in enumerate(split):
        summary+='\n## Reused temporal fold '+str(i+1)+'\n\nTrain '+str(train[0].date())+'–'+str(train[-1].date())+' ('+str(len(train))+' label-eligible sessions); purge20; test '+str(test[0].date())+'–'+str(test[-1].date())+'. Prior test and post-test20 labels excluded from training; parameters fixed/no fit. Past prices only warm causal indicators. Fresh cash and forced fold-end liquidation.\n\n'+metrics_table({n:v['walk_forward'][i]['test'] for n,v in results.items()})+'\n'
    summary+='\nTASI net buy-and-hold: '+str(report['benchmarks']['tasi_buy_hold_net_pct'])+'%; cash0%. CSV/JSON include Wilson uncertainty, payoff, turnover(two-sided/initialNAV), average close-mark gross exposure, Saudi-session median hold, regime results and fold stress cases. Intervals are descriptive: trades overlap. No newly untouched forward trade exists yet.\n'
    (out/'WALK_FORWARD.md').write_text(summary)
    decision='# DECISION — Phase 5\n\n**KEEP SHADOW / INCONCLUSIVE. No production changes and no promotion.**\n\n'
    for n,v in decisions.items():decision+='- '+n+': '+v['decision']+'; '+v['evidence_status']+'. Missing evidence: '+', '.join(v['failed_checks'])+'.\n'
    decision+='\nWhere valid_execution_comparison is false, even an attractive win rate or return cannot support an improvement claim; inspect symbol/date execution_data_issues. Research objective45–50% is not promised or sufficient. Require adequate independent after-cost expectancy and risk-adjusted stability. All negative cases preserved; no best historical parameter selected. Latest-bar success does not rehabilitate a full history. Untouched prospective observations are separate and never backfilled.\n\n'+'\n'.join(report['limitations'])+'\n'
    (out/'DECISION.md').write_text(decision);(out/'HYPOTHESES.md').write_text(Path('phase5/docs/HYPOTHESES.md').read_text())
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--phase4-results',required=True);p.add_argument('--output',default='output/phase5/current');a=p.parse_args();evaluate(a.snapshot,a.phase4_results,a.output)
