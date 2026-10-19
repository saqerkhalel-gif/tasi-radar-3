"""TASI 3.0: free-data, auditable end-of-day research scanner.
Not financial advice. No orders. No claim of full TASI coverage.
"""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy().sort_index()
    c, h, l, v = (d[x].astype(float) for x in ('Close','High','Low','Volume'))
    for n in (20,50,200):
        d[f'EMA{n}'] = c.ewm(span=n, adjust=False, min_periods=n).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0,np.nan)
    d['RSI14'] = (100 - 100/(1+rs)).where(loss.ne(0),100)
    macd = c.ewm(span=12,adjust=False,min_periods=12).mean()-c.ewm(span=26,adjust=False,min_periods=26).mean()
    d['MACD'] = macd
    d['MACD_signal'] = macd.ewm(span=9,adjust=False,min_periods=9).mean()
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    d['ATR14'] = tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    d['volume_avg20'] = v.rolling(20,min_periods=20).mean()
    d['prior_resistance20'] = h.shift(1).rolling(20,min_periods=20).max()
    d['prior_support20'] = l.shift(1).rolling(20,min_periods=20).min()
    d['range5'] = (h.rolling(5).max()-l.rolling(5).min())/c
    d['range20'] = (h.rolling(20).max()-l.rolling(20).min())/c
    return d


def fibonacci(df: pd.DataFrame, window: int=90) -> dict:
    """Chronological pivot pair: most recent extrema within lookback; no future candles."""
    recent = df.tail(window)
    hi_i, lo_i = recent['High'].idxmax(), recent['Low'].idxmin()
    high, low = float(recent.loc[hi_i,'High']), float(recent.loc[lo_i,'Low'])
    span = high-low
    if span <= 0: return {}
    up = lo_i < hi_i
    if up:
        ret = {str(k):high-span*k/100 for k in (38.2,50,61.8)}
        ext = {'127.2':low+span*1.272,'161.8':low+span*1.618}
    else:
        ret = {str(k):low+span*k/100 for k in (38.2,50,61.8)}
        ext = {'127.2':high-span*1.272,'161.8':high-span*1.618}
    return {'direction':'up' if up else 'down', 'high':high,'high_date':str(hi_i.date()),
            'low':low,'low_date':str(lo_i.date()),'retracement':ret,'extension':ext,
            'method':'chronological 90-session extrema; heuristic pivots, not manually validated'}


def analyze(symbol: str, df: pd.DataFrame, config: dict, benchmark: pd.DataFrame|None=None) -> dict:
    d = indicators(df)
    latest = d.iloc[-1]
    prev = d.iloc[-2]
    date = str(d.index[-1].date())
    price = float(latest['Close'])
    vol_ratio = float(latest['Volume']/latest['volume_avg20']) if latest['volume_avg20']>0 else None
    breakout = bool(price>latest['prior_resistance20'] and vol_ratio is not None and vol_ratio>=config['volume_confirmation_multiple'])
    trend = bool(price>latest['EMA20']>latest['EMA50'] and price>latest['EMA200'])
    reclaim = bool(prev['Close']<prev['EMA20'] and price>latest['EMA20'] and vol_ratio is not None and vol_ratio>=1.2)
    contraction = bool(latest['range5'] < latest['range20']*0.45)
    higher_lows = bool(d['Low'].iloc[-10:-5].min() < d['Low'].iloc[-5:].min())
    fib = fibonacci(d)
    # Target is conditional: previous 90-day high / upside extension, whichever is higher.
    targets = [float(d['High'].tail(90).max())]
    if fib and fib['direction']=='up': targets += [float(fib['extension']['127.2']),float(fib['extension']['161.8'])]
    target = max(targets)
    stop = float(min(latest['prior_support20'],price-2*latest['ATR14']))
    risk = price-stop
    upside_pct = (target/price-1)*100
    rr = (target-price)/risk if risk>0 else 0
    atr_pct = float(latest['ATR14']/price*100)
    relative_strength_20d = None
    if benchmark is not None and len(benchmark)>21:
        aligned = benchmark['Close'].reindex(d.index).ffill()
        if pd.notna(aligned.iloc[-21]) and aligned.iloc[-21]>0:
            relative_strength_20d = float((price/d['Close'].iloc[-21]-1)-(aligned.iloc[-1]/aligned.iloc[-21]-1))
    # Entries require independent price + volume confirmation and plausible reward.
    entry_ok = bool((breakout or reclaim) and trend and upside_pct>=config['minimum_upside_pct']
                    and rr>=config['minimum_reward_risk'] and atr_pct<=config['max_atr_pct'])
    classification = 'Entry' if entry_ok and breakout else 'Partial Entry' if entry_ok else 'Early Watch' if (contraction or higher_lows or trend) else 'Wait'
    return {'symbol':symbol,'date':date,'close':round(price,3),'classification':classification,
        'observations':{'breakout20_with_volume':breakout,'reclaim_ema20_with_volume':reclaim,
            'trend_ema':trend,'range_contraction':contraction,'higher_lows':higher_lows,
            'volume_ratio20':round(vol_ratio,3) if vol_ratio is not None else None,
            'rsi14':round(float(latest['RSI14']),2),'macd':round(float(latest['MACD']),4),
            'macd_signal':round(float(latest['MACD_signal']),4),'atr14':round(float(latest['ATR14']),3),
            'ema20':round(float(latest['EMA20']),3),'ema50':round(float(latest['EMA50']),3),
            'ema200':round(float(latest['EMA200']),3),
            'relative_strength_20d_vs_tasi':relative_strength_20d},
        'scenario':{'trigger':round(float(latest['prior_resistance20']),3),
            'invalidation':round(stop,3),'conditional_target':round(target,3),
            'upside_pct':round(upside_pct,2),'reward_risk':round(rr,2),
            'note':'Projected technical scenario, not a forecast or guaranteed return'},
        'fibonacci':fib,'volume_profile':'unavailable: daily OHLCV lacks intraday price-at-volume',
        'elliott_wave':'not scored: low-confidence discretionary hypothesis'}


