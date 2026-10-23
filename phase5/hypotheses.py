"""Three registered independent reversal hypotheses, causal prefix only."""
from collections import Counter
import copy
import numpy as np
import pandas as pd
from phase4.engines import features,scenario
from research import price_structure
from phase5.data import historical_window

CORE=('failed_breakdown','base_contraction','controlled_pullback')

def specifications(plan):
    specs={}
    for engine in CORE:
        native='support_lookback' if engine=='failed_breakdown' else ('base_sessions' if engine=='base_contraction' else 'pullback_sessions')
        neighbors=plan[engine]['support_neighborhood' if engine=='failed_breakdown' else 'length_neighborhood']
        base={'engine':engine,'native':plan[engine][native],'volume':plan['volume_multiple'],'conditioning':None}
        specs[engine]=base
        for value in neighbors:specs[engine+'__native_'+str(value)]={**base,'native':value}
        for value in (1.25,2.):specs[engine+'__volume_'+str(value)]={**base,'volume':value}
        for cond in ('market','sector'):specs[engine+'__'+cond]={**base,'conditioning':cond}
    return specs

def prepare(df,benchmark,sessions):
    d=features(df,benchmark,sessions);d['ROC10']=100*(d.Close/d.Close.shift(10)-1);d['ROC20']=100*(d.Close/d.Close.shift(20)-1)
    d['hist_improving']=(d.MACD-d.MACD_signal)>(d.MACD-d.MACD_signal).shift()
    for n in (10,20,30):
        support=d.Low.shift().rolling(n).min();failed=(d.Low<support)&(d.Close<support);frozen=support.where(failed);answer=pd.Series(np.nan,index=d.index)
        for lag in (3,2,1):answer=answer.where(~(frozen.shift(lag).notna()&(d.Close>frozen.shift(lag))),frozen.shift(lag))
        d[f'failed_level{n}']=answer
    norm=d.ATR14/d.Close
    for n in (20,30,40):
        low=d.Low.shift().rolling(n).min();high=d.High.shift().rolling(n).max()
        near=norm.shift().rolling(10).mean();older=norm.shift(11).rolling(n-10).mean()
        near_range=d.High.shift().rolling(10).max()-d.Low.shift().rolling(10).min()
        older_range=d.High.shift(11).rolling(n-10).max()-d.Low.shift(11).rolling(n-10).min()
        d[f'base_ok{n}']=((high/low-1)*100<=20)&(near<=.8*older)&(near_range<=.8*older_range)
    return d

def common_mask(d,volume=1.5):
    return ((d.volume_ratio>=volume)&(d.Volume>0)&(d.Close>d.Open)&(d.ATR14>0)&(d.ATR14/d.Close*100<=8)&(d.gain5<=8)&(d.extension_atr<=2)&d.RS20.notna()&d.RS60.notna()&d.RS120.notna()&(np.arange(len(d))>=125)).fillna(False)

def cheap_mask(d,spec):
    e=spec['engine'];n=spec['native'];m=common_mask(d,spec['volume'])
    if e=='failed_breakdown':m&=d[f'failed_level{n}'].notna()&(d.Close>d.High.shift())&d.RS20_improving&(d.RSI14>d.RSI14.shift())&d.hist_improving
    elif e=='base_contraction':m&=d[f'base_ok{n}']&d.above5&d.RS20_improving&d.RSI14.ge(40)&d.hist_improving
    elif e=='controlled_pullback':m&=(d.Close>d.High.shift())&(d.Close>d.EMA20)&d.RS20.gt(0)&d.hist_improving
    elif e=='simple_momentum20':m&=(d.Close>d.EMA20)&d.ROC20.gt(0)&d.RS20.gt(0)
    return m.fillna(False)

def context(symbol,d,benchmark,proxy=None):
    date=d.index[-1];b=benchmark.loc[:date,'Close'];e20=b.ewm(span=20,adjust=False,min_periods=20).mean();e50=b.ewm(span=50,adjust=False,min_periods=50).mean()
    market=bool(len(b)>50 and (b.iloc[-1]>=e50.iloc[-1] or e20.iloc[-1]>=e20.iloc[-6]))
    sector=proxy.excess(symbol,date,benchmark,20) if proxy is not None else None
    return {'market_regime':'Risk_ON_or_Neutral' if market else 'Risk_OFF','market_filter_pass':market,'sector_rs20_pct_points':sector,'sector_membership':'current_universe_unofficial_not_point_in_time','sector_filter_pass':sector is not None and sector>=0}

