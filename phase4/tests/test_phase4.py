import copy,json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from phase4.engines import features,cheap_mask,candidate,scenario,retest_level
from phase4.research import folds
from phase4.data_audit import independent_index
from phase4.shadow import advance,before_next_open

PLAN=json.loads(Path('phase4/plan.json').read_text())

def bars(n=260):
    ix=pd.bdate_range('2025-01-01',periods=n);c=50+np.arange(n)*.02+np.sin(np.arange(n)/5)
    return pd.DataFrame({'Open':c-.1,'High':c+.6,'Low':c-.6,'Close':c,'Volume':np.full(n,100000.)},index=ix)

def test_features_use_only_prefix_and_synchronized_calendar():
    d=bars();benchmark=d.copy();full=features(d,benchmark,d.index);prefix=features(d.iloc[:220],benchmark.iloc[:220],d.index[:220])
    pd.testing.assert_frame_equal(full.iloc[:220],prefix)
    broken=d.drop(d.index[-35]);r=features(broken,benchmark,d.index)
    assert pd.isna(r.RS60.iloc[-1]) and pd.isna(r.RS120.iloc[-1])
    assert pd.notna(r.RS20.iloc[-1])

def test_nearer_major_resistance_cannot_be_skipped_for_ten_percent():
    d=features(bars(),bars(),bars().index);d.loc[d.index[-1],['Close','ATR14','prior_support20']]=[100,1,97]
    s={'zones':[{'low':105,'touches':3},{'low':120,'touches':3}],'nearest_support':{'low':97}}
    r,reason=scenario(d,s,PLAN);assert r is None and reason=='upside_below_10'

def ready(engine):
    d=features(bars(),bars(),bars().index)
    d.loc[d.index[-2],['Close','EMA20','High','RSI14','MACD','MACD_signal']]=[99,100,99,45,0,0]
    d.loc[d.index[-1],['Open','Close','Low','High','EMA20','EMA50','EMA200','ATR14','prior_support20','RSI14','MACD','MACD_signal','RS20','RS60','RS120','volume_ratio','gain5','extension_atr']]=[99,100,99,101,99,98,97,1,97,50,2,0,5,4,3,2,2,1]
    d.loc[d.index[-1],['reclaim','above5','momentum','RS20_improving','contraction','demand','touch20']]=True
    d.loc[d.index[-11],'EMA50']=96
    s={'zones':[{'low':115,'high':116,'touches':3}],'nearest_support':{'low':97},'confirmed_higher_lows':True}
    if engine=='breakout_retest':
        # Frozen earlier level with later holds, a retest is NOT today's first break.
        d.loc[d.index[-3],['prior_resistance20','Close']]=[99,100]
    return d,s

@pytest.mark.parametrize('engine',['early_reversal','trend_pullback','breakout_retest'])
def test_independent_engines_can_emit_without_original_signal_set(engine):
    d,s=ready(engine);assert cheap_mask(d,engine,'',PLAN).iloc[-1]
    r,reason=candidate('TEST',d,engine,'',PLAN,d.index,s,{'entry_eligible':True})
    assert reason is None and r['scenario']['upside_pct']>=10 and r['scenario']['reward_risk']>=2
    assert not r['live_order_authorized']

@pytest.mark.parametrize('ablation',['','rs20_only','no_extension_guard','no_pattern_support'])
def test_ablations_cannot_remove_volume_confirmation(ablation):
    d,_=ready('early_reversal');d.loc[d.index[-1],'volume_ratio']=1.49
    assert not cheap_mask(d,'early_reversal',ablation,PLAN).iloc[-1]

def test_quarantine_blocks_every_engine_even_when_pattern_confirms():
    d,s=ready('early_reversal');d.attrs['price_repairs']=[{'date':str(d.index[-1].date())}]
    r,reason=candidate('TEST',d,'early_reversal','',PLAN,d.index,s)
    assert r is None and reason=='quarantined_or_zero_volume'

