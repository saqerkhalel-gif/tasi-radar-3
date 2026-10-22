import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
import radar

CFG=json.loads(Path('config.json').read_text())

def candles(n=260):
    x=np.arange(n);c=100+x*.12+np.sin(x/6)*1.4
    return pd.DataFrame({'Open':c-.1,'High':c+1,'Low':c-1,'Close':c,'Volume':np.full(n,100000)},index=pd.bdate_range('2025-01-01',periods=n))

def test_indicators():
    r=radar.indicators(candles()).iloc[-1]
    assert np.isfinite(r['EMA200']) and 0<=r['RSI14']<=100 and r['ATR14']>0

def test_bad_ohlcv_rejected():
    d=candles(10);d.iloc[0,d.columns.get_loc('High')]=1
    assert len(radar.normalize(d))==9

def test_benchmark_requires_close_only():
    d=candles()[['Close']]
    assert len(radar.normalize(d,benchmark=True))==260

def test_no_future_data_leak():
    d=candles();a=radar.analyze('TEST',d.iloc[:-1],CFG)
    d.iloc[-1,d.columns.get_loc('High')]=9999
    assert radar.analyze('TEST',d.iloc[:-1],CFG)==a

def test_rs_exact_20_and_60_sessions():
    dates=pd.bdate_range('2025-01-01',periods=61)
    s=pd.DataFrame({'Close':np.linspace(100,120,61)},index=dates)
    b=pd.DataFrame({'Close':np.linspace(100,110,61)},index=dates)
    r=radar.relative_strength(s,b,dates,60)
    assert r['value_pct_points']==pytest.approx(10)
    assert radar.relative_strength(s,b,dates,20)['start_date']==str(dates[-21].date())

def test_rs_never_fills_missing_sessions():
    d=candles();b=d.drop(d.index[-5])
    r=radar.relative_strength(d,b,d.index,20)
    assert r['value_pct_points'] is None and 'no forward fill' in r['reason']

def test_calendar_weekend_preclose_and_holiday():
    _,date=radar.session_calendar(datetime(2026,10,23,12,tzinfo=timezone.utc),CFG)
    assert date=='2026-10-22'
    _,date=radar.session_calendar(datetime(2026,10,22,12,19,tzinfo=timezone.utc),CFG)
    assert date=='2026-10-21'
    _,date=radar.session_calendar(datetime(2026,9,23,17,tzinfo=timezone.utc),CFG)
    assert date=='2026-09-22'

def breakout():
    d=candles();d.iloc[-1]=[d.iloc[-2]['Close'],d.iloc[-2]['High']+3,d.iloc[-2]['Close']-.5,d.iloc[-2]['High']+2,500000]
    return d

def test_stale_cannot_enter_even_with_loose_reward_filter():
    d=breakout();cfg={**CFG,'minimum_upside_pct':0,'minimum_reward_risk':0}
    r=radar.analyze('TEST',d,cfg,d,expected_session='2030-01-01')
    assert r['classification'] not in ('Entry','Partial Entry') and 'stale_price_data' in r['entry_blockers']

def test_missing_tasi_blocks_entry():
    r=radar.analyze('TEST',breakout(),CFG)
    assert r['classification'] not in ('Entry','Partial Entry') and 'stale_or_missing_TASI' in r['entry_blockers']

@pytest.mark.parametrize('n',[1,4,41,104,150,199])
def test_new_listings_partial_analysis_is_valid_json_and_never_entry(n):
    d=candles(n);r=radar.analyze('TEST',d,CFG,d)
    json.dumps(r,allow_nan=False)
    assert r['bars']==n and r['missing_indicators'] and r['classification'] not in ('Entry','Partial Entry')
    if n<60:assert r['confidence']=='low'

def test_volume_average_excludes_current_session():
    d=breakout();r=radar.analyze('TEST',d,CFG,d)
    assert r['observations']['volume_ratio20']==5

def test_no_volume_no_entry():
    d=breakout();d.iloc[-1,d.columns.get_loc('Volume')]=100000
    r=radar.analyze('TEST',d,CFG,d)
    assert not r['observations']['volume_confirmed'] and 'volume_not_confirmed' in r['entry_blockers']

def test_rs_missing_does_not_become_zero():
    d=candles();r=radar.analyze('TEST',d,CFG,d.drop(d.index[-5]))
    assert r['relative_strength']['20']['value_pct_points'] is None

def test_universe_and_fixed_count():
    u=pd.read_csv(CFG['symbols_file'],dtype={'symbol':str});radar.validate_universe(u,CFG)
    with pytest.raises(ValueError):radar.validate_universe(pd.concat([u.iloc[:-1],u.iloc[:1]]),CFG)
    u.loc[0,'symbol']='9557'
    with pytest.raises(ValueError):radar.validate_universe(u,CFG)

def test_watchlist_meaningful_change_and_baseline():
    d=candles();r=radar.analyze('7200',d,CFG,d)
    w=radar.watch_report([r],[],None,['7200'],r['date'])
    assert w['stocks'][0]['changes']==['first_observation']
    w=radar.watch_report([r],[],{'results':[r]},['7200'],r['date'])
    assert not w['stocks'][0]['changes']

