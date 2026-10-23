import copy,json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from phase4.tests.test_phase4 import bars,ready
from phase5.data import historical_window
from phase5.hypotheses import prepare,cheap_mask,pattern,specifications,CORE
from phase5.evaluate import wilson,walk_forward
from phase5.execution import simulate

PLAN=json.loads(Path('phase5/protocol.json').read_text())

def test_registered_cases_and_no_winner_selection():
    specs=specifications(PLAN)
    assert len(specs)==21 and all(sum(s['engine']==e for s in specs.values())==7 for e in CORE)
    assert PLAN['promotion'].startswith('No automatic promotion')
    assert PLAN['source_plan_sha']=='03675768ebbe0211d5a4349daac405c400f516ac'

def test_prepared_features_are_prefix_invariant():
    d=bars(300);b=d.copy()
    full=prepare(d,b,d.index);prefix=prepare(d.iloc[:240],b.iloc[:240],d.index[:240])
    pd.testing.assert_frame_equal(full.iloc[:240],prefix)
    changed=d.copy();changed.loc[changed.index[240:],'Close']*=2
    pd.testing.assert_frame_equal(full.iloc[:240],prepare(changed,b,d.index).iloc[:240])

def test_future_repair_cannot_retroactively_reject_signal():
    d=bars(260);d.attrs['price_repairs']=[{'date':str(d.index[-1].date())}]
    assert historical_window(d.iloc[:220],d.index[:220])['eligible']
    assert not historical_window(d,d.index)['eligible']
    assert not historical_window(d.drop(d.index[-30]),d.index)['eligible']

def test_latest_valid_bar_not_full_history_validity():
    d=bars();d.attrs['price_repairs']=[{'date':str(d.index[-20].date())}]
    assert d.Close.iloc[-1]>0 and not historical_window(d,d.index)['eligible']
    d=bars();d.iloc[-30,d.columns.get_loc('High')]=d.Close.iloc[-30]-1
    assert not historical_window(d,d.index)['eligible']

def test_failed_breakdown_requires_earlier_frozen_level_and_reclaim():
    d=bars();d.loc[d.index[-3],['Low','Close']]=[40,41]
    d.loc[d.index[-1],['Open','Low','High','Close']]=[55,53,59,58]
    p=prepare(d,d,d.index)
    assert pd.notna(p.failed_level20.iloc[-1])
    prefix=p.iloc[:-3];assert pd.isna(prefix.failed_level20.iloc[-1]) or prefix.failed_level20.iloc[-1]!=p.failed_level20.iloc[-1]

@pytest.mark.parametrize('engine',CORE)
def test_independent_pattern_positive_and_volume_block(engine):
    d,s=ready('early_reversal');d['hist_improving']=True;d['ROC20']=5.;d['failed_level20']=99.;d['base_ok30']=True
    spec=specifications(PLAN)[engine]
    if engine=='controlled_pullback':
        n=spec['native'];d.loc[d.index[-n-4],'reclaim']=True
        before=d.iloc[:-n-1];at=before.index[-3]
        d.loc[at:before.index[-1],['Close','High']]=[90,94]
        d.loc[d.index[-n-4],'Close']=90
        d.loc[d.index[-n-1:-1],['Low','EMA20','ATR14','Volume']]=[99,99,1,100]
        d.loc[d.index[-n-21:-n-1],'Volume']=1000
    assert cheap_mask(d,spec).iloc[-1]
    ok,reason,details=pattern(d,spec,s);assert ok,(engine,reason)
    d.loc[d.index[-1],'volume_ratio']=.5
    assert not cheap_mask(d,spec).iloc[-1]

def test_zero_trades_not_zero_percent_or_success():
    assert wilson(0,0)['lower_pct'] is None
    interval=wilson(2,5);assert interval['lower_pct']<40<interval['upper_pct']
    assert wilson(0,4)['upper_pct']>40

def test_purge_and_embargo_omit_previous_test_labels():
    ix=bars(450).index;folds=walk_forward(ix,ix[230:410],PLAN)
    for i,(train,purge,test) in enumerate(folds):
        assert len(purge)==20 and train[-1]<purge[0]<test[0]
        for _,_,oldtest in folds[:i]:
            prior_end=ix.get_loc(oldtest[-1]);excluded=ix[ix.get_loc(oldtest[0]):prior_end+21]
            assert not len(train.intersection(excluded))