def pattern(d,spec,structure):
    e=spec['engine'];n=spec['native'];last=d.iloc[-1]
    if e=='failed_breakdown':
        wick=(min(last.Open,last.Close)-last.Low)>(last.High-last.Low)*.4
        if not (structure['confirmed_higher_lows'] or wick):return False,'no_higher_low_or_wick_rejection',{}
        return True,None,{'frozen_reclaimed_support':float(last[f'failed_level{n}']),'support_lookback':n}
    if e=='base_contraction':
        if not structure['confirmed_higher_lows']:return False,'no_confirmed_higher_lows',{}
        return True,None,{'base_sessions':n,'preceding_base_end':str(d.index[-2].date())}
    if e=='controlled_pullback':
        if not structure['confirmed_higher_lows']:return False,'no_confirmed_higher_lows',{}
        pullback=d.iloc[-n-1:-1];before=d.iloc[:-n-1];support=structure['nearest_support'];atr=float(last.ATR14)
        touches=bool(((pullback.Low-pullback.EMA20).abs()<=.5*pullback.ATR14).any())
        if support:touches=touches or bool(((pullback.Low-support['center']).abs()<=.5*atr).any())
        if not touches:return False,'no_controlled_support_test',{}
        if len(before)<20 or not pullback.Volume.mean()<before.Volume.tail(20).mean():return False,'pullback_volume_not_contracting',{}
        historical=before.tail(15);reclaims=historical[historical.reclaim]
        if reclaims.empty:return False,'no_initial_reversal_before_pullback',{}
        at=reclaims.index[-1];start=float(reclaims.Close.iloc[-1]);gain=100*(before.loc[at:,'High'].max()/start-1)
        if not 3<=gain<=15:return False,'initial_reversal_gain_outside_3_15',{}
        return True,None,{'initial_reversal_date':str(at.date()),'initial_reversal_gain_pct':float(gain),'pullback_sessions':n}
    return True,None,{}

def generate(histories,benchmark,sessions,plan,proxy=None,latest_only=False):
    specs=specifications(plan);specs['simple_momentum20']={'engine':'simple_momentum20','native':20,'volume':1.5,'conditioning':None}
    signals={n:{} for n in specs};rejected={n:Counter() for n in specs};prepared={};observations=[];eligibility_counts={n:set() for n in specs}
    scenario_plan={'major_zone_minimum_touches':3,'support_buffer_atr':.25,'stop_atr_floor':1.5,'maximum_stop_pct':8,'minimum_upside_pct':10,'minimum_reward_risk':2}
    for symbol,df in histories.items():
        d=prepare(df,benchmark,sessions);prepared[symbol]=d;cache={}
        for name,spec in specs.items():
            mask=cheap_mask(d,spec)
            indexes=([len(d)-1] if mask.iloc[-1] else []) if latest_only else np.flatnonzero(mask.to_numpy())
            for i in indexes:
                date=d.index[i];pos=sessions.searchsorted(date)
                if pos>=len(sessions) or date!=sessions[pos]:continue
                prefix=d.iloc[:i+1]
                if i not in cache:cache[i]=(historical_window(prefix,sessions[:pos+1]),price_structure(prefix),context(symbol,prefix,benchmark,proxy))
                eligibility,structure,ctx=cache[i]
                if not eligibility['eligible']:rejected[name]['history_not_eligible']+=1;continue
                eligibility_counts[name].add(symbol)
                if spec['conditioning'] and not ctx[spec['conditioning']+'_filter_pass']:rejected[name][spec['conditioning']+'_condition_failed_or_unavailable']+=1;continue
                ok,reason,details=pattern(prefix,spec,structure)
                if not ok:rejected[name][reason]+=1;continue
                levels,reason=scenario(prefix,structure,scenario_plan)
                if reason:rejected[name][reason]+=1;continue
                last=prefix.iloc[-1]
                r={'symbol':symbol,'date':str(date.date()),'close':float(last.Close),'engine':spec['engine'],'variant':name,'classification':'Shadow Candidate',
                   'technical_score':float(last.RS20),'_original_stop':levels['invalidation'],'scenario':levels,'hypothesis':details,
                   'observations':{'volume_confirmed':True,'price_confirmed':True,'volume':float(last.Volume),'volume_ratio':float(last.volume_ratio)},
                   'entry_context':ctx,'features':{k:float(last[k]) if pd.notna(last[k]) else None for k in ('EMA20','EMA50','RSI14','MACD','MACD_signal','ATR14','RS20','RS60','RS120','gain5','ROC10','ROC20','extension_atr')},
                   'history_eligibility':eligibility,'data_quality':{'entry_eligible':True,'independently_validated':False},'live_order_authorized':False}
                if pos+1<len(sessions):signals[name].setdefault(sessions[pos+1],[]).append((symbol,copy.deepcopy(r)))
                if date==sessions[-1]:observations.append(r)
    return signals,prepared,{n:dict(v) for n,v in rejected.items()},observations,{n:len(s) for n,s in eligibility_counts.items()}
