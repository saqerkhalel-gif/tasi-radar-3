"""Entry-time features and separately labelled future excursion bounds for all56 trades."""
import argparse,json,os
from pathlib import Path
import numpy as np
import pandas as pd
from phase3.experiment import load_snapshot,SectorProxy
from phase4.research import dump
from phase5.hypotheses import prepare,context
from research import price_structure


def one_trade(t,d,benchmark,sessions,proxy,cohort):
    signal=pd.Timestamp(t['signal_date']);entry=pd.Timestamp(t['entry_date']);exitdate=pd.Timestamp(t['exit_date']);prefix=d.loc[:signal];last=prefix.iloc[-1];atr=float(last.ATR14)
    during=d.loc[entry:exitdate];sequence=[];cumhigh=-np.inf;cumlow=np.inf;entryprice=t['entry_price']
    for date,row in during.iterrows():
        cumhigh=max(cumhigh,float(row.High));cumlow=min(cumlow,float(row.Low));both=bool(row.High>=t['target'] and row.Low<=t['stop'])
        sequence.append({'date':str(date.date()),'open':float(row.Open),'high':float(row.High),'low':float(row.Low),'close':float(row.Close),'cumulative_mfe_pct':100*(cumhigh/entryprice-1),'cumulative_mae_pct':100*(cumlow/entryprice-1),
          'stop_and_target_same_bar':both,'within_bar_order':'UNKNOWN; stop-first execution if both touched','after_exit_unknown_on_exit_bar':date==exitdate})
    breakouts=prefix[prefix.Close>prefix.prior_resistance20];age=int(len(prefix)-1-prefix.index.get_loc(breakouts.index[-1])) if len(breakouts) else None
    base=0
    for n in range(5,min(61,len(prefix))):
        w=prefix.iloc[-n:];span=100*(w.High.max()/w.Low.min()-1)
        if span<=20:base=n
        else:break
    idx=sessions.get_indexer([entry,exitdate]);structure=price_structure(prefix);ctx=context(t['symbol'],prefix,benchmark,proxy)
    first3=d.reindex(sessions[sessions>=entry][:3]).dropna(subset=['Close']);level=float(last.prior_resistance20)
    isbreak=bool(last.Close>last.prior_resistance20);failed=bool(isbreak and len(first3) and first3.Close.lt(level).any())
    stopwidth=(entryprice-t['stop'])/atr;gain5=float(last.gain5);extension=float(last.extension_atr)
    tags=[]
    if failed:tags.append('breakout_failed_within3_sessions')
    if gain5>8 or extension>2:tags.append('extended_or_chased')
    if stopwidth<1.5:tags.append('stop_below1.5ATR')
    if ctx['market_regime']=='Risk_OFF':tags.append('weak_market')
    if ctx['sector_rs20_pct_points'] is None:tags.append('sector_unavailable')
    elif ctx['sector_rs20_pct_points']<0:tags.append('weak_current_sector_proxy')
    if t['exit_reason'].startswith('gap_stop'):tags.append('gap_through_stop')
    return {**t,'cohort':cohort,'entry_distance_ema20_atr':float((entryprice-last.EMA20)/atr),'entry_distance_ema50_atr':float((entryprice-last.EMA50)/atr),
      'stop_distance_atr':stopwidth,'entry_gap_pct':float(100*(entryprice/last.Close-1)),'trailing_return5_pct':gain5,'trailing_return10_pct':float(last.ROC10),'trailing_return20_pct':float(last.ROC20),
      'rs20_pct_points':float(last.RS20) if pd.notna(last.RS20) else None,'rs60_pct_points':float(last.RS60) if pd.notna(last.RS60) else None,'rs120_pct_points':float(last.RS120) if pd.notna(last.RS120) else None,
      'volume_ratio':float(last.volume_ratio),'volatility_contraction':bool(last.contraction),'confirmed_higher_lows':structure['confirmed_higher_lows'],'breakout_age_sessions':age,'base_length_observed_max60_sessions':base,
      'holding_sessions':int(idx[1]-idx[0]+1),'exit_stop_gap_pct':float(100*(t['exit_price']/t['stop']-1)) if t['exit_reason'].startswith('gap_stop') else None,
      'mfe_through_exit_bar_pct':100*(during.High.max()/entryprice-1),'mae_through_exit_bar_pct':100*(during.Low.min()/entryprice-1),'excursion_sequence':sequence,
      'descriptive_failure_tags':tags,'entry_context':ctx,'intrabar_path_identifiable':False,'future_labels_used_for_entry':False,
      'interpretation':'Associations only, not proven causes. Daily extrema through the exit bar may occur after a stop exit. Sequence is identifiable across dates, not within a daily bar.'}


