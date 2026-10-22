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
from research import quality_audit, price_structure, early_patterns, benchmark_audit, historical_research, update_ledger


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


def clean(value):
    """Strict JSON: never publish NaN or Infinity."""
    if isinstance(value, dict): return {k: clean(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, (np.bool_,)): return bool(value)
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (float, np.floating)): return round(float(value), 6) if math.isfinite(value) else None
    return value


def session_calendar(now, cfg):
    import exchange_calendars as xcals
    from zoneinfo import ZoneInfo
    local = now.astimezone(ZoneInfo('Asia/Riyadh'))
    cal = xcals.get_calendar('XSAU')
    # XSAU labels continuous-trading close at 15:00; include auction/last trade until 15:20.
    dates = cal.sessions_in_range(pd.Timestamp(local.date())-pd.Timedelta(days=cfg['lookback_calendar_days']+30), pd.Timestamp(local.date()))
    closed = set(cfg.get('extra_closed_dates', []))
    dates = pd.DatetimeIndex([d.tz_localize(None) if d.tzinfo else d for d in dates if str(d.date()) not in closed])
    if (local.hour, local.minute) < (15,20): dates = dates[dates.date < local.date()]
    if dates.empty: raise ValueError('No completed XSAU session; calendar update required')
    return dates, str(dates[-1].date())


def relative_strength(stock, benchmark, sessions, window):
    end = stock.index[-1]
    grid = sessions[sessions <= end][-(window+1):]
    if len(grid) != window+1 or grid[-1] != end:
        return {'value_pct_points': None, 'reason': 'insufficient calendar sessions'}
    pair = pd.concat([stock['Close'].reindex(grid).rename('stock'), benchmark['Close'].reindex(grid).rename('benchmark')], axis=1)
    if pair.isna().any().any() or (pair<=0).any().any():
        return {'value_pct_points': None, 'reason': 'missing synchronized stock or TASI sessions; no forward fill'}
    a,b = pair.iloc[0], pair.iloc[-1]
    return {'value_pct_points': float(100*((b['stock']/a['stock']-1)-(b['benchmark']/a['benchmark']-1))),
            'stock_return_pct':float(100*(b['stock']/a['stock']-1)),
            'tasi_return_pct':float(100*(b['benchmark']/a['benchmark']-1)),
            'start_date':str(grid[0].date()), 'end_date':str(grid[-1].date()), 'sessions':window, 'reason':None}


