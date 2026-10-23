"""Predeclared ablations on an immutable phase-two input snapshot.
Research-only: this module never changes the live scanner's classification.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os
from collections import Counter
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from radar import analyze, indicators, clean, session_calendar
from research import trade_exit


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_snapshot(root):
    root=Path(root);p=json.loads((root/'output/latest.json').read_text());bt=json.loads((root/'output/backtest.json').read_text())
    assert p['run_id']=='39870228858' and bt['run_id']==p['run_id']
    inputs=root/'research_inputs';cfg=json.loads((inputs/'config.json').read_text());meta=json.loads((inputs/'stock_metadata.json').read_text());histories={}
    for symbol in sorted(meta):
        d=pd.read_csv(inputs/(symbol+'.csv.gz'),index_col='Date',parse_dates=True,float_precision='round_trip');d.attrs.update(meta[symbol])
        assert hashlib.sha256(d.to_csv().encode()).hexdigest()==bt['data_hashes'][symbol],symbol+' input hash mismatch'
        histories[symbol]=d
    bench=pd.read_csv(inputs/'benchmark.csv',index_col='Date',parse_dates=True,float_precision='round_trip');bench.attrs.update(json.loads((inputs/'benchmark_metadata.json').read_text()))
    sessions,_=session_calendar(datetime.fromisoformat(p['run_utc']),cfg)
    return histories,bench,sessions,cfg,p,bt


def causal_signals(histories,bench,sessions,cfg):
    """Exact short circuit of mandatory original gates; never a new strategy.
    EMA/volume/price gates are causal vector operations. Expensive structure and
    RS calculations are evaluated only where all mandatory cheap gates pass.
    """
    signals={};prepared={}
    for symbol,df in histories.items():
        d=indicators(df);prepared[symbol]=d
        trend=(d['Close']>d['EMA20'])&(d['EMA20']>d['EMA50'])&(d['Close']>d['EMA200'])
        price=(d['Close']>d['prior_resistance20'])|((d['Close'].shift()<=d['EMA20'].shift())&(d['Close']>d['EMA20']))
        baseline=d['Volume'].shift().rolling(20,min_periods=20).mean()
        volume=(baseline>0)&(d['Volume']>0)&(d['Volume']/baseline>=cfg['volume_confirmation_multiple'])
        possible=trend&price&volume&(d['ATR14']/d['Close']*100<=cfg['max_atr_pct'])&(np.arange(len(d))>=cfg['minimum_entry_history_rows']-1)
        for i in np.flatnonzero(possible.to_numpy()):
            date=d.index[i];pos=sessions.searchsorted(date)+1
            if pos>=len(sessions):continue
            r=analyze(symbol,df.iloc[:i+1],cfg,bench.loc[:date],str(date.date()),sessions[sessions<=date],prepared=d.iloc[:i+1],research_mode=True)
            if r['classification'] in ('Entry','Partial Entry'):signals.setdefault(sessions[pos],[]).append((symbol,r))
    return signals,prepared


class SectorProxy:
    """Causal, leave-target-out, unofficial equal-weight sector basket."""
    def __init__(self,histories,universe,sessions,plan):
        self.sessions=sessions;self.plan=plan;self.sectors=universe.set_index('symbol')['sector'].to_dict();self.cache={}
        prices=pd.DataFrame({s:d['Close'].reindex(sessions) for s,d in histories.items()},index=sessions)
        for s,d in histories.items():
            q=pd.to_datetime(d.attrs.get('quarantine',[]));prices.loc[prices.index.isin(q),s]=np.nan
        self.returns=prices.pct_change(fill_method=None)
        self.first={s:d.index[0] for s,d in histories.items()}
    def excess(self,symbol,date,bench,window):
        key=(symbol,str(date),window)
        if key in self.cache:return self.cache[key]
        peers=[s for s in self.returns if s!=symbol and self.sectors.get(s)==self.sectors.get(symbol)]
        grid=self.sessions[self.sessions<=date][-(window+1):];answer=None
        if len(peers)>=self.plan['minimum_other_peers'] and len(grid)==window+1 and grid.isin(bench.index).all():
            active=pd.DataFrame({s:grid[1:]>=self.first[s] for s in peers},index=grid[1:]).sum(axis=1)
            r=self.returns.loc[grid[1:],peers];count=r.notna().sum(axis=1)
            enough=(count>=self.plan['minimum_other_peers'])&(count/active.replace(0,np.nan)>=self.plan['minimum_coverage'])
            if enough.all():answer=float(100*((1+r.mean(axis=1)).prod()-bench.loc[grid[-1],'Close']/bench.loc[grid[0],'Close']))
        self.cache[key]=answer;return answer


def entry_context(symbol,r,d,bench,proxy,plan):
    date=pd.Timestamp(r['date']);prefix=d.loc[:date];last=prefix.iloc[-1];b=bench.loc[:date,'Close']
    e50=b.ewm(span=50,adjust=False,min_periods=50).mean();e200=b.ewm(span=200,adjust=False,min_periods=200).mean()
    slope=plan['market_filter']['ema50_slope_sessions']
    market=bool(len(b)>max(200,slope) and b.iloc[-1]>e50.iloc[-1]>e200.iloc[-1] and e50.iloc[-1]>e50.iloc[-1-slope])
    atr=float(last['ATR14']);gain5=100*(last['Close']/prefix['Close'].iloc[-6]-1) if len(prefix)>=6 else None
    extension=(float(last['Close'])-float(last['EMA20']))/atr if atr>0 else None
    sector={str(n):proxy.excess(symbol,date,bench,n) for n in (20,60)}
    sector_ok=all(v is not None and v>0 for v in sector.values())
    confirmed=False;frozen=None
    for i in range(max(20,len(prefix)-1-plan['confirmation']['previous_breakout_lookback_sessions']),len(prefix)-1):
        row=prefix.iloc[i];level=row['prior_resistance20']
        if pd.notna(level) and row['Close']>level and (prefix['Close'].iloc[-2:]>level).all():confirmed=True;frozen=float(level)
    return {'market_trend_pass':market,'tasi_close':float(b.iloc[-1]),'tasi_ema50':float(e50.iloc[-1]) if pd.notna(e50.iloc[-1]) else None,
            'tasi_ema200':float(e200.iloc[-1]) if pd.notna(e200.iloc[-1]) else None,
            'sector_proxy_excess_pct_points':sector,'sector_strength_pass':sector_ok,
            'sector_data_available':all(v is not None for v in sector.values()),
            'gain_5_sessions_pct':gain5,'extension_above_ema20_atr':extension,'atr_at_signal':atr,
            'anti_chase_pass':bool(gain5 is not None and extension is not None and gain5<=plan['anti_chase']['maximum_5_session_gain_pct'] and extension<=plan['anti_chase']['maximum_extension_above_ema20_atr']),
            'confirmed_breakout_pass':confirmed,'frozen_confirmation_level':frozen,
            'retest_pass':r['early_patterns']['breakout_retest_holds'],
            'signal_price_breakout':r['observations']['price_breakout20']}


def make_variants(signals,prepared,bench,proxy,plan):
    variants={name:{} for name in plan['variants']};contexts={};rejections={name:Counter() for name in variants}
    for execution_date,rows in signals.items():
        for symbol,r in rows:
            ctx=entry_context(symbol,r,prepared[symbol],bench,proxy,plan);contexts[(symbol,r['date'])]=ctx
            gates={'baseline':True,'tasi_trend':ctx['market_trend_pass'],'sector_strength':ctx['sector_strength_pass'],
                   'confirmed_breakout':ctx['confirmed_breakout_pass'],'retest':ctx['retest_pass'],'anti_chase':ctx['anti_chase_pass'],
                   'market_sector_anti_chase':ctx['market_trend_pass'] and ctx['sector_strength_pass'] and ctx['anti_chase_pass']}
            for name in variants:
                v=copy.deepcopy(r)
                if name.startswith('stop_'):
                    atr=ctx['atr_at_signal'];original=v['scenario']['invalidation'];price=v['close']
                    if name=='stop_atr_floor':stop=min(original,price-plan['stop_variants']['atr_floor']['minimum_distance_atr']*atr)
                    else:
                        support=v['price_structure']['nearest_support']
                        if support is None:rejections[name]['missing_confirmed_support']+=1;continue
                        stop=min(original,support['low']-plan['stop_variants']['support_buffer']['buffer_atr']*atr)
                    target=v['scenario']['conditional_target']
                    if stop<=0 or stop>=price or (price-stop)/price*100>plan['stop_variants']['maximum_stop_distance_pct']:
                        rejections[name]['stop_distance_exceeds_cap_or_invalid']+=1;continue
                    if (target-price)/(price-stop)<2:rejections[name]['wider_stop_fails_reward_risk']+=1;continue
                    v['_original_stop']=original;v['scenario']['invalidation']=stop;v['scenario']['reward_risk']=(target-price)/(price-stop)
                elif not gates[name]:
                    reason='sector_proxy_unavailable' if name=='sector_strength' and not ctx['sector_data_available'] else 'signal_filter_rejected'
                    rejections[name][reason]+=1;continue
                variants[name].setdefault(execution_date,[]).append((symbol,v))
    return variants,contexts,{name:dict(x) for name,x in rejections.items()}


def simulate(data,signals,benchmark,dates,cfg,plan=None,risk_sized=False):
    bt=cfg.get('backtest',{});cost=(bt.get('commission_bps_per_side',15.5)+bt.get('slippage_bps_per_side',5))/10000
    slots=bt.get('max_positions',10);hold=bt.get('max_hold_sessions',20)
    cash=100000.;positions={};trades=[];curve=[];skipped=Counter();marks_stale=0;max_planned_risk_pct=0
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
            risk_details={}
            if risk_sized:
                limits=plan['stop_variants']
                if (price-stop)/price*100>limits['maximum_stop_distance_pct']:
                    skipped['execution_stop_distance_exceeds_cap']+=1;continue
                original=record['_original_stop']
                if original>=price:skipped['invalid_original_risk_reference']+=1;continue
                original_risk_share=price-original+cost*(price+original)
                risk_share=price-stop+cost*(price+stop)
                base_risk=equity/slots/(price*(1+cost))*original_risk_share
                existing=sum(p['quantity']*(p['entry_price']-p['stop']+cost*(p['entry_price']+p['stop'])) for p in positions.values())
                allowed=min(equity*limits['maximum_equity_risk_per_trade_pct']/100,base_risk,max(0,equity*limits['maximum_aggregate_open_equity_risk_pct']/100-existing))
                budget=min(budget,allowed/risk_share*price*(1+cost))
                planned=budget/(price*(1+cost))*risk_share
                max_planned_risk_pct=max(max_planned_risk_pct,100*(existing+planned)/equity)
                risk_details={'planned_risk_cash':planned,'same_signal_baseline_risk_cash':base_risk,'equity_at_entry':equity}
            if budget<1:continue
            quantity=budget/(price*(1+cost));cash-=budget
            positions[symbol]={'symbol':symbol,'signal_date':record['date'],'entry_date':str(date.date()),'entry_price':price,'quantity':quantity,
                               'stop':stop,'target':target,'age':0,'last_mark':price,'signal_score':record['technical_score'],**risk_details}
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
            'skipped_orders':dict(skipped),'trades':trades,'equity_curve':curve,'maximum_aggregate_planned_risk_pct':max_planned_risk_pct if risk_sized else None}



def add_metrics(result):
    e=np.array([100000.]+[x['equity'] for x in result['equity_curve']]);r=e[1:]/e[:-1]-1
    result['daily_sharpe_annualized']=float(np.sqrt(252)*r.mean()/r.std(ddof=1)) if len(r)>1 and r.std(ddof=1)>1e-12 else None
    dd=abs(result['maximum_drawdown_pct']);result['return_over_drawdown']=result['portfolio_return_pct']/dd if dd>1e-10 else None
    return result


def bootstrap_excess(candidate,baseline,plan,trials):
    def returns(x):
        e=np.array([100000.]+[r['equity'] for r in x['equity_curve']]);return e[1:]/e[:-1]-1
    diff=returns(candidate)-returns(baseline);n=len(diff);block=plan['daily_bootstrap_block_sessions']
    if n<block:return {'lower_mean_daily_excess_pct':None,'upper_mean_daily_excess_pct':None}
    rng=np.random.default_rng(plan['random_seed']);samples=[]
    for _ in range(plan['bootstrap_samples']):
        starts=rng.integers(0,n-block+1,size=int(np.ceil(n/block)))
        sample=np.concatenate([diff[i:i+block] for i in starts])[:n];samples.append(sample.mean()*100)
    alpha=plan['familywise_alpha']/trials
    return {'lower_mean_daily_excess_pct':float(np.quantile(samples,alpha/2)),
            'upper_mean_daily_excess_pct':float(np.quantile(samples,1-alpha/2)),
            'bonferroni_trials':trials,'block_sessions':block,'resamples':len(samples),
            'note':'Paired moving-block bootstrap on development daily portfolio returns; small samples and multiple dependent strategies limit inference.'}


def select_on_development(development,halves,plan):
    baseline=development['baseline'];decisions={};eligible=[]
    for name,candidate in development.items():
        if name=='baseline':continue
        ci=bootstrap_excess(candidate,baseline,plan,len(development)-1)
        sharpe=candidate['daily_sharpe_annualized'];base_sharpe=baseline['daily_sharpe_annualized']
        gates={'enough_development_trades':candidate['trades_count']>=plan['minimum_development_trades'],
               'enough_trades_in_both_development_halves':all(x['trades_count']>=plan['minimum_subperiod_trades'] for x in halves[name]),
               'positive_net_expectancy':candidate['expectancy_pct'] is not None and candidate['expectancy_pct']>0,
               'portfolio_return_improves':candidate['portfolio_return_pct']>baseline['portfolio_return_pct'],
               'daily_sharpe_improves':sharpe is not None and base_sharpe is not None and sharpe>base_sharpe,
               'drawdown_not_materially_worse':abs(candidate['maximum_drawdown_pct'])<=abs(baseline['maximum_drawdown_pct'])*1.05,
               'adjusted_excess_return_confidence_positive':ci['lower_mean_daily_excess_pct'] is not None and ci['lower_mean_daily_excess_pct']>0,
               'both_development_halves_profitable':all(x['portfolio_return_pct']>0 for x in halves[name])}
        decisions[name]={'gates':gates,'confidence_interval':ci,'qualifies_for_prospective_validation':all(gates.values())}
        if all(gates.values()):eligible.append(name)
    candidate=max(eligible,key=lambda x:development[x]['daily_sharpe_annualized']) if eligible else None
    return {'selected_on_development_only':candidate,'candidates':decisions,'live_strategy':'baseline','adopted':False,
            'reason':'No qualified development candidate; retain original.' if not candidate else 'Candidate requires new genuinely unseen prospective trades; historical reused holdout cannot authorize adoption.',
            'historical_holdout_was_previously_exposed':True,'new_unseen_trade_count':0,'required_new_unseen_trades':plan['minimum_new_unseen_test_trades']}


def diagnose_trades(trades,signals,contexts,prepared,histories,sessions):
    bykey={(symbol,r['date']):r for rows in signals.values() for symbol,r in rows};rows=[]
    for t in trades:
        key=(t['symbol'],t['signal_date']);r=bykey[key];ctx=contexts[key];d=histories[t['symbol']]
        entry=pd.Timestamp(t['entry_date']);exitdate=pd.Timestamp(t['exit_date']);idx=sessions.get_loc(entry)
        window=sessions[idx:idx+20];window=window[window<=pd.Timestamp('2026-10-21')]
        observed=d.reindex(window);q=set(d.attrs.get('quarantine',[]));observed=observed[[str(x.date()) not in q for x in observed.index]].dropna()
        trigger=r['scenario']['trigger'] if ctx['signal_price_breakout'] else r['observations']['ema20']
        first3=observed.reindex(window[:3]).dropna();failed=bool(trigger and not first3.empty and (first3['Close']<trigger).any())
        during=observed.loc[:exitdate];atr=ctx['atr_at_signal'];width=(t['entry_price']-t['stop'])/atr
        late=not ctx['anti_chase_pass'];tags=[]
        if failed:tags.append('breakout_failed_within_3_sessions' if ctx['signal_price_breakout'] else 'ema_reclaim_failed_within_3_sessions')
        if late:tags.append('extended_or_chased_at_signal')
        if not ctx['market_trend_pass']:tags.append('weak_TASI_trend_at_signal')
        if not ctx['sector_data_available']:tags.append('sector_proxy_unavailable')
        elif not ctx['sector_strength_pass']:tags.append('weak_sector_relative_strength_at_signal')
        if width<1.5:tags.append('stop_distance_below_1_5_ATR')
        if t['exit_reason'].startswith('gap_stop'):tags.append('gap_through_stop')
        recovery=observed[observed.index>exitdate]
        rows.append({**t,**ctx,'stop_distance_atr_at_entry':width,'stop_distance_pct_at_entry':100*(t['entry_price']-t['stop'])/t['entry_price'],
                     'posthoc_failed_breakout_or_reclaim':failed,'posthoc_failed_breakout':failed and ctx['signal_price_breakout'],
                     'maximum_favorable_excursion_through_exit_bar_pct':100*(during['High'].max()/t['entry_price']-1) if len(during) else None,
                     'maximum_adverse_excursion_through_exit_bar_pct':100*(during['Low'].min()/t['entry_price']-1) if len(during) else None,
                     'post_exit_high_reached_target_in_original_20_session_window':bool(len(recovery) and (recovery['High']>=t['target']).any()),
                     'diagnostic_tags':tags,'interpretation':'Tags are associations, not proven causal explanations. Post-entry diagnostics are never used by filters. Excursions include the exit bar; intraday path is unknown.'})
    tags=sorted({tag for r in rows for tag in r['diagnostic_tags']});groups={}
    for tag in tags:
        selected=[r for r in rows if tag in r['diagnostic_tags']];other=[r for r in rows if tag not in r['diagnostic_tags']]
        groups[tag]={'trades':len(selected),'losers':sum(r['net_return_pct']<=0 for r in selected),'winners':sum(r['net_return_pct']>0 for r in selected),
                    'mean_net_return_pct':float(np.mean([r['net_return_pct'] for r in selected])),
                    'other_trades':len(other),'other_mean_net_return_pct':float(np.mean([r['net_return_pct'] for r in other])) if other else None}
    return {'count':len(rows),'winners':sum(r['net_return_pct']>0 for r in rows),'losers':sum(r['net_return_pct']<=0 for r in rows),
            'exit_reason_counts':dict(Counter(r['exit_reason'] for r in rows)),'associations':groups,'trades':rows,
            'note':'All 25 trades, winners and losers. Diagnostics on the known historical test are descriptive and cannot make it an unseen test again.'}


def assert_baseline_reproduction(computed,frozen):
    for key in ('trades_count','win_rate_pct','average_win_pct','average_loss_pct','expectancy_pct','portfolio_return_pct','maximum_drawdown_pct','tasi_buy_hold_net_return_pct'):
        a,b=computed[key],frozen[key]
        assert (a is None and b is None) or abs(a-b)<2e-5,'Baseline mismatch: '+key
    assert len(computed['trades'])==len(frozen['trades'])==25
    for a,b in zip(computed['trades'],frozen['trades']):
        for k in ('symbol','signal_date','entry_date','exit_date','exit_reason'):assert a[k]==b[k],('Baseline trade mismatch',k,a,b)
        for k in ('entry_price','exit_price','stop','target','net_return_pct'):assert abs(a[k]-b[k])<2e-5,(k,a,b)


def report_markdown(report):
    lines=['# Phase 3 comparison — research only','',f"Frozen input run: {report['frozen_run_id']}; research run: {report['run_url']}",'',
           '**Decision: keep the original live strategy. No new rule has been deployed.**','',
           'All variants use identical frozen inputs, dates, execution rules and costs. The reused historical holdout is not virgin out-of-sample evidence.','',
           'Development: '+report['split']['development_start']+' through '+report['split']['development_end']+'; 20-session purge; reused temporal test: '+report['split']['test_start']+' through '+report['split']['test_end']+'.','']
    for section in ('full_period','development','reused_temporal_test'):
        lines += ['## '+section,'','| Variant | Trades | Win % | Mean win % | Mean loss % | Expectancy % | Portfolio % | Max daily DD % | Daily Sharpe |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for name,data in report['variants'].items():
            r=data[section];vals=[r[k] for k in ('trades_count','win_rate_pct','average_win_pct','average_loss_pct','expectancy_pct','portfolio_return_pct','maximum_drawdown_pct','daily_sharpe_annualized')]
            lines.append('| '+name+' | '+' | '.join('NA' if v is None else str(round(v,3)) for v in vals)+' |')
        lines.append('')
    lines += ['## Interpretation','',report['selection']['reason'],'',
              'At least 30 development trades and 20 new unseen test trades are required by the registered governance gates. A higher win rate alone is insufficient. Sector strength uses an unofficial leave-target-out basket; current-universe and adjusted-history biases remain. Costs assume 15.5 bps commission + 5 bps slippage each side, no taxes. Stops cannot guarantee loss limits across gaps.','',
              'Loss associations and every original trade are in trade_diagnostics.json/.csv. Source checks are in quality_recheck.json. These audits never retrospectively change the frozen comparison inputs.']
    return '\n'.join(lines)+'\n'


def run(root,output,plan_path,universe_path):
    plan=json.loads(Path(plan_path).read_text());histories,bench,sessions,cfg,latest,frozen=load_snapshot(root)
    assert frozen['full_period']['trades_count']==25
    universe=pd.read_csv(universe_path,dtype={'symbol':str});assert len(universe)==254
    dates=sessions[(sessions>=pd.Timestamp(plan['evaluation_start']))&(sessions<=pd.Timestamp(plan['evaluation_end']))]
    test=dates[dates>=pd.Timestamp(plan['test_start'])];before=dates[dates<test[0]];dev=before[:-plan['purge_sessions']];purge=before[-plan['purge_sessions']:]
    assert len(purge)==20 and dev[-1]<purge[0]<test[0]
    print('Reconstructing causal baseline signals',flush=True);signals,prepared=causal_signals(histories,bench,sessions,cfg)
    proxy=SectorProxy(histories,universe,sessions,plan['sector_proxy']);variants,contexts,rejected=make_variants(signals,prepared,bench,proxy,plan)
    def evaluate(name,period):return add_metrics(simulate(histories,variants[name],bench,period,cfg,plan,risk_sized=name.startswith('stop_')))
    # Selection is locked from DEVELOPMENT ONLY before any candidate test/full results are evaluated.
    development={name:evaluate(name,dev) for name in variants}
    halves={name:[evaluate(name,dev[:len(dev)//2]),evaluate(name,dev[len(dev)//2:])] for name in variants}
    selection=select_on_development(development,halves,plan)
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    dump=lambda path,value:path.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False))
    dump(out/'selection_lock.json',{'plan_sha256':digest(plan_path),'selection':selection,'development_end':str(dev[-1].date()),'test_start':str(test[0].date()),'created_before_candidate_test_evaluation':True})
    results={name:{'development':development[name],'development_halves':halves[name],
                   'full_period':evaluate(name,dates),'reused_temporal_test':evaluate(name,test),'signal_rejections':rejected[name]} for name in variants}
    assert_baseline_reproduction(results['baseline']['full_period'],frozen['full_period'])
    diagnostics=diagnose_trades(frozen['full_period']['trades'],signals,contexts,prepared,histories,sessions)
    run_id=os.getenv('GITHUB_RUN_ID','local');url=f'https://github.com/saqerkhalel-gif/tasi-radar-3/actions/runs/{run_id}' if run_id!='local' else None
    report={'schema_version':1,'run_id':run_id,'run_url':url,'source_commit':os.getenv('GITHUB_SHA'),'frozen_run_id':latest['run_id'],
            'preregistered_plan_commit':'25e6e4d1a39e81cf61bdb891acd717671203b608','plan_sha256':digest(plan_path),'universe_sha256':digest(universe_path),
            'input_hashes':frozen['data_hashes'],'benchmark_sha256':hashlib.sha256(bench.to_csv().encode()).hexdigest(),
            'frozen_baseline_reproduced':True,'cost_model':frozen['cost_model'],
            'split':{'development_start':str(dev[0].date()),'development_end':str(dev[-1].date()),'purge_start':str(purge[0].date()),'purge_end':str(purge[-1].date()),'purge_sessions':20,'test_start':str(test[0].date()),'test_end':str(test[-1].date()),'test_previously_exposed':True},
            'selection':selection,'variants':results,'diagnostic_summary':{k:v for k,v in diagnostics.items() if k!='trades'},
            'limitations':plan['limitations']+['All ablations filter original eligible signals; they do not invent unconfirmed retest entries or relax price/volume gates.','Bootstrap intervals are descriptive under a small, dependent sample; no statistical certainty is claimed.','The 20-session development gap prevents trades/outcomes overlapping the test boundary. Histories before the boundary remain available as causal indicator warmup.']}
    for doc in (diagnostics,):doc.update(run_id=run_id,run_url=url,frozen_run_id=latest['run_id'])
    dump(out/'comparison.json',report);dump(out/'trade_diagnostics.json',diagnostics)
    dump(out/'baseline_signals.json',{str(k.date()):rows for k,rows in signals.items()})
    pd.DataFrame(diagnostics['trades']).to_csv(out/'trade_diagnostics.csv',index=False)
    rows=[]
    for name,sections in results.items():
        for section in ('development','full_period','reused_temporal_test'):
            rows.append({'variant':name,'period':section,**{k:v for k,v in sections[section].items() if k not in ('trades','equity_curve','skipped_orders')}})
    pd.DataFrame(rows).to_csv(out/'comparison.csv',index=False)
    (out/'REPORT.md').write_text(report_markdown(clean(report)))
    print(json.dumps(clean({'run_id':run_id,'split':report['split'],'selection':selection,'full_period':{n:{k:r['full_period'][k] for k in ('trades_count','win_rate_pct','portfolio_return_pct','maximum_drawdown_pct')} for n,r in results.items()}})),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',default='output/phase3/current');p.add_argument('--plan',default='phase3/plan.json');p.add_argument('--universe',default='data/tasi_symbols.csv');a=p.parse_args()
    run(a.snapshot,a.output,a.plan,a.universe)
