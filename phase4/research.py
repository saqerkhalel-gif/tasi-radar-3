"""Fixed-data registered comparison, purged time folds and complete diagnostics."""
from __future__ import annotations
import argparse,copy,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from radar import clean
from phase3.experiment import (load_snapshot,causal_signals,add_metrics,assert_baseline_reproduction,
    SectorProxy,entry_context,diagnose_trades,bootstrap_excess)
from phase4.engines import generate
from phase4.execution import simulate

REGISTRATION_COMMIT='d5c64e5e54545f3bc30b2872a963fd9d08dd8daf'
METRICS=('trades_count','win_rate_pct','average_win_pct','average_loss_pct','expectancy_pct','portfolio_return_pct','maximum_drawdown_pct','daily_sharpe_annualized')

def dump(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def folds(sessions,dates,plan):
    result=[]
    for i,test in enumerate(np.array_split(dates,plan['walk_forward']['test_folds'])):
        before=sessions[sessions<test[0]];purge=before[-plan['walk_forward']['purge_sessions']:];train=before[:-len(purge)]
        assert len(train)>=plan['walk_forward']['minimum_training_sessions'] and len(purge)==20
        assert train[-1]<purge[0]<test[0]
        result.append((train,purge,test))
    return result

def metrics_table(results):
    rows=['| Strategy | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max DD % | Sharpe |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,r in results.items():rows.append('| '+name+' | '+' | '.join('NA' if r[k] is None else str(round(r[k],4)) for k in METRICS)+' |')
    return '\n'.join(rows)

def augmented_diagnostics(original,signals,prepared,histories,bench,sessions,universe,p3):
    proxy=SectorProxy(histories,universe,sessions,p3['sector_proxy'])
    contexts={(s,r['date']):entry_context(s,r,prepared[s],bench,proxy,p3) for rows in signals.values() for s,r in rows}
    result=diagnose_trades(original['trades'],signals,contexts,prepared,histories,sessions)
    for t in result['trades']:
        d=prepared[t['symbol']].loc[:t['signal_date']];last=d.iloc[-1];atr=float(last.ATR14)
        t['distance_ema20_atr']=float((last.Close-last.EMA20)/atr)
        t['distance_ema50_atr']=float((last.Close-last.EMA50)/atr)
        t['distance_ema20_pct']=float(100*(last.Close/last.EMA20-1))
        t['momentum_before_entry']={str(n):float(100*(last.Close/d.Close.iloc[-n-1]-1)) for n in (5,20,60)}
        t['rsi_at_signal']=float(last.RSI14);t['macd_hist_at_signal']=float(last.MACD-last.MACD_signal)
        t['entry_gap_pct']=float(100*(t['entry_price']/last.Close-1))
        t['exit_timing_note']='Exit mechanics known; within-exit-bar high/low order is unknown. MFE/MAE are bounds, not realizable returns.'
    return result

def evaluate(root,output):
    plan=json.loads(Path('phase4/plan.json').read_text());p3=json.loads(Path('phase3/plan.json').read_text())
    histories,bench,sessions,cfg,latest,frozen=load_snapshot(root)
    universe=pd.read_csv('data/tasi_symbols.csv',dtype={'symbol':str});assert len(universe)==254
    dates=sessions[(sessions>=plan['comparison_start'])&(sessions<=plan['comparison_end'])]
    assert dates.isin(bench.index).all() and bench.attrs.get('historical_integrity_ok',True)
    print('Reproduce original causal signals and 25 frozen trades',flush=True)
    original,prepared=causal_signals(histories,bench,sessions,cfg)
    base=add_metrics(simulate(histories,original,bench,dates,cfg));assert_baseline_reproduction(base,frozen['full_period'])
    print('Evaluate independent engines on ALL histories, not only original trades',flush=True)
    variants,_,rejections,last=generate(histories,bench,sessions,plan)
    variants['original']=original;matched=copy.deepcopy(original)
    for rows in matched.values():
        for _,r in rows:r['_original_stop']=r['scenario']['invalidation']
    variants['original_risk_matched']=matched
    limits={'stop_variants':{'maximum_stop_distance_pct':plan['maximum_stop_pct'],'maximum_equity_risk_per_trade_pct':plan['risk']['maximum_planned_risk_per_trade_pct'],'maximum_aggregate_open_equity_risk_pct':plan['risk']['maximum_aggregate_planned_risk_pct']}}
    cfg=copy.deepcopy(cfg);cfg.setdefault('backtest',{}).update(commission_bps_per_side=15.5,slippage_bps_per_side=5,max_positions=10,max_hold_sessions=20)
    def run(name,period,stress=False):
        c=copy.deepcopy(cfg)
        if stress:c['backtest']['slippage_bps_per_side']=15
        return add_metrics(simulate(histories,variants[name],bench,period,c,limits,risk_sized=name!='original'))
    split=folds(sessions,dates,plan);results={};registry=[]
    for name in variants:
        print(name,flush=True)
        full=run(name,dates);stress=run(name,dates,True)
        temporal=[{'fold':i+1,'training_start':str(train[0].date()),'training_end':str(train[-1].date()),'purge_start':str(purge[0].date()),'purge_end':str(purge[-1].date()),'purge_sessions':len(purge),'training_sessions':len(train),
                   'test':run(name,test),'stress_test':run(name,test,True),'parameters_fitted':False,'virgin_out_of_sample':False} for i,(train,purge,test) in enumerate(split)]
        ci=bootstrap_excess(full,base,p3,len(variants)-1) if name!='original' else None
        checks={'minimum_50_trades':full['trades_count']>=50,'win_rate_40pct':full['win_rate_pct'] is not None and full['win_rate_pct']>=40,
                'positive_base_and_stress_expectancy':all(x['expectancy_pct'] is not None and x['expectancy_pct']>0 for x in (full,stress)),
                'minimum_10_trades_each_fold':all(f['test']['trades_count']>=10 for f in temporal),
                'at_least_two_profitable_folds':sum(f['test']['portfolio_return_pct']>0 for f in temporal)>=2,
                'adjusted_excess_ci_positive':ci is not None and ci['lower_mean_daily_excess_pct'] is not None and ci['lower_mean_daily_excess_pct']>0,
                'new_prospective_20_trades':False}
        results[name]={'full_period':full,'stress_costs':stress,'walk_forward':temporal,'signal_rejections':rejections.get(name,{}),'signal_count':sum(map(len,variants[name].values())),
                       'paired_daily_excess_uncertainty':ci,'evidence_checks':checks,'adopted':False,
                       'recommendation':'Shadow only; no promotion. '+', '.join(k for k,v in checks.items() if not v)}
        registry.append({'variant':name,'status':'evaluated','cost_cases':['base','stress'],'folds':3,'parameters_changed_after_registration':False})
    run_id=os.getenv('GITHUB_RUN_ID','local');url=None if run_id=='local' else 'https://github.com/saqerkhalel-gif/tasi-radar-3/actions/runs/'+run_id
    report={'schema_version':1,'run_id':run_id,'run_url':url,'created_utc':datetime.now(timezone.utc).isoformat(),'source_commit':os.getenv('GITHUB_SHA'),
            'registration_commit':REGISTRATION_COMMIT,'plan_sha256':hashlib.sha256(Path('phase4/plan.json').read_bytes()).hexdigest(),
            'frozen_run_id':latest['run_id'],'input_data_hashes':frozen['data_hashes'],'frozen_baseline_reproduced':True,
            'comparison_start':str(dates[0].date()),'comparison_end':str(dates[-1].date()),'variants':results,
            'benchmarks':{'tasi_net_buy_hold_pct':base['tasi_buy_hold_net_return_pct'],'cash_return_pct':0,'cash_interest_assumed':0},
            'costs':plan['costs'],'all_registered_experiments':registry,'current_universe_survivorship_bias_unresolved':True,
            'corporate_action_point_in_time_bias_unresolved':True,'historical_period_previously_inspected':True,'new_prospective_trade_count':0,
            'live_strategy_changed':False,'adopted':False,'limitations':plan['limitations']}
    out=Path(output);out.mkdir(parents=True,exist_ok=True);dump(out/'comparison.json',report)
    pd.DataFrame([{'variant':n,**{k:r['full_period'][k] for k in METRICS}} for n,r in results.items()]).to_csv(out/'comparison.csv',index=False)
    dump(out/'experiment_registry.json',{'registration_commit':REGISTRATION_COMMIT,'plan_sha256':report['plan_sha256'],'experiments':registry,'familywise_trials':len(variants)-1,'selection':'None; no automatic adoption; report ALL cases including zero-trade cases.'})
    diag=augmented_diagnostics(base,original,prepared,histories,bench,sessions,universe,p3);diag['run_id']=run_id;dump(out/'trade_diagnostics.json',diag)
    pd.json_normalize(diag['trades']).to_csv(out/'trade_diagnostics.csv',index=False)
    dump(out/'shadow_seed_candidates.json',{'historical_only':True,'eligible_for_prospective_entries':False,'candidates':last})
    comparison='# Strategy Comparison — Phase 4, shadow research\n\n'+str(url)+'\n\nOriginal 25 trades reproduced exactly. All 16 registered portfolios use identical dates, frozen inputs and execution costs. Original retains original sizing; the separately reported original_risk_matched isolates the effect of new risk caps.\n\n'+metrics_table({n:r['full_period'] for n,r in results.items()})+'\n\n## Higher-cost sensitivity\n\n'+metrics_table({n:r['stress_costs'] for n,r in results.items()})+'\n\nTASI net buy/hold: '+str(base['tasi_buy_hold_net_return_pct'])+'%; cash: 0%. Trade expectancy is the mean net trade return; portfolio return uses daily marked equity, ten position slots, maximum 0.5% planned NAV risk/trade and 3% aggregate for new engines. No leverage. Gaps can exceed planned risk.\n\n'
    comparison+='## Recommendations\n\n'+'\n'.join('- '+e+': '+results[e]['recommendation'] for e in plan['engines'])+'\n\nBootstrap intervals are descriptive, multiplicity-adjusted for 15 variants, dependent and based on a small reused sample; they do not establish a fresh out-of-sample result. No thresholds were retuned after these results.\n'
    (out/'STRATEGY_COMPARISON.md').write_text(comparison)
    lines=['# Walk-Forward Results','', 'These are three purged, chronological REUSED temporal tests, not virgin OOS. Parameters were registered before this run and remain fixed; no best fold/configuration is selected. Each test starts with fresh cash, closes at fold end and is reported independently; do not sum fold returns as a continuous portfolio. Training is an expanding observed prefix, separated by 20 sessions. Feature warm-up uses only the known prefix; there is no future fit.']
    for i,(train,purge,test) in enumerate(split):
        lines+=['',f'## Fold {i+1}',f'Train {train[0].date()}–{train[-1].date()} ({len(train)} sessions); purge {purge[0].date()}–{purge[-1].date()}; test {test[0].date()}–{test[-1].date()}.','',metrics_table({n:r['walk_forward'][i]['test'] for n,r in results.items()})]
    (out/'WALK_FORWARD_RESULTS.md').write_text('\n'.join(lines)+'\n')
    for name in ('RESEARCH_REVIEW.md','DEVELOPMENT_ROADMAP.md'):(out/name).write_text(Path('phase4/docs',name).read_text())
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',default='output/phase4/current');a=p.parse_args();evaluate(a.snapshot,a.output)