def analyze(symbol, df, config, benchmark=None, expected_session=None, sessions=None, prepared=None, research_mode=False):
    d = prepared if prepared is not None else indicators(df)
    last = d.iloc[-1]; prev = d.iloc[-2] if len(d)>1 else last
    price = float(last['Close']); date = str(d.index[-1].date())
    expected_session = expected_session or date
    sessions = pd.DatetimeIndex(sessions if sessions is not None else d.index)
    fresh = date == expected_session
    num = lambda x: float(x) if pd.notna(x) and np.isfinite(x) else None
    # Exclude current volume from the average used to confirm current volume.
    baseline = num(d['Volume'].shift(1).rolling(20,min_periods=20).mean().iloc[-1])
    vr = float(last['Volume'])/baseline if baseline and baseline>0 else None
    volume_confirmed = bool(vr is not None and vr >= config['volume_confirmation_multiple'] and last['Volume']>0)
    resistance = num(last['prior_resistance20']); support = num(last['prior_support20'])
    breakout = bool(resistance is not None and price>resistance)
    reclaim = bool(pd.notna(prev['EMA20']) and prev['Close']<=prev['EMA20'] and price>last['EMA20'])
    trend = bool(price>last['EMA20']>last['EMA50'] and price>last['EMA200'])
    contraction = bool(last['range5'] < last['range20']*0.45)
    higher_lows = bool(len(d)>=10 and d['Low'].iloc[-10:-5].min()<d['Low'].iloc[-5:].min())
    quality=quality_audit(df,sessions)
    structure=price_structure(d)
    patterns=early_patterns(d,structure)
    fib = fibonacci(d) if len(d)>=20 else {}
    atr = num(last['ATR14']); atr_pct = atr/price*100 if atr else None
    stop = max(support,price-2*atr) if support is not None and atr else None
    if stop is not None and not 0<stop<price: stop=None
    # Prior high is the first objective; use one 127.2% extension only after clearing it.
    prior_high = float(d['High'].iloc[:-1].tail(90).max()) if len(d)>1 else None
    target = prior_high if prior_high is not None and prior_high>price else None
    target_method = 'previous 90-session high' if target else None
    if target is None and fib.get('direction')=='up':
        candidate=fib['extension']['127.2']
        if price<candidate<=price*1.30: target=candidate;target_method='conditional 127.2% swing extension (maximum 30% upside)'
    if structure['structural_invalidation'] is not None:
        stop=structure['structural_invalidation']
    overhead=structure['nearest_resistance']
    if overhead and (target is None or overhead['low']<target):
        target=overhead['low'];target_method='nearest confirmed overhead pivot zone (conservative lower edge)'
    upside = (target/price-1)*100 if target else None
    rr = (target-price)/(price-stop) if target and stop else None
    required = ['EMA20','EMA50','EMA200','RSI14','MACD','MACD_signal','ATR14','prior_support20','prior_resistance20']
    missing = [x for x in required if num(last[x]) is None]
    rs = {}
    for n in (20,60):
        rs[str(n)] = relative_strength(d,benchmark,sessions,n) if benchmark is not None and not benchmark.empty else {'value_pct_points':None,'reason':'TASI benchmark unavailable'}
    if any(rs[str(n)]['value_pct_points'] is None for n in (20,60)): missing.append('synchronized_relative_strength')
    benchmark_fresh = bool(benchmark is not None and not benchmark.empty and str(benchmark.index[-1].date())==expected_session)
    confidence = 'high' if not missing and fresh and benchmark_fresh else 'medium' if len(d)>=60 else 'low'
    blockers=[]
    if not quality['entry_eligible']:blockers.append('unverified_or_suspicious_OHLCV')
    if not research_mode and benchmark is not None and not benchmark.attrs.get('entry_eligible',True):blockers.append('benchmark_quality_not_verified')
    if patterns['false_upside_breakout']:blockers.append('failed_upside_breakout')
    if not fresh: blockers.append('stale_price_data')
    if not benchmark_fresh: blockers.append('stale_or_missing_TASI')
    if missing or len(d)<config.get('minimum_entry_history_rows',200): blockers.append('insufficient_entry_indicators')
    if not (breakout or reclaim): blockers.append('price_not_confirmed')
    if not volume_confirmed: blockers.append('volume_not_confirmed')
    if not trend: blockers.append('trend_not_confirmed')
    if upside is None or upside < max(10,config['minimum_upside_pct']): blockers.append('upside_below_10pct_or_no_target')
    if rr is None or rr < max(2,config['minimum_reward_risk']): blockers.append('reward_risk_below_minimum_or_missing')
    if atr_pct is None or atr_pct>config['max_atr_pct']: blockers.append('volatility_or_missing_ATR')
    entry = not blockers
    classification = 'Entry' if entry and breakout else 'Partial Entry' if entry else 'Early Watch' if len(d)>=20 and (contraction or higher_lows or trend or breakout or reclaim or patterns['early_reversal_candidate'] or patterns['accumulation_candidate']) else 'Wait'
    score = 25*trend+15*breakout+8*reclaim+15*volume_confirmed+8*(last['MACD']>last['MACD_signal'])+7*(45<=last['RSI14']<=70)+5*contraction+5*higher_lows
    score += sum(6 for n in (20,60) if rs[str(n)]['value_pct_points'] is not None and rs[str(n)]['value_pct_points']>0)
    score+=5*patterns['accumulation_candidate']+5*patterns['early_reversal_candidate']+3*patterns['breakout_retest_holds']-10*patterns['false_upside_breakout']
    if not quality['entry_eligible'] or (not research_mode and benchmark is not None and not benchmark.attrs.get('entry_eligible',True)):confidence='low';score-=10
    if not fresh: score-=30
    if confidence=='low':score-=15
    obs={'breakout20_with_volume':breakout and volume_confirmed,'reclaim_ema20_with_volume':reclaim and volume_confirmed,
         'price_breakout20':breakout,'volume_confirmed':volume_confirmed,'trend_ema':trend,'range_contraction':contraction,'higher_lows':higher_lows,
         'volume':float(last['Volume']),'volume_avg20_prior':baseline,'volume_ratio20':vr,
         'rsi14':num(last['RSI14']),'macd':num(last['MACD']),'macd_signal':num(last['MACD_signal']),
         'macd_histogram':num(last['MACD']-last['MACD_signal']),'atr14':atr,
         'ema20':num(last['EMA20']),'ema50':num(last['EMA50']),'ema200':num(last['EMA200']),
         'support20':support,'resistance20':resistance,
         'relative_strength_20d_vs_tasi':rs['20']['value_pct_points'],'relative_strength_60d_vs_tasi':rs['60']['value_pct_points']}
    return clean({'symbol':symbol,'date':date,'last_bar':date,'close':price,'classification':classification,'technical_score':score,
        'data_fresh':fresh,'expected_session':expected_session,'confidence':confidence,'missing_indicators':missing,'entry_blockers':blockers,
        'observations':obs,'relative_strength':rs,'data_quality':quality,'price_structure':structure,'early_patterns':patterns,
        'nomination_reasons':patterns['evidence']+(['EMA_trend_confirmed'] if trend else [])+(['price_and_volume_confirmed'] if volume_confirmed and (breakout or reclaim) else []),
        'scenario':{'trigger':resistance,'reclaim_trigger':num(last['EMA20']),'trigger_rule':'daily close above resistance or EMA20 reclaim, with prior-20-volume multiple >= '+str(config['volume_confirmation_multiple']),
                    'invalidation':stop,'conditional_target':target,'target_method':target_method,'upside_pct':upside,'reward_risk':rr,
                    'forecast_window':'next 5–20 trading sessions; conditional, not a guaranteed return'},
        'fibonacci':fib,'bars':len(d),'first_bar':str(d.index[0].date()),'source':'Yahoo Finance/yfinance; unofficial adjusted daily prices'})


