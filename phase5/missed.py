"""Future labels for missed-move review, never supplied to signal features."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from phase4.research import dump
from phase5.hypotheses import CORE,cheap_mask,pattern
from phase5.data import historical_window
from research import price_structure

def review(data,prepared,sessions,signals,output,start='2026-03-05',end='2026-10-21',latest_review=False):
    signalkeys={(s,r['date'],name) for name,sigs in signals.items() if name in CORE for rows in sigs.values() for s,r in rows}
    rows=[];excluded_outcome_windows=0
    for symbol,df in data.items():
        d=prepared[symbol];grid=sessions[(sessions>=start)&(sessions<=end)];blocked_until=None
        if latest_review:grid=grid[-40:]
        for date in grid:
            if date not in df.index or (blocked_until is not None and date<=blocked_until):continue
            pos=sessions.get_loc(date);future=sessions[pos+1:pos+21];future=future[future<=pd.Timestamp(end)]
            if len(future)<20:continue
            f=df.reindex(future);q=set(df.attrs.get('quarantine',[]))
            if not f[['Open','High','Low','Close','Volume']].notna().all().all() or not f.Volume.gt(0).all() or any(str(x.date()) in q for x in future):excluded_outcome_windows+=1;continue
            gain=float(100*(f.High.max()/df.loc[date,'Close']-1))
            if gain<8:continue
            prefix=d.loc[:date];eligible=historical_window(prefix,sessions[:pos+1])
            if not eligible['eligible']:continue
            from phase5.hypotheses import specifications
            plan=json.loads(Path('phase5/protocol.json').read_text());specs=specifications(plan)
            status={};gate_values={'volume_ratio':float(prefix.volume_ratio.iloc[-1]),'gain5_pct':float(prefix.gain5.iloc[-1]),'ema20_extension_atr':float(prefix.extension_atr.iloc[-1]),'rs20':float(prefix.RS20.iloc[-1]) if pd.notna(prefix.RS20.iloc[-1]) else None}
            for engine in CORE:
                recorded=(symbol,str(date.date()),engine) in signalkeys
                if recorded:status[engine]='prior_session_signal_recorded; realized portfolio fill may differ'
                elif not bool(cheap_mask(prefix,specs[engine]).iloc[-1]):
                    last=prefix.iloc[-1];why=[]
                    if last.volume_ratio<1.5:why.append('volume_below1.5x')
                    if last.Close<=last.Open:why.append('bullish_close_not_confirmed')
                    if last.gain5>8 or last.extension_atr>2:why.append('extended_entry_blocked')
                    if last.ATR14/last.Close*100>8:why.append('ATR_risk_over8pct')
                    if pd.isna(last.RS120):why.append('synchronized_RS_history_missing')
                    if engine=='failed_breakdown' and pd.isna(last.failed_level20):why.append('no_prior_failed_breakdown_reclaim')
                    if engine=='base_contraction' and not last.base_ok30:why.append('base_not_contracting')
                    why.append('registered_price_momentum_RS_trigger_not_fully_confirmed')
                    status[engine]=';'.join(why)
                else:
                    ok,reason,_=pattern(prefix,specs[engine],price_structure(prefix))
                    status[engine]=reason if not ok else 'target_RR_stop_or_condition_gate_not_satisfied'
            first8=future[np.flatnonzero((f.High.to_numpy()/df.loc[date,'Close']-1)>=.08)[0]]
            later_confirmations=[{'engine':e,'signal_date':dt} for ss,dt,e in signalkeys if ss==symbol and date<=pd.Timestamp(dt)<first8]
            rows.append({'symbol':symbol,'prior_signal_date':str(date.date()),'outcome_start':str(future[0].date()),'outcome_end':str(future[-1].date()),
              'prior_close':float(df.loc[date,'Close']),'maximum_future_high_gain_pct':gain,'threshold8':True,'threshold10':gain>=10,
              'prior_data_vendor_window_eligible':True,'independently_validated_history':False,'engine_reasons':status,'prior_gate_values':gate_values,'recorded_core_signals_before_first8pct_touch':later_confirmations,'no_recorded_core_signal_before8pct_touch':not bool(later_confirmations),
              'missed_by_all_three':all('signal_recorded' not in v for v in status.values()),
              'guaranteed_entry_or_profit':False,'overlap_policy':'At most one event per symbol per20-session outcome horizon',
              'note':'Future daily high is an outcome bound, not a guaranteed tradable return. Reasons were evaluated using prior-session features only; no thresholds optimized from this review.'})
            blocked_until=future[-1]
    report={'schema_version':1,'events':rows,'eligible_nonoverlapping_events':len(rows),'at_least10pct':sum(r['threshold10'] for r in rows),'missed_by_all_three':sum(r['missed_by_all_three'] for r in rows),'future_labels_used_for_entry':False,'latest_daily_review':latest_review,'excluded_unusable_outcome_windows':excluded_outcome_windows,'outcome_quality_policy':'All20 future sessions must have observed OHLCV with positive volume and no quarantine; otherwise no missed-move inference.'}
    out=Path(output);dump(out/'missed_opportunities.json',report);pd.json_normalize(rows).to_csv(out/'MISSED_OPPORTUNITIES.csv',index=False)
    (out/'MISSED_OPPORTUNITIES.md').write_text('# Missed-move review\n\nEvents are nonoverlapping per-symbol20-session windows with vendor-eligible prior-session data and a later daily high>=8% or10%. They are not guaranteed entries or realizable profits. Earliest eligible event-date labeling can precede a later confirmed signal: read recorded_core_signals_before_first8pct_touch separately from the initial-day rejection. Counts are not a trading success denominator. Every reason uses only the prior prefix; future highs label outcomes only. No fitting or rule tuning uses this review. Daily shadow history records actually observed signals and cannot backfill unseen past observations.\n')
    return report
