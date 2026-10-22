import json
from pathlib import Path
import pandas as pd
import numpy as np
import pytest
import radar
import research
from test_radar import candles, CFG


def test_quote_repair_cannot_authorize_entry():
    d=candles();d.attrs['price_repairs']=[{'date':str(d.index[-1].date())}]
    r=radar.analyze('T',d,CFG,d)
    assert not r['data_quality']['entry_eligible'] and 'unverified_or_suspicious_OHLCV' in r['entry_blockers']
    assert r['classification'] not in ('Entry','Partial Entry')


def test_future_repair_does_not_contaminate_past_signal():
    d=candles();d.attrs['price_repairs']=[{'date':str(d.index[-1].date())}]
    assert research.quality_audit(d.iloc[:-1])['entry_eligible']


def test_large_adjusted_jump_quarantined():
    d=candles();d.iloc[-1,d.columns.get_loc('Close')]*=2
    assert not research.quality_audit(d)['entry_eligible']


def test_missing_calendar_rows_disclosed():
    d=candles();s=d.index;d=d.drop(s[-3])
    q=research.quality_audit(d,s)
    assert q['missing_sessions']==[str(s[-3].date())]


def test_zero_volume_blocked():
    d=candles();d.iloc[-1,d.columns.get_loc('Volume')]=0
    assert not research.quality_audit(d)['entry_eligible']


def test_pivots_require_two_observed_right_bars():
    d=radar.indicators(candles());date=d.index[-1];d.loc[date,'Low']=1
    s=research.price_structure(d)
    assert date.date().isoformat() not in [x['date'] for x in s['last_confirmed_lows']]
    assert all(pd.Timestamp(x['confirmed_date'])<=date for x in s['last_confirmed_lows'])


def test_precomputed_features_equal_prefix_and_ignore_future():
    d=candles();prepared=radar.indicators(d)
    a=radar.analyze('T',d.iloc[:240],CFG,d.iloc[:240])
    b=radar.analyze('T',d.iloc[:240],CFG,d.iloc[:240],prepared=prepared.iloc[:240])
    assert a==b
    d.iloc[240:,d.columns.get_loc('Close')]=10000
    assert radar.analyze('T',d.iloc[:240],CFG,d.iloc[:240],prepared=radar.indicators(d).iloc[:240])==a


def test_benchmark_disagreement_blocks():
    d=candles()[['Close']];live=d.iloc[-1:].copy();live['Close']*=1.01
    q=research.benchmark_audit(d,live,d.index,str(d.index[-1].date()),[])
    assert not q['entry_eligible'] and q['mismatch_dates']
    assert research.benchmark_audit(d,d.iloc[-1:],d.index,str(d.index[-1].date()),[])['entry_eligible']


def test_benchmark_no_overlap_cannot_authorize_live_entry():
    d=candles()[['Close']]
    assert not research.benchmark_audit(d,None,d.index,str(d.index[-1].date()),[])['entry_eligible']


@pytest.mark.parametrize('bar,expected,reason',[
    ({'Open':85,'Low':80,'High':125},85,'gap_stop'),
    ({'Open':125,'Low':120,'High':130},120,'gap_target_capped'),
    ({'Open':100,'Low':89,'High':121},90,'stop'),
    ({'Open':100,'Low':95,'High':121},120,'target')])
def test_conservative_exit_ordering(bar,expected,reason):
    assert research.trade_exit(bar,90,120)==(expected,reason)


def execution_case(cost=0,quarantine=False,gap=100):
    dates=pd.bdate_range('2026-01-01',periods=3)
    d=pd.DataFrame({'Open':[gap,100,100],'Low':[99,99,99],'High':[101,101,101],'Close':[100,100,100],'Volume':1000},index=dates)
    d.attrs['quarantine']=[str(dates[0].date())] if quarantine else []
    signal={'date':'2025-12-31','technical_score':50,'scenario':{'invalidation':90,'conditional_target':120}}
    b=pd.DataFrame({'Close':[100,100,100]},index=dates)
    cfg={**CFG,'backtest':{'commission_bps_per_side':cost,'slippage_bps_per_side':0,'max_positions':1,'max_hold_sessions':20}}
    return research.portfolio_backtest({'T':d},{dates[0]:[('T',signal)]},b,dates,cfg)


def test_costs_reduce_flat_price_profit_and_drawdown():
    free=execution_case();costly=execution_case(20)
    assert free['portfolio_return_pct']==pytest.approx(0)
    assert costly['portfolio_return_pct']<0 and costly['maximum_drawdown_pct']<0
    assert costly['trades_count']==1 and costly['average_loss_pct']<0


def test_quarantined_execution_bar_skipped():
    b=execution_case(quarantine=True)
    assert b['trades_count']==0 and b['skipped_orders']['quarantined_execution_bar']==1
    assert b['win_rate_pct'] is None


def test_gap_cannot_enter_when_remaining_upside_below_ten():
    b=execution_case(gap=115)
    assert b['trades_count']==0 and b['skipped_orders']['next_open_invalidates_reward_or_risk']==1


def test_ledger_levels_frozen_no_same_day_outcome():
    d=candles();r=radar.analyze('T',d,CFG,d)
    r['classification']='Early Watch';r['data_quality']['entry_eligible']=True
    ledger=research.update_ledger(None,[r],{'T':d},'one');old=json.loads(json.dumps(ledger))
    r['scenario']['conditional_target']=999
    new=research.update_ledger(old,[r],{'T':d},'two')
    assert len(new['opportunities'])==1 and new['opportunities'][0]['observed_sessions']==0
    # Levels are serialized independently when saved; this simulates persisted input.
    assert new['opportunities'][0]['scenario']['conditional_target']!=999


def test_history_future_mutation_cannot_change_earlier_signals():
    d=candles(210);b=d[['Close']].copy();seen=[]
    def capture(symbol,df,cfg,bench,expected,sessions,**kw):
        r=radar.analyze(symbol,df,cfg,bench,expected,sessions,**kw)
        if len(df)==205:seen.append(r)
        return r
    research.historical_research({'T':d},b,d.index,CFG,capture,radar.indicators)
    d.iloc[205:,d.columns.get_loc('High')]=99999
    research.historical_research({'T':d},b,d.index,CFG,capture,radar.indicators)
    assert seen[0]==seen[1]