def normalize(raw, benchmark=False):
    raw=raw.copy()
    if isinstance(raw.columns,pd.MultiIndex):raw.columns=raw.columns.get_level_values(0)
    cols=['Close'] if benchmark else ['Open','High','Low','Close','Volume']
    if not all(x in raw.columns for x in cols):raise ValueError('missing '+','.join(cols)+' columns')
    d=raw[cols].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
    d.index=pd.to_datetime(d.index)
    if d.index.tz is not None:d.index=d.index.tz_localize(None)
    d.index=d.index.normalize()
    d=d[~d.index.duplicated(keep='last')].sort_index()
    mask=d['Close']>0
    if not benchmark:mask &= (d['High']>=d['Low'])&(d['High']>=d['Open'])&(d['High']>=d['Close'])&(d['Low']<=d['Open'])&(d['Low']<=d['Close'])&(d['Open']>0)&(d['Low']>0)&(d['Volume']>=0)
    valid=d[mask].copy()
    valid.attrs['normalization']={'source_rows':len(raw),'valid_rows':len(valid),'rejected_or_duplicate_rows':len(raw)-len(valid)}
    return valid


def restore_current_close(raw, metadata, expected):
    """Repair only a provider-null final close using its dated final-session quote."""
    from zoneinfo import ZoneInfo
    raw=raw.copy(); repairs=[]
    stamp=metadata.get('regularMarketTime');price=metadata.get('regularMarketPrice')
    try:
        stamp=pd.Timestamp(stamp,unit='s',tz='UTC') if isinstance(stamp,(int,float)) else pd.Timestamp(stamp)
        if stamp.tzinfo is None:return raw,repairs
        stamp=stamp.tz_convert(ZoneInfo('Asia/Riyadh'))
        if str(stamp.date())!=expected or metadata.get('exchangeTimezoneName')!='Asia/Riyadh':return raw,repairs
        if not ((10,0)<=(stamp.hour,stamp.minute)<=(15,20)) or not price or not math.isfinite(float(price)):return raw,repairs
        for i in raw.index:
            row=raw.loc[i]
            if str(i.date())==expected and pd.isna(row['Close']) and row['Volume']>0 and row['Low']<=price<=row['High']:
                raw.loc[i,'Close']=float(price)
                if 'Adj Close' in raw.columns:raw.loc[i,'Adj Close']=float(price)
                repairs.append({'date':expected,'field':'Close','source':'Yahoo regularMarketPrice','quote_timestamp':stamp.isoformat(),'value':float(price),'reason':'daily Close was null; quote date and OHLC range validated'})
    except (TypeError,ValueError,KeyError):pass
    return raw,repairs