def test_end_date_is_exclusive_and_all_outputs(monkeypatch,tmp_path):
    # Deterministic end-to-end scan with real calendar; includes stale, short, failed and full histories.
    now=datetime.now(timezone.utc);sessions,expected=radar.session_calendar(now,CFG)
    dates=sessions[-260:];d=candles(len(dates));d.index=dates
    calls=[]
    def fetch(ticker,start,end,benchmark=False):
        calls.append(end)
        if ticker=='1010.SR':raise ValueError('test source failure')
        if ticker=='1020.SR':return d.iloc[-4:]
        if ticker=='1030.SR':return d.iloc[:-1]
        return d[['Close']] if benchmark else d
    monkeypatch.setattr(radar,'fetch_yahoo',fetch)
    cfg={**CFG,'output_dir':str(tmp_path/'output')};cf=tmp_path/'config.json';cf.write_text(json.dumps(cfg))
    r=radar.run(SimpleNamespace(config=str(cf),limit=None))
    assert r['scanned_successfully']==253 and r['failed_count']==1 and r['stale_count']==1
    assert set(calls)=={(pd.Timestamp(expected)+pd.Timedelta(days=1)).date().isoformat()}
    for name in ['latest.json','top20.json','watchlist.json','manifest.json','latest.csv','top20.csv']:assert (tmp_path/'output'/name).exists()
    assert len(json.loads((tmp_path/'output/top20.json').read_text())['results'])==20
    from scripts.verify_output import verify
    verify(tmp_path/'output')

def test_all_entry_gates_for_every_classification():
    d=breakout();r=radar.analyze('TEST',d,CFG,d)
    # Any future tuning must preserve these independent gates.
    if r['classification'] in ('Entry','Partial Entry'):
        assert r['data_fresh'] and not r['missing_indicators'] and not r['entry_blockers']
        assert r['scenario']['upside_pct']>=10 and r['scenario']['reward_risk']>=2
        assert r['observations']['volume_confirmed']

def test_flatten_and_ranking_are_deterministic():
    d=candles();r=radar.analyze('A',d,CFG,d);r.update(name='A',sector='test')
    assert radar.flatten(r)['price_date']==r['last_bar']
    assert radar.rank_results([r,r])==[r,r]

def test_confirmed_entry_and_each_reward_safety_gate(monkeypatch):
    d=candles();d['Close']=120.;d['Open']=119.;d['High']=121.;d['Low']=118.;d.iloc[-70,d.columns.get_loc('High')]=150.
    d.iloc[-1,d.columns.get_loc('Volume')]=500000.
    original=radar.indicators
    def forced(x):
        v=original(x)
        for k,val in {'EMA20':110.,'EMA50':105.,'EMA200':100.,'RSI14':60.,'MACD':2.,'MACD_signal':1.,'ATR14':2.,'prior_support20':112.,'prior_resistance20':118.}.items():v[k]=val
        return v
    monkeypatch.setattr(radar,'indicators',forced)
    r=radar.analyze('TEST',d,CFG,d)
    assert r['classification']=='Entry' and not r['entry_blockers']
    r=radar.analyze('TEST',d,{**CFG,'minimum_reward_risk':100},d)
    assert r['classification']=='Early Watch'
    d['High']=121.
    r=radar.analyze('TEST',d,CFG,d)
    assert r['classification'] not in ('Entry','Partial Entry') and 'upside_below_10pct_or_no_target' in r['entry_blockers']

def test_schedule_is_sunday_thursday_afterclose_before_report():
    from zoneinfo import ZoneInfo
    text=Path('.github/workflows/radar.yml').read_text()
    assert "cron: '35 14 * * 0-4'" in text
    assert 'python -m pytest -q' in text and 'unittest discover' not in text
    assert 'retention-days: 90' in text and 'contents: write' in text
    for n in range(7):
        utc=datetime(2026,10,18+n,14,35,tzinfo=timezone.utc)
        local=utc.astimezone(ZoneInfo('Asia/Riyadh'))
        assert (local.hour,local.minute)==(17,35)

def test_null_close_only_uses_dated_quote_within_range():
    d=candles(4);i=d.index[-1];d.loc[i,'Close']=np.nan
    metadata={'regularMarketTime':pd.Timestamp(str(i.date())+' 15:19:59',tz='Asia/Riyadh'),'regularMarketPrice':float(d.loc[i,'Open']),'exchangeTimezoneName':'Asia/Riyadh'}
    fixed,repairs=radar.restore_current_close(d,metadata,str(i.date()))
    assert fixed.loc[i,'Close']==d.loc[i,'Open'] and len(repairs)==1
    for m in [{**metadata,'regularMarketPrice':10000},{**metadata,'regularMarketTime':metadata['regularMarketTime']-pd.Timedelta(days=1)}]:
        fixed,repairs=radar.restore_current_close(d,m,str(i.date()))
        assert pd.isna(fixed.loc[i,'Close']) and not repairs

def test_tasi_fallback_parses_numeric_close_and_date(monkeypatch):
    import requests
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'data':[{'rowDateTimestamp':'2026-10-22T00:00:00Z','last_closeRaw':'9695.86'}]}
    monkeypatch.setattr(requests,'get',lambda *a,**k:Response())
    d=radar.fetch_tasi_fallback('2026-01-01','2026-10-23')
    assert d.iloc[0]['Close']==9695.86 and str(d.index[0].date())=='2026-10-22'
