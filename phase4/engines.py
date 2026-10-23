"""Registered independent causal engines. Research signals NEVER drive radar.py."""
from __future__ import annotations
from collections import Counter
import copy
import numpy as np
import pandas as pd
from radar import indicators
from research import quality_audit, price_structure

ENGINES=('early_reversal','trend_pullback','breakout_retest')
ABLATIONS=('rs20_only','no_extension_guard','no_pattern_support')

def features(df, benchmark, sessions):
    d=indicators(df)
    grid=sessions[sessions<=d.index[-1]]
    c=df.Close.reindex(grid);b=benchmark.Close.reindex(grid)
    # A missing interior bar invalidates the entire synchronized return window.
    for n in (20,60,120):
        complete=c.notna().rolling(n+1,min_periods=n+1).sum().eq(n+1)&b.notna().rolling(n+1,min_periods=n+1).sum().eq(n+1)
        d[f'RS{n}']=(100*(c/c.shift(n)-b/b.shift(n))).where(complete).reindex(d.index)
    d['RS20_improving']=d.RS20>d.RS20.shift(5)
    d['gain5']=100*(d.Close/d.Close.shift(5)-1)
    d['extension_atr']=(d.Close-d.EMA20)/d.ATR14
    norm=d.ATR14/d.Close
    d['contraction']=norm.rolling(5).mean()<norm.shift(5).rolling(35).median()*.8
    up=d.Volume.where(d.Close.diff()>0,0).rolling(10).sum();down=d.Volume.where(d.Close.diff()<0,0).rolling(10).sum()
    d['demand']=(up>1.3*down)&(up>0)
    d['momentum']=(d.MACD-d.MACD_signal)>(d.MACD-d.MACD_signal).shift(1)
    d['volume_ratio']=d.Volume/d.Volume.shift().rolling(20,min_periods=20).mean().replace(0,np.nan)
    d['reclaim']=(d.Close>d.EMA20)&(d.Close.shift()<=d.EMA20.shift())
    d['above5']=d.Close>d.High.shift().rolling(5).max()
    d['touch20']=(d.Low<=d.EMA20+.5*d.ATR14).shift().rolling(5).max().eq(1)
    return d

def cheap_mask(d,engine,ablation,plan):
    common=(d.volume_ratio>=plan['volume_multiple'])&(d.Volume>0)&(d.Close>d.Open)&(d.ATR14>0)&(d.ATR14/d.Close*100<=plan['maximum_atr_pct'])&(np.arange(len(d))>=plan['minimum_history']-1)
    if ablation!='no_extension_guard':common&=(d.gain5<=plan['maximum_5_session_gain_pct'])&(d.extension_atr<=plan['maximum_extension_ema20_atr'])
    if engine=='early_reversal':
        rule=(d.reclaim|d.above5)&(d.RSI14>=40)&(d.RSI14>d.RSI14.shift())&d.momentum&d.RS20_improving
        if ablation!='rs20_only':rule&=d.RS60.gt(-10)&d.RS120.notna()
    elif engine=='trend_pullback':
        rule=(d.Close>d.EMA50)&(d.EMA50>d.EMA200)&(d.EMA50>d.EMA50.shift(10))&d.touch20&(d.Close>d.High.shift())&d.RSI14.between(45,70)&d.RS20.gt(0)
        if ablation!='rs20_only':rule&=d.RS60.gt(0)&d.RS120.ge(0)
    elif engine=='breakout_retest':
        rule=(d.Close>d.EMA50)&(d.Close>d.Close.shift())&d.RS20.gt(0)
        if ablation!='rs20_only':rule&=d.RS60.gt(0)&d.RS120.ge(0)
    elif engine=='simple_breakout20':rule=d.Close>d.prior_resistance20
    elif engine=='simple_ema50':rule=(d.Close>d.EMA50)&(d.Close.shift()<=d.EMA50.shift())
    else:raise ValueError(engine)
    return (common&rule).fillna(False)

def retest_level(d):
    last=d.iloc[-1]
    for i in range(len(d)-2,max(19,len(d)-12),-1):
        level=d.iloc[i].prior_resistance20
        if pd.notna(level) and d.Close.iloc[i]>level and abs(last.Low-level)<=.5*last.ATR14 and last.Close>level and last.Close>d.Close.iloc[-2] and d.Close.iloc[i+1:].min()>=.98*level:return float(level)
    return None

