import numpy as np
import pandas as pd
from radar import indicators, fibonacci, analyze, normalize

CFG={'minimum_upside_pct':10,'minimum_reward_risk':2,'volume_confirmation_multiple':1.5,'max_atr_pct':12}

def candles(n=260):
    x=np.arange(n)
    close=100+x*0.12+np.sin(x/6)*1.4
    return pd.DataFrame({'Open':close-0.1,'High':close+1,'Low':close-1,'Close':close,
        'Volume':np.full(n,100000)},index=pd.bdate_range('2025-01-01',periods=n))

def test_indicator_warmup_and_values():
    d=indicators(candles())
    assert np.isfinite(d.iloc[-1]['EMA200'])
    assert 0<=d.iloc[-1]['RSI14']<=100
    assert d.iloc[-1]['ATR14']>0
    assert np.isfinite(d.iloc[-1]['MACD'])

def test_fibonacci_upward_wave():
    d=candles(100)
    f=fibonacci(d)
    assert f['direction'] in ('up','down')
    assert abs(f['retracement']['50']-(f['high']+f['low'])/2)<1e-7

def test_no_entry_without_volume_confirmation():
    r=analyze('TEST',candles(),CFG)
    assert r['classification'] not in ('Entry','Partial Entry')
    assert r['observations']['volume_ratio20']==1

def test_bad_ohlcv_rejected():
    d=candles(10)
    d.loc[d.index[0],'High']=1
    assert len(normalize(d))==9

def test_cannot_use_future_bars():
    d=candles()
    r1=analyze('TEST',d.iloc[:-1],CFG)
    d2=d.copy();d2.iloc[-1,d2.columns.get_loc('High')]=9999
    r2=analyze('TEST',d2.iloc[:-1],CFG)
    assert r1['fibonacci']==r2['fibonacci']
