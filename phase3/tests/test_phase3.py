import copy,json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from phase3 import experiment as e
from phase3.quality_recheck import valid_daily_row
from research import portfolio_backtest
import radar

PLAN=json.loads(Path('phase3/plan.json').read_text());CFG=json.loads(Path('config.json').read_text())


def frames(n=280):
    dates=pd.bdate_range('2025-01-01',periods=n+1);c=100+np.arange(n)*.1
    d=pd.DataFrame({'Open':c,'High':c+.05,'Low':c-.05,'Close':c,'Volume':1000.},index=dates[:-1])
    d.iloc[180,d.columns.get_loc('High')]=150
    d.iloc[240,d.columns.get_loc('Close')]+=.2;d.iloc[240,d.columns.get_loc('High')]=d.iloc[240]['Close']+.05;d.iloc[240,d.columns.get_loc('Volume')]=5000
    b=pd.DataFrame({'Close':100.},index=dates)
    return d,b,dates


def test_optimized_signal_short_circuit_matches_naive_and_has_real_positive():
    d,b,dates=frames();optimized,_=e.causal_signals({'T':d},b,dates,CFG);naive={}
    prepared=radar.indicators(d)
    for i in range(199,len(d)):
        date=d.index[i];r=radar.analyze('T',d.iloc[:i+1],CFG,b.loc[:date],str(date.date()),dates[dates<=date],prepared=prepared.iloc[:i+1],research_mode=True)
        if r['classification'] in ('Entry','Partial Entry'):naive.setdefault(dates[dates.searchsorted(date)+1],[]).append(('T',r))
    assert optimized==naive and sum(map(len,optimized.values()))>0


def test_future_mutation_cannot_change_past_eligible_signal():
    d,b,dates=frames();a,_=e.causal_signals({'T':d},b,dates,CFG);cut=dates[241]
    d.loc[d.index>dates[240],['Close','High']]*=3
    b.loc[b.index>dates[240],'Close']*=2
    z,_=e.causal_signals({'T':d},b,dates,CFG)
    assert {k:v for k,v in a.items() if k<=cut}=={k:v for k,v in z.items() if k<=cut}


def proxy_case():
    dates=pd.bdate_range('2026-01-01',periods=62)
    data={s:pd.DataFrame({'Close':np.linspace(100,110,62)},index=dates) for s in ['T','A','B','C','D']}
    universe=pd.DataFrame({'symbol':list(data),'sector':'same'});benchmark=pd.DataFrame({'Close':100.},index=dates)
    return data,universe,benchmark,dates


def test_sector_proxy_excludes_target_and_does_not_use_future_prices():
    data,u,b,dates=proxy_case();first=e.SectorProxy(data,u,dates,PLAN['sector_proxy']).excess('T',dates[60],b,60)
    data['T']['Close']*=2
    for frame in data.values():frame.loc[dates[61],'Close']=999999
    second=e.SectorProxy(data,u,dates,PLAN['sector_proxy']).excess('T',dates[60],b,60)
    assert first==pytest.approx(second) and first>0


def test_missing_sector_sessions_never_forward_filled():
    data,u,b,dates=proxy_case();data['A']=data['A'].drop(dates[20])
    assert e.SectorProxy(data,u,dates,PLAN['sector_proxy']).excess('T',dates[60],b,60) is None


def test_too_few_other_sector_peers_returns_unavailable():
    data,u,b,dates=proxy_case();del data['A'];del data['B']
    assert e.SectorProxy(data,u,dates,PLAN['sector_proxy']).excess('T',dates[60],b,60) is None


def execution(stop=96,target=120,opening=100):
    dates=pd.bdate_range('2026-01-01',periods=4)
    d=pd.DataFrame({'Open':[opening,100,100,100],'High':101.,'Low':99.,'Close':100.,'Volume':1000.},index=dates)
    d.attrs['quarantine']=[];b=d[['Close']]
    r={'date':'2025-12-31','technical_score':50,'scenario':{'invalidation':stop,'conditional_target':target},'_original_stop':96}
    return {'T':d},{dates[0]:[('T',r)]},b,dates


@pytest.mark.parametrize('stop,target,opening',[(96,120,100),(99.5,120,100),(96,120,110),(96,120,95)])
def test_research_baseline_simulator_exactly_matches_original(stop,target,opening):
    data,signals,b,dates=execution(stop,target,opening)
    original=portfolio_backtest(data,signals,b,dates,CFG);new=e.simulate(data,signals,b,dates,CFG)
    new.pop('maximum_aggregate_planned_risk_pct');assert original==new


def test_wider_stop_reduces_exposure_and_caps_planned_cash_risk():
    data,signals,b,dates=execution(stop=94)
    result=e.simulate(data,signals,b,dates,CFG,PLAN,risk_sized=True)
    assert result['trades_count']==1 and result['maximum_aggregate_planned_risk_pct']<=3
    t=result['trades'][0]
    assert t['planned_risk_cash']<=t['same_signal_baseline_risk_cash']+1e-8
    assert t['planned_risk_cash']<=t['equity_at_entry']*.005+1e-8


def test_overwide_stop_rejected_instead_of_increasing_risk():
    data,signals,b,dates=execution(stop=90,target=130)
    result=e.simulate(data,signals,b,dates,CFG,PLAN,risk_sized=True)
    assert not result['trades'] and result['skipped_orders']['execution_stop_distance_exceeds_cap']==1


def test_development_outcomes_ignore_later_test_price_changes():
    data,signals,b,dates=execution();development=dates[:2]
    first=e.simulate(data,signals,b,development,CFG)
    data['T'].loc[dates[2]:,'High']=1000
    data['T'].loc[dates[2]:,'Close']=1000
    assert e.simulate(data,signals,b,development,CFG)==first


def test_high_win_rate_and_tiny_sample_cannot_authorize_new_strategy():
    data,signals,b,dates=execution();base=e.add_metrics(e.simulate(data,signals,b,dates,CFG));candidate=copy.deepcopy(base)
    candidate.update(win_rate_pct=100,trades_count=3,expectancy_pct=1,portfolio_return_pct=3,daily_sharpe_annualized=4)
    p={**PLAN,'bootstrap_samples':20};result=e.select_on_development({'baseline':base,'test':candidate},{'test':[candidate,candidate]},p)
    assert result['selected_on_development_only'] is None and not result['adopted']
    assert not result['candidates']['test']['gates']['enough_development_trades']
    assert result['historical_holdout_was_previously_exposed']


@pytest.mark.parametrize('patch', [{'Close':np.nan},{'High':90},{'Volume':0},{'Open':np.inf}])
def test_bad_free_source_daily_row_not_accepted(patch):
    row={'Open':100,'High':101,'Low':99,'Close':100,'Volume':1000};row.update(patch)
    assert not valid_daily_row(row)[0]