def normalize(raw:pd.DataFrame) -> pd.DataFrame:
    if isinstance(raw.columns,pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    cols=['Open','High','Low','Close','Volume']
    if not all(c in raw.columns for c in cols): raise ValueError('missing OHLCV columns')
    d=raw[cols].copy().dropna()
    d.index=pd.to_datetime(d.index).tz_localize(None) if d.index.tz is not None else pd.to_datetime(d.index)
    d=d[~d.index.duplicated(keep='last')].sort_index()
    d=d[(d['High']>=d['Low']) & (d['High']>=d['Open']) & (d['High']>=d['Close']) &
        (d['Low']<=d['Open']) & (d['Low']<=d['Close']) & (d['Close']>0) & (d['Volume']>=0)]
    return d


def fetch_yahoo(ticker:str, start:str) -> pd.DataFrame:
    import yfinance as yf
    return normalize(yf.download(ticker,start=start,auto_adjust=True,progress=False,threads=False,timeout=20))


def run(args):
    cfg=json.loads(Path(args.config).read_text(encoding='utf-8'))
    universe=pd.read_csv(cfg['symbols_file'],dtype={'symbol':str})
    universe=universe.drop_duplicates('symbol')
    if args.limit: universe=universe.head(args.limit)
    out=Path(cfg['output_dir']);out.mkdir(parents=True,exist_ok=True)
    start=(datetime.now(timezone.utc)-timedelta(days=cfg['lookback_calendar_days'])).date().isoformat()
    results=[]; failures=[]; histories={}
    try: bench=fetch_yahoo(cfg['benchmark'],start)
    except Exception as e: bench=None; failures.append({'symbol':cfg['benchmark'],'reason':str(e)[:200]})
    for row in universe.itertuples(index=False):
        symbol=str(row.symbol)
        try:
            d=fetch_yahoo(f'{symbol}.SR',start)
            if len(d)<cfg['minimum_history_rows']: raise ValueError(f'insufficient bars {len(d)}')
            r=analyze(symbol,d,cfg,bench)
            r['name']=row.name; r['sector']=row.sector
            r['data_source']='Yahoo Finance via yfinance; adjusted daily OHLCV (unofficial)'
            r['bars']=len(d);r['first_bar']=str(d.index[0].date());r['last_bar']=str(d.index[-1].date())
            results.append(r)
            histories[symbol]=d[['Close','Volume']]
        except Exception as e:
            failures.append({'symbol':symbol,'reason':str(e)[:200]})
    now=datetime.now(timezone.utc).isoformat()
    report={'run_utc':now,'source':'Yahoo Finance via yfinance; free/unofficial; validation against Saudi Exchange pending',
        'universe_file':cfg['symbols_file'],'universe_count':len(universe),
        'scanned_successfully':len(results),'failed_count':len(failures),
        'coverage_pct':round(100*len(results)/len(universe),2) if len(universe) else 0,
        'full_tasi_coverage_claim':False,
        'warning':'The included symbol list is a SMALL STARTER SAMPLE, not the complete TASI universe. No real-time claims.',
        'results':results,'failures':failures}
    (out/'latest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    # Date-stamped archive: no overwriting previous runs
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (out/f'run_{stamp}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    pd.DataFrame([{'symbol':r['symbol'],'date':r['date'],'classification':r['classification'],
       'close':r['close'],'upside_pct':r['scenario']['upside_pct'],'reward_risk':r['scenario']['reward_risk']} for r in results],
       columns=['symbol','date','classification','close','upside_pct','reward_risk']).to_csv(out/'latest.csv',index=False)
    print(f"VERIFIED SCAN {len(results)}/{len(universe)} ({report['coverage_pct']}% of supplied sample); failures={len(failures)}")
    for r in results:
        if r['classification'] in ('Entry','Partial Entry'):print('SIGNAL',r['symbol'],r['classification'],r['date'])
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default='config.json');p.add_argument('--limit',type=int)
    run(p.parse_args())