def fetch_tasi_fallback(start,end):
    """Public Investing.com TASI instrument 11319, identified on its TASI history page."""
    import requests
    url='https://api.investing.com/api/financialdata/historical/11319'
    response=requests.get(url,params={'start-date':start,'end-date':end,'time-frame':'Daily','add-missing-rows':'false'},headers={'domain-id':'www'},timeout=25)
    response.raise_for_status();rows=response.json().get('data') or []
    if not rows:raise ValueError('Investing.com returned empty TASI history')
    d=pd.DataFrame({'Close':[float(r['last_closeRaw']) for r in rows]},index=pd.to_datetime([r['rowDateTimestamp'] for r in rows],utc=True).tz_localize(None))
    return normalize(d,True)


def merge_benchmark_sources(sources, errors):
    """Merge only observed closes; never synthesize/fill missing sessions."""
    merged=pd.DataFrame(columns=['Close'],index=pd.DatetimeIndex([]));used=[]
    for label,d in sources:
        if d is None or d.empty:continue
        d=normalize(d,True)
        overlap=merged.index.intersection(d.index)
        if len(overlap) and ((merged.loc[overlap,'Close']/d.loc[overlap,'Close']-1).abs()>0.001).any():
            errors.append(label+': source disagreement above 0.1%; rejected');continue
        merged=d.copy() if merged.empty else pd.concat([merged,d]);merged=merged[~merged.index.duplicated(keep='last')].sort_index()
        used.append(label)
    return merged,used


def fetch_yahoo(ticker,start,end,benchmark=False):
    import yfinance as yf
    import time
    last_error='no data'
    for attempt in range(3):
        try:
            # Explicit end is exclusive. Include the expected session, never today's incomplete bar.
            instrument=yf.Ticker(ticker)
            raw=instrument.history(start=start,end=end,interval='1d',auto_adjust=False,raise_errors=True,timeout=20)
            repairs=[]
            if not benchmark:
                expected=(pd.Timestamp(end)-pd.Timedelta(days=1)).date().isoformat()
                # Do not request metadata unless a final-session row actually has a null close.
                null_final=any(str(i.date())==expected and pd.isna(raw.loc[i,'Close']) for i in raw.index)
                if null_final:raw,repairs=restore_current_close(raw,instrument.history_metadata,expected)
                if 'Adj Close' in raw.columns:
                    ratio=raw['Adj Close']/raw['Close']
                    raw[['Open','High','Low','Close']]=raw[['Open','High','Low','Close']].mul(ratio,axis=0)
            d=normalize(raw,benchmark)
            d.attrs['price_repairs']=repairs
            if d.empty:raise ValueError('empty valid price history')
            return d
        except Exception as e:
            last_error=str(e)[:250]
            if attempt<2:time.sleep(2**attempt)
    raise ValueError(last_error)