def test_harmonized_execution_rejects_zero_volume_fill_and_accounts_costs():
    ix=pd.bdate_range('2026-01-01',periods=3);df=pd.DataFrame({'Open':[100]*3,'High':[101,113,101],'Low':[99]*3,'Close':[100]*3,'Volume':[0,100,100]},index=ix)
    record={'date':'2025-12-31','technical_score':1,'scenario':{'invalidation':95,'conditional_target':112},'_original_stop':95}
    limits={'stop_variants':{'maximum_stop_distance_pct':8,'maximum_equity_risk_per_trade_pct':.5,'maximum_aggregate_open_equity_risk_pct':3}}
    r=simulate({'X':df},{ix[0]:[('X',record)]},df,ix,{},limits,True)
    assert r['trades_count']==0 and r['skipped_orders']['invalid_or_zero_volume_execution_bar']==1
    df.loc[ix[0],'Volume']=100
    r=simulate({'X':df},{ix[0]:[('X',record)]},df,ix,{},limits,True)
    assert r['trades_count']==1 and 11<r['trades'][0]['net_return_pct']<12
    assert r['turnover_pct_initial_nav']>0 and r['mean_gross_exposure_pct']>0 and r['maximum_aggregate_planned_risk_pct']<=3

def test_missed_move_labels_do_not_invent_entry_and_preserve_prior_reasons(tmp_path):
    from phase5.missed import review
    d=bars(260);date=d.index[-21];d.loc[d.index[-1],'High']=d.loc[date,'Close']*1.12
    prepared=prepare(d,d,d.index)
    r=review({'X':d},{'X':prepared},d.index,{},tmp_path,start=str(date.date()),end=str(d.index[-1].date()))
    assert r['eligible_nonoverlapping_events']==1
    row=r['events'][0];assert row['threshold10'] and not row['guaranteed_entry_or_profit']
    assert 'volume_below1.5x' in row['engine_reasons']['failed_breakdown']
    assert not r['future_labels_used_for_entry']

def test_phase5_shadow_idempotent_and_future_only(monkeypatch,tmp_path):
    import phase5.shadow as shadow
    from datetime import datetime,timezone
    ix=pd.to_datetime(['2026-10-25','2026-10-26'])
    df=pd.DataFrame({'Open':[99,100],'High':[100,113],'Low':[98,99],'Close':[99,112],'Volume':[100,200]},index=ix)
    stage={'n':1}
    def daily(root):
        n=stage['n'];d=df.iloc[:n].copy()
        return {'X':d},d.copy().rename_axis('Date'),{}, {'run_id':str(n),'universe_count':254,'expected_session':str(ix[n-1].date()),'run_url':'https://example.test/'+str(n),'benchmark_quality':{'entry_eligible':True}}
    monkeypatch.setattr(shadow,'load_daily',daily)
    monkeypatch.setattr(shadow,'session_calendar',lambda now,cfg:(ix[:stage['n']],None))
    monkeypatch.setattr(shadow,'SectorProxy',lambda *a,**k:None)
    monkeypatch.setattr(shadow,'review',lambda *a,**k:None)
    candidate={'variant':'failed_breakdown','engine':'failed_breakdown','symbol':'X','date':'2026-10-25',
      'scenario':{'invalidation':95,'conditional_target':112},'hypothesis':{},'features':{},'entry_context':{}}
    # Benchmark integrity must explicitly pass.
    old_daily=daily
    def trusted(root):
        data,b,cfg,p=old_daily(root);b.attrs['historical_integrity_ok']=True
        return data,b,cfg,p
    monkeypatch.setattr(shadow,'load_daily',trusted)
    monkeypatch.setattr(shadow,'generate',lambda *a,**k:({}, {}, {}, [candidate], {}))
    now=datetime(2026,10,25,15,tzinfo=timezone.utc)
    shadow.update('unused',tmp_path,now);shadow.update('unused',tmp_path,now)
    ledger=json.loads((tmp_path/'ledger.json').read_text());assert len(ledger['observations'])==1
    assert ledger['observations'][0]['status']=='pending'
    stage['n']=2;result=shadow.update('unused',tmp_path,datetime(2026,10,26,15,tzinfo=timezone.utc))
    assert result['prospective_closed_trades']==1 and not result['adopted']
