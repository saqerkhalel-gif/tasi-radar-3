"""Phase-two causal structure, data quarantine and reproducible research.
All feature functions see only a prefix ending at signal close. Future bars are
used exclusively by the execution engine and retrospective outcome evaluation.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import numpy as np
import pandas as pd


def quality_audit(d, sessions=None):
    repairs=d.attrs.get('price_repairs',[])
    repaired={x['date'] for x in repairs}
    # A large adjusted-price discontinuity needs corporate-action verification.
    jumps=d['Close'].pct_change().abs()>0.22
    flagged={str(x.date()) for x in d.index[jumps]}
    quarantine=sorted(repaired|flagged)
    recent={str(x.date()) for x in d.index[-200:]}
    missing=[]
    if sessions is not None and len(d):
        grid=sessions[(sessions>=d.index[0])&(sessions<=d.index[-1])]
        missing=[str(x.date()) for x in grid.difference(d.index)]
    zero=d['Volume'].eq(0)
    return {'entry_eligible':not bool(recent.intersection(quarantine)) and not bool(zero.iloc[-1]),
            'normalization':d.attrs.get('normalization',{}),'quarantined_dates':quarantine,'unverified_quote_repairs':repairs,
            'large_adjusted_price_jumps':sorted(flagged),'missing_session_count':len(missing),
            'missing_sessions':missing,'zero_volume_rows':int(zero.sum()),
            'last_bar_zero_volume':bool(zero.iloc[-1]),
            'status':'quarantined' if recent.intersection(quarantine) else 'vendor_checks_passed',
            'independent_exchange_validation':False,
            'note':'Vendor checks are not official exchange validation. Quote-substituted closes and >22% adjusted-price jumps are quarantined; no automatic price repair.'}


def price_structure(d):
    """Only pivots confirmed by two already observed right-hand bars are used."""
    w=d.tail(90);c=float(w['Close'].iloc[-1]);a=float(w['ATR14'].iloc[-1]) if pd.notna(w['ATR14'].iloc[-1]) else c*.02
    tol=max(a*.5,c*.005);pivots=[];lows=[]
    low=w['Low'].to_numpy();high=w['High'].to_numpy()
    for i in range(2,len(w)-2):
        for side,prices,ok in [('support',low,low[i]==low[i-2:i+3].min()),('resistance',high,high[i]==high[i-2:i+3].max())]:
            if ok:
                p={'side':side,'price':float(prices[i]),'date':str(w.index[i].date()),'confirmed_date':str(w.index[i+2].date())}
                pivots.append(p)
                if side=='support':lows.append(p)
    clusters=[]
    for p in sorted(pivots,key=lambda x:x['price']):
        if clusters and p['price']-clusters[-1]['center']<=tol:
            z=clusters[-1];z['points'].append(p);z['center']=float(np.mean([x['price'] for x in z['points']]))
        else:clusters.append({'center':p['price'],'points':[p]})
    zones=[{'low':z['center']-tol/2,'high':z['center']+tol/2,'center':z['center'],
            'touches':len(z['points']),'last_pivot_date':max(p['date'] for p in z['points']),
            'side':'support' if z['center']<c else 'resistance'} for z in clusters if len(z['points'])>=2]
    support=next(iter(sorted([z for z in zones if z['high']<c],key=lambda z:z['center'],reverse=True)),None)
    resistance=next(iter(sorted([z for z in zones if z['low']>c],key=lambda z:z['center'])),None)
    inv=support['low']-a*.25 if support else None
    return {'zones':zones,'nearest_support':support,'nearest_resistance':resistance,
            'structural_invalidation':inv if inv and 0<inv<c else None,
            'confirmed_higher_lows':len(lows)>=2 and lows[-1]['price']>lows[-2]['price'],
            'last_confirmed_lows':lows[-3:],'pivot_confirmation_sessions':2,
            'method':'90 observed bars; five-bar confirmed pivots clustered within max(0.5 ATR,0.5% price); heuristic zones'}


def early_patterns(d,structure):
    last=d.iloc[-1];c=float(last['Close']);hist=d['MACD']-d['MACD_signal']
    momentum=bool(len(d)>=4 and hist.iloc[-4:].notna().all() and hist.iloc[-1]>hist.iloc[-4] and hist.iloc[-1]>hist.iloc[-2])
    atr=d['ATR14']/d['Close'];volatility=bool(len(d)>=40 and atr.iloc[-5:].mean()<atr.iloc[-40:-5].median()*.8)
    returns=d['Close'].diff();up=d['Volume'].where(returns>0,0).tail(10).sum();down=d['Volume'].where(returns<0,0).tail(10).sum()
    demand=bool(up>down*1.3 and up>0)
    res=last['prior_resistance20'];sup=last['prior_support20']
    false_breakout=bool(pd.notna(res) and last['High']>res and c<res)
    bear_trap=bool(pd.notna(sup) and last['Low']<sup and c>sup and momentum)
    retest=False;retest_level=None
    # Earlier breakout must already exist; today's candle may only test it.
    for i in range(max(20,len(d)-10),len(d)-1):
        row=d.iloc[i];level=row['prior_resistance20']
        if pd.notna(level) and row['Close']>level:
            if last['Low']<=level+float(last['ATR14'])*.5 and c>level and d['Close'].iloc[i+1:].min()>=level*.98:
                retest=True;retest_level=float(level)
    flags={'confirmed_higher_lows':structure['confirmed_higher_lows'],'volatility_contraction':volatility,
           'momentum_improving':momentum,'demand_volume_improving':demand,
           'false_upside_breakout':false_breakout,'failed_downside_breakdown':bear_trap,'breakout_retest_holds':retest}
    accumulation=bool(flags['confirmed_higher_lows'] and volatility and demand)
    reversal=bool(momentum and (flags['confirmed_higher_lows'] or bear_trap or retest))
    return {**flags,'accumulation_candidate':accumulation,'early_reversal_candidate':reversal,
            'retest_level':retest_level,'up_down_volume_ratio10':float(up/down) if down else None,
            'evidence':[k for k,v in flags.items() if v],
            'note':'Observed patterns; Early Watch until all original Entry gates and data-quality gates pass.'}


def benchmark_audit(bench, live, sessions, expected, errors):
    if bench is None or bench.empty:
        return {'entry_eligible':False,'reason':'missing benchmark','independent_exchange_validation':False}
    overlap=bench.index.intersection(live.index) if live is not None else pd.DatetimeIndex([])
    mismatch=[] if not len(overlap) else [str(x.date()) for x in overlap[(bench.loc[overlap,'Close']/live.loc[overlap,'Close']-1).abs()>.001]]
    jumps=[str(x.date()) for x in bench.index[bench['Close'].pct_change().abs()>.15]]
    recent=sessions[sessions<=pd.Timestamp(expected)][-61:]
    eligible=len(recent)==61 and recent.isin(bench.index).all() and not mismatch and not jumps and not any('disagreement' in x for x in errors)
    # Current vendor overlap is required for live signals, not historical simulated signals.
    eligible=bool(eligible and len(overlap) and pd.Timestamp(expected) in overlap)
    return {'entry_eligible':eligible,'rows':len(bench),'source_overlap_rows':len(overlap),'mismatch_dates':mismatch,
            'suspicious_jump_dates':jumps,'recent_61_sessions_complete':bool(len(recent)==61 and recent.isin(bench.index).all()),
            'independent_exchange_validation':False,'sha256':hashlib.sha256(bench.to_csv().encode()).hexdigest(),
            'note':'Persisted Investing TASI instrument 11319, observed cache and Yahoo ^TASI.SR. Overlap tolerance 0.1%; no interpolation. Full historical official exchange reconciliation unavailable.'}


def trade_exit(bar,stop,target):
    """Gap prices first, then adverse ordering if both levels touch in one bar."""
    if bar['Open']<=stop:return float(bar['Open']),'gap_stop'
    if bar['Open']>=target:return float(target),'gap_target_capped'
    if bar['Low']<=stop:return float(stop),'stop'
    if bar['High']>=target:return float(target),'target'
    return None,None


def portfolio_backtest(data,signals,benchmark,dates,cfg):
    bt=cfg.get('backtest',{});cost=(bt.get('commission_bps_per_side',15.5)+bt.get('slippage_bps_per_side',5))/10000
    slots=bt.get('max_positions',10);hold=bt.get('max_hold_sessions',20)
    cash=100000.;positions={};trades=[];curve=[];skipped=Counter();marks_stale=0
    def close_position(symbol,price,date,reason):
        nonlocal cash
        p=positions.pop(symbol);cash+=p['quantity']*price*(1-cost)
        net=price*(1-cost)/(p['entry_price']*(1+cost))-1
        trades.append({k:v for k,v in p.items() if k not in ('quantity','last_mark','age') }|{'exit_date':str(date.date()),'exit_price':price,'exit_reason':reason,'net_return_pct':100*net})
    for date in dates:
        # Signals are from the preceding calendar session, never this day's close.
        for symbol,record in sorted(signals.get(date,[]),key=lambda x:(-x[1]['technical_score'],x[0])):
            if symbol in positions or len(positions)>=slots:continue
            bar=data[symbol].loc[date] if date in data[symbol].index else None
            if bar is None:skipped['missing_execution_bar']+=1;continue
            if str(date.date()) in data[symbol].attrs.get('quarantine',[]):skipped['quarantined_execution_bar']+=1;continue
            price=float(bar['Open']);stop=record['scenario']['invalidation'];target=record['scenario']['conditional_target']
            upside=(target/price-1)*100;rr=(target-price)/(price-stop) if price>stop else -1
            if upside<10 or rr<2 or price<=stop or price>=target:skipped['next_open_invalidates_reward_or_risk']+=1;continue
            equity=cash+sum(p['quantity']*p['last_mark'] for p in positions.values());budget=min(cash,equity/slots)
            if budget<1:continue
            quantity=budget/(price*(1+cost));cash-=budget
            positions[symbol]={'symbol':symbol,'signal_date':record['date'],'entry_date':str(date.date()),'entry_price':price,'quantity':quantity,
                               'stop':stop,'target':target,'age':0,'last_mark':price,'signal_score':record['technical_score']}
        for symbol,p in list(positions.items()):
            df=data[symbol]
            if date not in df.index or str(date.date()) in df.attrs.get('quarantine',[]):
                marks_stale+=1;p['age']+=1;continue
            bar=df.loc[date];p['age']+=1;p['last_mark']=float(bar['Close'])
            price,reason=trade_exit(bar,p['stop'],p['target'])
            if price is None and p['age']>=hold:price=float(bar['Close']);reason='time_exit'
            if price is not None:close_position(symbol,price,date,reason)
        curve.append({'date':str(date.date()),'equity':cash+sum(p['quantity']*p['last_mark'] for p in positions.values())})
    unliquidated=0
    if len(dates):
        last=dates[-1]
        for symbol,p in list(positions.items()):
            if last in data[symbol].index and str(last.date()) not in data[symbol].attrs.get('quarantine',[]):close_position(symbol,float(data[symbol].loc[last,'Close']),last,'end_of_test')
            else:unliquidated+=1
        curve[-1]['equity']=cash+sum(p['quantity']*p['last_mark'] for p in positions.values())
    values=np.array([100000.]+[x['equity'] for x in curve]);peak=np.maximum.accumulate(values)
    wins=[t['net_return_pct'] for t in trades if t['net_return_pct']>0];loss=[t['net_return_pct'] for t in trades if t['net_return_pct']<=0]
    netreturn=100*(values[-1]/100000-1)
    valid=bool(len(dates)>1 and benchmark is not None and dates.isin(benchmark.index).all() and not unliquidated and benchmark.attrs.get('historical_integrity_ok',True))
    bm=100*(benchmark.loc[dates[-1],'Close']*(1-cost)/(benchmark.loc[dates[0],'Close']*(1+cost))-1) if valid else None
    return {'start_date':str(dates[0].date()) if len(dates) else None,'end_date':str(dates[-1].date()) if len(dates) else None,
            'trades_count':len(trades),'win_rate_pct':100*len(wins)/len(trades) if trades else None,
            'average_win_pct':float(np.mean(wins)) if wins else None,'average_loss_pct':float(np.mean(loss)) if loss else None,
            'expectancy_pct':float(np.mean([t['net_return_pct'] for t in trades])) if trades else None,
            'portfolio_return_pct':netreturn,'maximum_drawdown_pct':float(100*np.min(values/peak-1)),
            'tasi_buy_hold_net_return_pct':bm,'excess_return_pct_points':netreturn-bm if bm is not None else None,
            'comparison_valid':valid,'unliquidated_positions':unliquidated,'stale_mark_position_days':marks_stale,
            'skipped_orders':dict(skipped),'trades':trades,'equity_curve':curve}


def historical_research(histories,benchmark,sessions,cfg,analyze,indicators):
    """Evaluate a frozen strategy; no parameter search, no randomized splits."""
    bt=cfg.get('backtest',{});minimum=cfg.get('minimum_entry_history_rows',200)
    signals={};snapshots={};missed=[];detected=[];window=bt.get('max_hold_sessions',20);hashes={}
    warm=[]
    for symbol,df in histories.items():
        prepared=indicators(df);snapshots[symbol]={};q=set(df.attrs.get('quarantine',[]));hashes[symbol]=hashlib.sha256(df.to_csv().encode()).hexdigest()
        if len(df)>minimum:warm.append(df.index[minimum])
        print('Historical research '+symbol,flush=True)
        # The earlier 20-bar histories also permit evaluating missed early-watch patterns.
        cooldown=-1
        for i in range(19,len(df)):
            date=df.index[i];date_s=str(date.date())
            bench_prefix=benchmark.loc[:date] if benchmark is not None else None
            r=analyze(symbol,df.iloc[:i+1],cfg,bench_prefix,date_s,sessions[sessions<=date],prepared=prepared.iloc[:i+1],research_mode=True)
            snapshots[symbol][date_s]=r
            if len(snapshots[symbol])>5:del snapshots[symbol][next(iter(snapshots[symbol]))]
            next_index=sessions.searchsorted(date)+1
            if r['classification'] in ('Entry','Partial Entry') and next_index<len(sessions):signals.setdefault(sessions[next_index],[]).append((symbol,r))
            # Matured, non-overlapping 20-session excursions; never used as features.
            future_dates=sessions[next_index:next_index+window]
            if i<=cooldown or len(future_dates)<window or not future_dates.isin(df.index).all():continue
            used=[date_s]+[str(x.date()) for x in future_dates]
            if q.intersection(used):continue
            future=df.loc[future_dates];peak=float(future['High'].max());gain=100*(peak/float(df.iloc[i]['Close'])-1)
            if gain<10:continue
            cooldown=i+window
            prior=[snapshots[symbol].get(str(x.date())) for x in df.index[max(19,i-4):i+1]]
            recognized=any(p and p['classification'] in ('Entry','Partial Entry','Early Watch') for p in prior)
            record={'symbol':symbol,'base_date':date_s,'evaluation_end':str(future_dates[-1].date()),'base_close':float(df.iloc[i]['Close']),
                    'maximum_high_gain_pct':gain,'maximum_close_gain_pct':100*(float(future['Close'].max())/float(df.iloc[i]['Close'])-1),
                    'classification_at_base':r['classification'],'detected_in_previous_5_observed_bars':recognized,
                    'not_entry_reasons':r['entry_blockers'],'missing_detection_reasons':[] if recognized else ['no_early_pattern_or_trend_confirmation']+r['entry_blockers'],
                    'patterns_at_base':r.get('early_patterns',{}),'note':'Retrospective high excursion, not a realizable strategy return; 20 calendar sessions, deduplicated per stock.'}
            (detected if recognized else missed).append(record)
    dates=sessions[sessions>=min(warm)] if warm else sessions[:0]
    excluded_tail=[]
    while len(dates):
        day=str(dates[-1].date());available=[d for d in histories.values() if len(d) and d.index[0]<=dates[-1]]
        unusable=sum(dates[-1] not in d.index or day in d.attrs.get('quarantine',[]) for d in available)
        if not available or unusable/max(len(available),1)<=.10:break
        excluded_tail.append({'date':day,'unusable_stock_count':unusable,'available_histories':len(available)});dates=dates[:-1]
    # Calendar split fixed by available evaluation dates; holdout is descriptive,
    # not an independent validation set because current rules were not preregistered.
    split=int(len(dates)*.7);holdout=dates[split:]
    full=portfolio_backtest(histories,signals,benchmark,dates,cfg);oos=portfolio_backtest(histories,signals,benchmark,holdout,cfg)
    backtest={'strategy_version':'phase2.0','execution':'Prior-session signals, next-session open; open reward/risk rechecked; fixed stop/target, stop first on ambiguous bars, 20-session maximum hold; max 10 equal-equity slots; cash uninvested earns zero.',
              'cost_model':{'commission_bps_per_side':bt.get('commission_bps_per_side',15.5),'slippage_bps_per_side':bt.get('slippage_bps_per_side',5),'taxes_included':False,'applied_to':'entry and exit notional; configured assumptions, not broker quote'},
              'data_hashes':hashes,'full_period':full,'chronological_last_30pct':oos,
              'excluded_tail_sessions':excluded_tail,'signal_count':sum(len(x) for date,x in signals.items() if date in dates),'holdout_note':'Chronological 70/30 descriptive split; no optimization, no claim of independent out-of-sample validation.',
              'limitations':['Current 254-company snapshot creates survivorship bias; delisted equities absent.','Only about 520 calendar days available; short history, few trades and one market regime can be inconclusive.','Vendor retrospectively adjusted prices are not point-in-time corporate-action snapshots.','Quarantined bars cannot generate signals, execute orders or value exits; missing position marks are carried and counted.','TASI comparison uses observed close-to-close values over identical evaluation dates; stocks enter at next open.','No tax, spread beyond assumed slippage, liquidity capacity or dividend cash-flow model; adjusted closes embed vendor adjustments.','No reconstruction of how old source corrections were known in real time.']}
    opportunities={'window_sessions':window,'minimum_excursion_pct':10,'detected_count':len(detected),'missed_count':len(missed),
                   'missed_reason_counts':dict(Counter(reason for x in missed for reason in x['missing_detection_reasons'])),
                   'detected':detected,'missed':missed,'note':'Retrospective research, not forward performance. Early Watch counts as detected, not as an Entry or profitable trade.'}
    return backtest,opportunities


def update_ledger(previous,results,histories,run_id):
    import copy
    ledger=copy.deepcopy((previous or {}).get('opportunities',[]));ids={x['id'] for x in ledger}
    for item in ledger:
        if item.get('status') not in ('watching','triggered'):continue
        df=histories.get(item['symbol'])
        if df is None:continue
        for date,bar in df[df.index>pd.Timestamp(item['last_evaluated_date'])].iterrows():
            day=str(date.date())
            if day in df.attrs.get('quarantine',[]):continue
            item['last_evaluated_date']=day;item['observed_sessions']+=1
            item['maximum_high_gain_pct']=max(item['maximum_high_gain_pct'],100*(float(bar['High'])/item['discovery_close']-1))
            item['maximum_adverse_move_pct']=min(item['maximum_adverse_move_pct'],100*(float(bar['Low'])/item['discovery_close']-1))
            stop=item['scenario'].get('invalidation');target=item['scenario'].get('conditional_target');trigger=item['scenario'].get('trigger')
            if stop and bar['Low']<=stop:item['status']='invalidated'
            elif target and bar['High']>=target:item['status']='target_touched'
            elif trigger and bar['Close']>trigger:item['status']='triggered' # observed crossing, not a new Entry authorization
            if item['status'] in ('invalidated','target_touched'):break
            if item['observed_sessions']>=20:item['status']='expired';break
    for r in results:
        if r['classification']=='Wait' or not r['data_fresh']:continue
        if not r['data_quality']['entry_eligible']:continue
        key=r['symbol']+':'+r['date']
        # Keep one unresolved scenario per symbol; freeze levels on discovery.
        if key in ids or any(x['symbol']==r['symbol'] and x['status'] in ('watching','triggered') for x in ledger):continue
        ledger.append({'id':key,'symbol':r['symbol'],'discovery_date':r['date'],'discovery_run_id':run_id,'discovery_close':r['close'],
                       'classification_at_discovery':r['classification'],'scenario':copy.deepcopy(r['scenario']),'status':'watching',
                       'last_evaluated_date':r['date'],'observed_sessions':0,'maximum_high_gain_pct':0.,'maximum_adverse_move_pct':0.})
    return {'opportunities':ledger,'note':'Forward ledger starts on deployment. Discovery levels frozen; later trusted bars only. A trigger crossing is not an Entry authorization.'}