def flatten(r):
    return {'symbol':r['symbol'],'name':r.get('name'),'sector':r.get('sector'),'classification':r['classification'],
        'technical_score':r['technical_score'],'close':r['close'],'price_date':r['date'],'data_fresh':r['data_fresh'],
        'confidence':r['confidence'],'bars':r['bars'],'missing_indicators':';'.join(r['missing_indicators']),
        'entry_blockers':';'.join(r['entry_blockers']),'nomination_reasons':';'.join(r.get('nomination_reasons',[])),
        'quality_status':r.get('data_quality',{}).get('status'),**r['observations'],**r['scenario']}


def rank_results(results):
    order={'Entry':3,'Partial Entry':2,'Early Watch':1,'Wait':0}
    return sorted(results,key=lambda r:(r['data_fresh'],order[r['classification']],r['technical_score'],r['symbol']),reverse=True)


def watch_report(results,failures,previous,symbols,expected):
    old={r['symbol']:r for r in (previous or {}).get('results',[])}
    current={r['symbol']:r for r in results}; failed={f['symbol']:f for f in failures}
    rows=[]
    for s in symbols:
        r=current.get(s);p=old.get(s);changes=[]
        if r:
            if not p:changes.append('first_observation')
            else:
                if r['classification']!=p.get('classification'):changes.append('classification_changed')
                if r['data_fresh']!=p.get('data_fresh'):changes.append('freshness_changed')
                if r['date']!=p.get('date'):
                    inv=p.get('scenario',{}).get('invalidation');trigger=p.get('scenario',{}).get('trigger')
                    if inv and p['close']>inv>=r['close']:changes.append('prior_invalidation_crossed')
                    if trigger and p['close']<=trigger<r['close']:changes.append('prior_trigger_crossed')
                    if abs(r['close']/p['close']-1)>=0.05:changes.append('price_move_at_least_5pct')
            rows.append({'symbol':s,'status':'analyzed','changes':changes,'previous_date':p.get('date') if p else None,
                         'previous_classification':p.get('classification') if p else None,'current':r})
        else:rows.append({'symbol':s,'status':'failed','changes':['data_failure'],'reason':failed.get(s,{}).get('reason','not in universe')})
    return {'expected_session':expected,'comparison_run_utc':(previous or {}).get('run_utc'),'stocks':rows,'note':'First observation is a baseline, not a newly triggered signal.'}


def validate_universe(universe,cfg):
    s=universe['symbol']
    if len(universe)!=cfg['expected_universe_count'] or s.duplicated().any():raise ValueError('Expected exactly 254 unique equity symbols')
    if not s.str.fullmatch(r'\d{4}').all() or (s.astype(int)>=9000).any():raise ValueError('Invalid or Nomu symbol')
    if s.astype(int).between(4330,4350).any() or s.astype(int).between(4700,4999).any() or universe['name'].str.contains('صندوق|ريت|REIT|ETF',case=False,regex=True).any():raise ValueError('Fund excluded from equity universe')
    if universe[['name','sector']].isna().any().any():raise ValueError('Missing universe metadata')