def test_purged_folds_are_disjoint_and_past_only():
    ix=bars(400).index;parts=folds(ix,ix[220:380],PLAN)
    all_test=[]
    for train,purge,test in parts:
        assert train[-1]<purge[0]<test[0] and len(purge)==20
        assert not len(train.intersection(test));all_test.extend(test)
    assert len(all_test)==len(set(all_test))==160

def test_html_and_wrong_index_fail_independent_reconciliation():
    b=bars();assert independent_index('<html>verification</html>',b)['observed_overlap_sessions']==0
    text=b.reset_index(names='Date')[['Date','Close']].to_csv(index=False)
    assert independent_index(text,b)['entire_historical_index_independently_reconciled']
    changed=b.copy();changed.Close*=2
    r=independent_index(text,changed);assert r['sessions_exceeding_0_1pct_tolerance']==len(b) and not r['entire_historical_index_independently_reconciled']

def observation():
    return {'status':'pending','signal_date':'2026-10-18','recorded_utc':'2026-10-18T15:00:00+00:00','scenario':{'invalidation':95,'conditional_target':112},'eligible_prospective':True}

def test_shadow_stop_first_costs_and_no_historical_backfill():
    ix=pd.to_datetime(['2026-10-18','2026-10-19']);d=pd.DataFrame({'Open':[99,100],'High':[100,113],'Low':[98,94],'Close':[99,108],'Volume':[100,100]},index=ix)
    r=advance(observation(),d,ix);assert r['status']=='closed' and r['exit_price']==95 and r['net_return_pct']< -5
    late=observation();late['recorded_utc']='2026-10-19T08:00:00+00:00'
    assert advance(late,d,ix)['status']=='expired'
    seed=observation();seed['status']='historical_seed';assert advance(seed,d,ix)['status']=='historical_seed'
    assert before_next_open('2026-10-19T06:59:00+00:00',pd.Timestamp('2026-10-19'))
    assert not before_next_open('2026-10-19T07:01:00+00:00',pd.Timestamp('2026-10-19'))

def test_shadow_next_open_and_bad_data_cannot_create_success():
    ix=pd.to_datetime(['2026-10-18','2026-10-19']);d=pd.DataFrame({'Open':[99,111],'High':[100,113],'Low':[98,100],'Close':[99,112],'Volume':[100,100]},index=ix)
    assert advance(observation(),d,ix)['reason']=='next_open_invalidates_entry_gates'
    d.loc[ix[-1],'Open']=100;d.attrs['quarantine']=['2026-10-19']
    assert advance(observation(),d,ix)['reason']=='quarantined_execution_bar'

def test_execution_unchanged_original_and_risk_cap_at_admission():
    from phase3.experiment import simulate as old
    from phase4.execution import simulate
    ix=pd.bdate_range('2026-01-01',periods=4)
    data={str(i):pd.DataFrame({'Open':[100]*4,'High':[101]*4,'Low':[99]*4,'Close':[100,99.5,99.5,99.5],'Volume':[100]*4},index=ix) for i in range(10)}
    record={'date':'2025-12-31','technical_score':1,'scenario':{'invalidation':95,'conditional_target':112},'_original_stop':95}
    signals={ix[0]:[(str(i),copy.deepcopy(record)) for i in range(6)],ix[1]:[(str(i),copy.deepcopy(record)) for i in range(6,10)]}
    limits={'stop_variants':{'maximum_stop_distance_pct':8,'maximum_equity_risk_per_trade_pct':.5,'maximum_aggregate_open_equity_risk_pct':3}}
    assert simulate(data,signals,data['0'],ix,{})==old(data,signals,data['0'],ix,{})
    result=simulate(data,signals,data['0'],ix,{},limits,risk_sized=True)
    assert result['maximum_aggregate_planned_risk_pct']<=3+1e-10
    assert all(t['planned_risk_cash']<=.005*t['equity_at_entry']+1e-8 for t in result['trades'])
