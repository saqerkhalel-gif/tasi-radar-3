"""Phase5 harmonized execution model: invalid/zero-volume bar refusal and exposure/turnover. Same original semantics; aggregate admission-risk metric excludes rejected zero-budget orders. Caps apply at order admission, not continuously as NAV changes. Gaps can exceed stop risk."""
from collections import Counter
import numpy as np
from research import trade_exit
from phase3.quality_recheck import valid_daily_row

def simulate(data,signals,benchmark,dates,cfg,plan=None,risk_sized=False):
    bt=cfg.get('backtest',{});cost=(bt.get('commission_bps_per_side',15.5)+bt.get('slippage_bps_per_side',5))/10000
    slots=bt.get('max_positions',10);hold=bt.get('max_hold_sessions',20)
    cash=100000.;positions={};trades=[];curve=[];skipped=Counter();marks_stale=0;max_planned_risk_pct=0;turnover_cash=0.;exposure_curve=[]
    def close_position(symbol,price,date,reason):
        nonlocal cash,turnover_cash
        p=positions.pop(symbol);turnover_cash+=p['quantity']*price;cash+=p['quantity']*price*(1-cost)
        net=price*(1-cost)/(p['entry_price']*(1+cost))-1
        trades.append({k:v for k,v in p.items() if k not in ('quantity','last_mark','age') }|{'exit_date':str(date.date()),'exit_price':price,'exit_reason':reason,'net_return_pct':100*net})
    for date in dates:
        # Signals are from the preceding calendar session, never this day's close.
        for symbol,record in sorted(signals.get(date,[]),key=lambda x:(-x[1]['technical_score'],x[0])):
            if symbol in positions or len(positions)>=slots:continue
            bar=data[symbol].loc[date] if date in data[symbol].index else None
            if bar is None:skipped['missing_execution_bar']+=1;continue
            if str(date.date()) in data[symbol].attrs.get('quarantine',[]):skipped['quarantined_execution_bar']+=1;continue
            if not valid_daily_row(bar)[0]:skipped['invalid_or_zero_volume_execution_bar']+=1;continue
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
                risk_details={'planned_risk_cash':planned,'same_signal_baseline_risk_cash':base_risk,'equity_at_entry':equity}
            if budget<1:continue
            if risk_sized:max_planned_risk_pct=max(max_planned_risk_pct,100*(existing+planned)/equity)
            quantity=budget/(price*(1+cost));cash-=budget;turnover_cash+=quantity*price
            positions[symbol]={'symbol':symbol,'signal_date':record['date'],'entry_date':str(date.date()),'entry_price':price,'quantity':quantity,
                               'stop':stop,'target':target,'age':0,'last_mark':price,'signal_score':record['technical_score'],**risk_details}
        for symbol,p in list(positions.items()):
            df=data[symbol]
            if date not in df.index or str(date.date()) in df.attrs.get('quarantine',[]):
                marks_stale+=1;p['age']+=1;continue
            bar=df.loc[date]
            if not valid_daily_row(bar)[0]:marks_stale+=1;p['age']+=1;continue
            p['age']+=1;p['last_mark']=float(bar['Close'])
            price,reason=trade_exit(bar,p['stop'],p['target'])
            if price is None and p['age']>=hold:price=float(bar['Close']);reason='time_exit'
            if price is not None:close_position(symbol,price,date,reason)
        total=cash+sum(p['quantity']*p['last_mark'] for p in positions.values())
        exposure_curve.append({'date':str(date.date()),'gross_exposure_pct':100*sum(p['quantity']*p['last_mark'] for p in positions.values())/total if total else 0})
        curve.append({'date':str(date.date()),'equity':cash+sum(p['quantity']*p['last_mark'] for p in positions.values())})
    unliquidated=0
    if len(dates):
        last=dates[-1]
        for symbol,p in list(positions.items()):
            if last in data[symbol].index and str(last.date()) not in data[symbol].attrs.get('quarantine',[]) and valid_daily_row(data[symbol].loc[last])[0]:close_position(symbol,float(data[symbol].loc[last,'Close']),last,'end_of_test')
            else:unliquidated+=1
        curve[-1]['equity']=cash+sum(p['quantity']*p['last_mark'] for p in positions.values())
    values=np.array([100000.]+[x['equity'] for x in curve]);peak=np.maximum.accumulate(values)
    wins=[t['net_return_pct'] for t in trades if t['net_return_pct']>0];loss=[t['net_return_pct'] for t in trades if t['net_return_pct']<=0]
    netreturn=100*(values[-1]/100000-1)
    valid=bool(len(dates)>1 and benchmark is not None and dates.isin(benchmark.index).all() and not unliquidated and marks_stale==0 and benchmark.attrs.get('historical_integrity_ok',True))
    bm=100*(benchmark.loc[dates[-1],'Close']*(1-cost)/(benchmark.loc[dates[0],'Close']*(1+cost))-1) if valid else None
    return {'start_date':str(dates[0].date()) if len(dates) else None,'end_date':str(dates[-1].date()) if len(dates) else None,
            'trades_count':len(trades),'win_rate_pct':100*len(wins)/len(trades) if trades else None,
            'average_win_pct':float(np.mean(wins)) if wins else None,'average_loss_pct':float(np.mean(loss)) if loss else None,
            'expectancy_pct':float(np.mean([t['net_return_pct'] for t in trades])) if trades else None,
            'portfolio_return_pct':netreturn,'maximum_drawdown_pct':float(100*np.min(values/peak-1)),
            'tasi_buy_hold_net_return_pct':bm,'excess_return_pct_points':netreturn-bm if bm is not None else None,
            'turnover_pct_initial_nav':100*turnover_cash/100000,'mean_gross_exposure_pct':float(np.mean([x['gross_exposure_pct'] for x in exposure_curve])) if exposure_curve else 0,'exposure_curve':exposure_curve,'comparison_valid':valid,'unliquidated_positions':unliquidated,'stale_mark_position_days':marks_stale,
            'skipped_orders':dict(skipped),'trades':trades,'equity_curve':curve,'maximum_aggregate_planned_risk_pct':max_planned_risk_pct if risk_sized else None}