def diagnose(snapshot,phase4_results,output):
    data,b,sessions,cfg,p,bt=load_snapshot(snapshot);p4=json.loads((Path(phase4_results)/'comparison.json').read_text())
    assert p4['run_id']=='39941086262' and p4['frozen_run_id']==p['run_id']
    universe=pd.read_csv('data/tasi_symbols.csv',dtype={'symbol':str});p3=json.loads(Path('phase3/plan.json').read_text());proxy=SectorProxy(data,universe,sessions,p3['sector_proxy']);prepared={s:prepare(d,b,sessions) for s,d in data.items()}
    cohorts={'baseline':bt['full_period']['trades'],'phase4_early_reversal':p4['variants']['early_reversal']['full_period']['trades']};assert len(cohorts['baseline'])==25 and len(cohorts['phase4_early_reversal'])==31
    rows=[one_trade(t,prepared[t['symbol']],b,sessions,proxy,name) for name,trades in cohorts.items() for t in trades]
    groups={}
    for name in cohorts:
        rr=[r for r in rows if r['cohort']==name];groups[name]={}
        for tag in sorted({tag for r in rr for tag in r['descriptive_failure_tags']}):
            subset=[r for r in rr if tag in r['descriptive_failure_tags']];groups[name][tag]={'trades':len(subset),'losses':sum(r['net_return_pct']<=0 for r in subset),'mean_net_return_pct':float(np.mean([r['net_return_pct'] for r in subset]))}
    report={'run_id':os.getenv('GITHUB_RUN_ID','local'),'cohort_counts':{k:len(v) for k,v in cohorts.items()},'trades':rows,'associations':groups,'all56_exported':True,'no_causal_claim':True}
    out=Path(output);dump(out/'trade_diagnostics.json',report)
    flat=[{k:v for k,v in r.items() if k!='excursion_sequence'} for r in rows];pd.json_normalize(flat).to_csv(out/'TRADE_DIAGNOSTICS.csv',index=False)
    sequence=[{'cohort':r['cohort'],'symbol':r['symbol'],'entry_date':r['entry_date'],**bar} for r in rows for bar in r['excursion_sequence']];pd.DataFrame(sequence).to_csv(out/'TRADE_EXCURSIONS.csv',index=False)
    (out/'TRADE_DIAGNOSTICS.md').write_text('# Trade diagnostics\n\nAll25 original and31 phase4 early-reversal trades, including winners and losers. Entry features use only the prefix through signal close. Outcomes and excursion sequences are separately labelled future observations; they never drive an entry filter.\n\nOriginal known associations:18/25 extended entries(16losses);8/25 failed breakouts(8losses);19/25 stops below1.5ATR(15losses). These overlap and do not prove causality. Phase5 exports both signal-close extension and actual gap-adjusted entry distances. Regime and sector definitions differ from phase3 legacy definitions and are explicitly recorded.\n\nDaily bar order cannot be recovered. MFE/MAE include exit-bar bounds and may include prices after an intraday exit. TRADE_EXCURSIONS.csv records identifiable date ordering, never an invented intrabar path.\n')
    print(json.dumps(report['cohort_counts']));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--phase4-results',required=True);p.add_argument('--output',default='output/phase5/current');a=p.parse_args();diagnose(a.snapshot,a.phase4_results,a.output)