def run(args):
    import os,hashlib,collections
    cfg=json.loads(Path(args.config).read_text(encoding='utf-8'))
    universe=pd.read_csv(cfg['symbols_file'],dtype={'symbol':str});validate_universe(universe,cfg)
    if getattr(args,'limit',None):universe=universe.head(args.limit)
    out=Path(cfg['output_dir']);out.mkdir(parents=True,exist_ok=True)
    previous=None
    if (out/'latest.json').exists():
        try:previous=json.loads((out/'latest.json').read_text())
        except (ValueError,OSError):pass
    now=datetime.now(timezone.utc);sessions,expected=session_calendar(now,cfg)
    end=(pd.Timestamp(expected)+pd.Timedelta(days=1)).date().isoformat()
    start=(pd.Timestamp(expected)-pd.Timedelta(days=cfg['lookback_calendar_days'])).date().isoformat()
    bench=None;benchmark_errors=[]
    try:
        bench=fetch_yahoo(cfg['benchmark'],start,end,True);bench=bench[bench.index.isin(sessions)]
        if bench.empty:raise ValueError('No TASI closes on valid sessions')
        if len(bench)<61:benchmark_errors.append(f'insufficient TASI history: {len(bench)} closes; 61 synchronized sessions required for RS60')
    except Exception as e:benchmark_errors.append(str(e));bench=None
    live_benchmark=bench.copy() if bench is not None else None
    sources=[]
    for label,path in [('Investing.com TASI observed seed',Path(cfg.get('benchmark_seed','data/tasi_benchmark_seed.csv'))),('prior-run observed benchmark cache',out/'benchmark.csv')]:
        if path.exists():
            try:
                cached=pd.read_csv(path,index_col='Date',parse_dates=True)
                cached=normalize(cached,True);cached=cached[cached.index.isin(sessions)]
                sources.append((label,cached))
            except Exception as e:benchmark_errors.append(label+': '+str(e)[:200])
    sources.append(('Yahoo Finance ^TASI.SR current observations',bench))
    bench,benchmark_sources=merge_benchmark_sources(sources,benchmark_errors)
    if len(bench)<61 or str(bench.index[-1].date())!=expected or not sessions[-61:].isin(bench.index).all():
        try:
            alternative=fetch_tasi_fallback(start,end);alternative=alternative[alternative.index.isin(sessions)]
            bench,used=merge_benchmark_sources([('persisted observed TASI',bench),('Investing.com online TASI 11319',alternative)],benchmark_errors)
            benchmark_sources+=used[1:]
        except Exception as e:benchmark_errors.append('TASI fallback: '+str(e)[:250])
    benchmark_source=' + '.join(benchmark_sources)
    if not bench.empty:bench.to_csv(out/'benchmark.csv',index_label='Date')
    else:bench=None
    benchmark_quality=benchmark_audit(bench,live_benchmark,sessions,expected,benchmark_errors)
    if bench is not None:
        bench.attrs['entry_eligible']=benchmark_quality['entry_eligible']
        bench.attrs['historical_integrity_ok']=not benchmark_quality.get('suspicious_jump_dates') and not benchmark_quality.get('mismatch_dates') and not any('disagreement' in x for x in benchmark_errors)
    results=[];failures=[];histories={}
    for row in universe.itertuples(index=False):
        try:
            d=fetch_yahoo(str(row.symbol)+'.SR',start,end);d=d[d.index.isin(sessions)]
            if d.empty:raise ValueError('No valid OHLCV on completed sessions')
            qa=quality_audit(d,sessions);d.attrs['quarantine']=qa['quarantined_dates'];histories[row.symbol]=d
            r=analyze(row.symbol,d,cfg,bench,expected,sessions);r.update(name=row.name,sector=row.sector,price_repairs=d.attrs.get('price_repairs',[]));results.append(r)
        except Exception as e:failures.append({'symbol':row.symbol,'name':row.name,'reason':str(e)[:300]})
        print(f'{len(results)+len(failures)}/{len(universe)} {row.symbol}',flush=True)
    run_id=os.getenv('GITHUB_RUN_ID',now.strftime('%Y%m%dT%H%M%SZ'))
    attempt=os.getenv('GITHUB_RUN_ATTEMPT','1');run_url='https://github.com/'+os.getenv('GITHUB_REPOSITORY','saqerkhalel-gif/tasi-radar-3')+'/actions/runs/'+run_id if os.getenv('GITHUB_RUN_ID') else None
    counts=dict(collections.Counter(r['classification'] for r in results))
    counts={c:counts.get(c,0) for c in ['Entry','Partial Entry','Early Watch','Wait']}
    fresh=sum(r['data_fresh'] for r in results);bmdate=str(bench.index[-1].date()) if bench is not None else None
    report=clean({'schema_version':3,'run_utc':now.isoformat(),'completed_utc':datetime.now(timezone.utc).isoformat(),'run_id':run_id,'run_attempt':attempt,'run_url':run_url,'source_commit':os.getenv('GITHUB_SHA'),
        'expected_session':expected,'calendar':'exchange_calendars XSAU plus configured closures; post-close 15:20 Riyadh gate',
        'source':'Yahoo Finance via yfinance stocks; benchmark source separately disclosed; unofficial; no real-time claim',
        'universe_file':cfg['symbols_file'],'universe_sha256':hashlib.sha256(Path(cfg['symbols_file']).read_bytes()).hexdigest(),
        'universe_count':len(universe),'scanned_successfully':len(results),'failed_count':len(failures),
        'coverage_pct':round(100*len(results)/len(universe),2),'fresh_count':fresh,'fresh_coverage_pct':round(100*fresh/len(universe),2),
        'stale_count':len(results)-fresh,'classification_counts':counts,'price_dates':dict(collections.Counter(r['date'] for r in results)),
        'benchmark':{'symbol':cfg['benchmark'],'source':benchmark_source,'last_bar':bmdate,'fresh':bmdate==expected,'bars':len(bench) if bench is not None else 0,'errors':benchmark_errors},
        'limited_history_count':sum(bool(r['missing_indicators']) for r in results),'price_repaired_count':sum(bool(r.get('price_repairs')) for r in results),
        'relative_strength_coverage':{str(n):sum(r['relative_strength'][str(n)]['value_pct_points'] is not None for r in results) for n in (20,60)},
        'full_tasi_coverage_claim':False,'coverage_note':'Coverage denominator is the fixed 254-company equity snapshot, not an independently verified live constituent list.',
        'benchmark_quality':benchmark_quality,'quarantined_stock_count':sum(not r['data_quality']['entry_eligible'] for r in results),
        'ranking_note':'Technical candidates including Early Watch/Wait; conditional targets, not guaranteed profits; Entry requires fresh stock and TASI data, 200 bars, synchronized RS, price+volume, upside >=10%, reward/risk >=2.',
        'results':results,'failures':failures})
    print('Starting causal historical research',flush=True)
    backtest,missed=historical_research(histories,bench,sessions,cfg,analyze,indicators)
    for document in (backtest,missed):document.update(run_id=run_id,run_url=run_url,run_utc=report['run_utc'],expected_session=expected)
    prior_ledger=None
    if (out/'opportunity_ledger.json').exists():
        prior_ledger=json.loads((out/'opportunity_ledger.json').read_text())
    ledger=update_ledger(prior_ledger,results,histories,run_id);ledger.update(run_id=run_id,run_url=run_url,run_utc=report['run_utc'])
    prior_repairs=[]
    for old in (previous or {}).get('results',[]):
        for repair in old.get('price_repairs',[]):
            stamp=pd.Timestamp(repair['quote_timestamp'])
            prior_repairs.append({'symbol':old['symbol'],'repair_date':repair['date'],
                'quote_date_matches':str(stamp.date())==repair['date'],
                'quote_in_session':(10,0)<=(stamp.hour,stamp.minute)<=(15,20),
                'positive_value':float(repair['value'])>0,'independently_verified':False})
    quality_report={'run_id':run_id,'run_url':run_url,'run_utc':report['run_utc'],'benchmark':benchmark_quality,
        'previous_run_repair_review':{'run_id':(previous or {}).get('run_id'),'recorded_repaired_stock_count':sum(bool(r.get('price_repairs')) for r in (previous or {}).get('results',[])),
        'repair_records_reviewed':len(prior_repairs),'same_vendor_timestamp_checks_passed':sum(x['quote_date_matches'] and x['quote_in_session'] and x['positive_value'] for x in prior_repairs),
        'records':prior_repairs,'independently_validated_count':0,'disposition':'Same-vendor quote/range checks do not independently verify exchange closes. Quarantine on all affected dates.'},
        'stocks':[{'symbol':r['symbol'],**r['data_quality']} for r in results],
        'quarantined_stock_count':report['quarantined_stock_count'],'failed_fetches':failures}
    report['research_summary']={'backtest_trades':backtest['full_period']['trades_count'],'missed_10pct_excursions':missed['missed_count'],'detected_10pct_excursions':missed['detected_count']}
    ranked=rank_results(results)[:20]
    top={'run_utc':report['run_utc'],'run_url':run_url,'expected_session':expected,'ranking_note':report['ranking_note'],'count':len(ranked),'results':ranked}
    watch=watch_report(results,failures,previous,cfg['watch_symbols'],expected);watch.update(run_utc=report['run_utc'],run_url=run_url)
    dump=lambda p,x:p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    for name,doc in [('backtest.json',backtest),('missed_opportunities.json',missed),('opportunity_ledger.json',ledger),('quality_report.json',quality_report)]:dump(out/name,doc)
    pd.DataFrame(backtest['full_period']['trades']).to_csv(out/'backtest_trades.csv',index=False)
    pd.DataFrame(backtest['full_period']['equity_curve']).to_csv(out/'backtest_equity.csv',index=False)
    pd.DataFrame(missed['missed']).to_csv(out/'missed_opportunities.csv',index=False)
    # Input snapshots are artifact-only to avoid growing Git history with every OHLCV download.
    inputs=Path('research_inputs');inputs.mkdir(exist_ok=True)
    for symbol,df in histories.items():df.to_csv(inputs/(symbol+'.csv.gz'),compression='gzip',index_label='Date')
    dump(inputs/'quarantine.json',{symbol:df.attrs.get('quarantine',[]) for symbol,df in histories.items()})
    if bench is not None:bench.to_csv(inputs/'benchmark.csv',index_label='Date')
    dump(inputs/'config.json',cfg)
    dump(inputs/'stock_metadata.json',{symbol:df.attrs for symbol,df in histories.items()})
    dump(inputs/'benchmark_metadata.json',bench.attrs if bench is not None else {})
    dump(out/'latest.json',report);dump(out/'top20.json',top);dump(out/'watchlist.json',watch)
    columns=list(flatten(results[0])) if results else ['symbol','name','classification','price_date']
    pd.DataFrame([flatten(r) for r in results],columns=columns).to_csv(out/'latest.csv',index=False)
    pd.DataFrame([flatten(r) for r in ranked],columns=columns).to_csv(out/'top20.csv',index=False)
    archive=out/'history'/f'{run_id}_{attempt}';archive.mkdir(parents=True,exist_ok=True)
    for name in ('latest.json','latest.csv','top20.json','top20.csv','watchlist.json','backtest.json','backtest_trades.csv','backtest_equity.csv','missed_opportunities.json','missed_opportunities.csv','opportunity_ledger.json','quality_report.json','benchmark.csv'):
        (archive/name).write_bytes((out/name).read_bytes())
    dump(out/'manifest.json',{'run_url':run_url,'run_id':run_id,'run_utc':report['run_utc'],'completed_utc':report['completed_utc'],'expected_session':expected,'classification_counts':counts,'analyzed':len(results),'failed':len(failures),'fresh':fresh,'history_path':str(archive),'research_files':['backtest.json','quality_report.json','missed_opportunities.json','opportunity_ledger.json'],'input_snapshot_location':'GitHub run artifact research_inputs/ (90 days)'})
    print(json.dumps({k:report[k] for k in ['universe_count','scanned_successfully','failed_count','coverage_pct','fresh_count','stale_count','classification_counts','benchmark','relative_strength_coverage']},ensure_ascii=False),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default='config.json');p.add_argument('--limit',type=int)
    run(p.parse_args())