def scenario(d,structure,plan):
    last=d.iloc[-1];price=float(last.Close);atr=float(last.ATR14)
    major=sorted((z for z in structure['zones'] if z['low']>price and z['touches']>=plan['major_zone_minimum_touches']),key=lambda z:z['low'])
    high=float(d.High.iloc[-127:-1].max())
    target=float(major[0]['low']) if major else high
    support=structure['nearest_support'];level=float(support['low']) if support else float(last.prior_support20)
    stop=min(level-plan['support_buffer_atr']*atr,price-plan['stop_atr_floor']*atr)
    if not np.isfinite([price,stop,target]).all() or not 0<stop<price<target:return None,'invalid_levels'
    upside=100*(target/price-1);rr=(target-price)/(price-stop)
    if 100*(price-stop)/price>plan['maximum_stop_pct']:return None,'stop_over_cap'
    if upside<plan['minimum_upside_pct']:return None,'upside_below_10'
    if rr<plan['minimum_reward_risk']:return None,'reward_risk_below_2'
    return {'trigger':price,'invalidation':stop,'conditional_target':target,'upside_pct':upside,'reward_risk':rr,'target_source':'nearest_confirmed_major_zone' if major else 'prior_126_session_high'},None

def candidate(symbol,d,engine,ablation,plan,sessions,structure=None,quality=None):
    date=d.index[-1];last=d.iloc[-1]
    quality=quality or quality_audit(d,sessions[sessions<=date])
    if not quality['entry_eligible']:return None,'quarantined_or_zero_volume'
    # Current signal must actually be a calendar session; recent gaps are unsafe.
    grid=sessions[sessions<=date][-plan['minimum_history']:]
    if len(grid)!=plan['minimum_history'] or not grid.isin(d.index).all():return None,'incomplete_calendar_history'
    structure=structure or price_structure(d)
    if engine=='breakout_retest' and retest_level(d) is None:return None,'no_confirmed_retest'
    if ablation!='no_pattern_support':
        if engine=='early_reversal' and not (structure['confirmed_higher_lows'] and (bool(last.contraction) or bool(last.demand))):return None,'no_accumulation_support'
        if engine in ('trend_pullback','breakout_retest') and not (structure['confirmed_higher_lows'] or bool(last.contraction)):return None,'no_structure_support'
    levels,reason=scenario(d,structure,plan)
    if reason:return None,reason
    lo=float(d.Low.tail(126).min());hi=float(d.High.tail(126).max())
    context={k:float(last[k]) if pd.notna(last[k]) else None for k in ('EMA20','EMA50','EMA200','RSI14','MACD','MACD_signal','ATR14','RS20','RS60','RS120','volume_ratio','gain5','extension_atr')}
    return {'symbol':symbol,'date':str(date.date()),'close':float(last.Close),'classification':'Shadow Entry','engine':engine,'ablation':ablation,
            'technical_score':float(last.RS20) if pd.notna(last.RS20) else 0.,'scenario':levels,'_original_stop':levels['invalidation'],
            'data_quality':quality,'price_structure':structure,'features':context,
            'observations':{'price_confirmed':True,'volume_confirmed':True,'volume':float(last.Volume)},
            'supporting_fibonacci_only':{str(x):hi-(hi-lo)*x for x in (.382,.5,.618)},
            'reasons':[engine,'bullish_price_and_1.5x_volume','confirmed_target_10pct_RR2','verified_vendor_checks_only_not_exchange_certification'],
            'live_order_authorized':False},None

def generate(histories,benchmark,sessions,plan,latest_only=False):
    names=[e for e in ENGINES]+[e+'__'+a for e in ENGINES for a in ABLATIONS]+['simple_breakout20','simple_ema50']
    signals={n:{} for n in names};reject={n:Counter() for n in names};prepared={};last_records=[]
    for symbol,df in histories.items():
        if df.empty:continue
        d=features(df,benchmark,sessions);prepared[symbol]=d;cache={}
        for name in names:
            engine,_,ablation=name.partition('__');mask=cheap_mask(d,engine,ablation,plan)
            indexes=[len(d)-1] if latest_only and bool(mask.iloc[-1]) else ([] if latest_only else np.flatnonzero(mask.to_numpy()))
            for i in indexes:
                date=d.index[i];pos=sessions.searchsorted(date)
                if pos>=len(sessions) or sessions[pos]!=date:continue
                prefix=d.iloc[:i+1]
                if i not in cache:cache[i]=(quality_audit(prefix,sessions[:pos+1]),price_structure(prefix))
                quality,structure=cache[i]
                r,reason=candidate(symbol,prefix,engine,ablation,plan,sessions,structure,quality)
                if reason:reject[name][reason]+=1;continue
                if pos+1<len(sessions):signals[name].setdefault(sessions[pos+1],[]).append((symbol,copy.deepcopy(r)))
                if date==sessions[-1]:last_records.append(dict(r,variant=name))
    return signals,prepared,{n:dict(v) for n,v in reject.items()},last_records
