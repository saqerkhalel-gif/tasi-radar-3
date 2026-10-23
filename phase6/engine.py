"""Deterministic event-sourced paper books. Decisions and fills are separate events."""
from __future__ import annotations
import math
from datetime import datetime,timezone
from phase6.calendar import open_utc,next_session
from phase6.quality import cross_source
from phase3.quality_recheck import valid_daily_row
from phase6.ledger import sha

TERMINAL={'REJECTED','NOT_EXECUTABLE','CLOSED','TIMED_OUT','DATA_UNVERIFIABLE'}

def project(events,protocol):
    books={name:{'cash':protocol['initial_capital_per_strategy'],'positions':{},'trades':[],'curve':[],'invalid':False} for name in protocol['strategies']}
    candidates={}
    for e in events:
        p=e['payload'];kind=e['kind']
        if kind=='PREDICTION_RECORDED':candidates[e['event_id']]={**p,'id':e['event_id'],'status':'PENDING'}
        elif kind in ('REJECTED','NOT_EXECUTABLE'):
            if p['prediction_id'] in candidates:candidates[p['prediction_id']]['status']=kind;candidates[p['prediction_id']]['outcome_reason']=p['reason']
        elif kind=='OPENED':
            c=candidates[p['prediction_id']];c.update(status='OPEN',entry=p)
            book=books[c['strategy']];book['cash']-=p['cash_spent'];book['positions'][c['id']]={**p,'prediction':c,'mark':p['raw_entry_price']}
        elif kind in ('CLOSED','TIMED_OUT'):
            c=candidates[p['prediction_id']];c.update(status=kind,exit=p)
            book=books[c['strategy']];book['cash']+=p['cash_received'];book['positions'].pop(c['id'],None);book['trades'].append({**c,'entry':c['entry'],'exit':p})
        elif kind=='DATA_UNVERIFIABLE':
            c=candidates[p['prediction_id']];c['status']=kind;c['outcome_reason']=p['reason'];books[c['strategy']]['invalid']=True
        elif kind in ('MARKED','OPEN_MARKED'):
            book=books[p['strategy']]
            for key,mark in p['marks'].items():
                if key in book['positions']:book['positions'][key]['mark']=mark
            if kind=='MARKED':book['curve'].append(p)
    # A later revision also invalidates previously closed records, never erases their events.
    for book in books.values():
        book['trades']=[{**t,'status':candidates[t['id']]['status']} for t in book['trades']]
    return candidates,books

def levels_ok(price,stop,target,p):
    if not all(isinstance(x,(float,int)) and math.isfinite(x) for x in (price,stop,target)):return False
    return (0<stop<price<target and 100*(target/price-1)>=p['minimum_upside_pct']-1e-8
            and (target-price)/(price-stop)>=p['minimum_reward_risk']-1e-8
            and 100*(price-stop)/price<=p['maximum_stop_distance_pct']+1e-8)

def risk_size(book,raw_open,stop,p):
    slip=p['slippage_bps_per_side']/10000;commission=p['commission_bps_per_side']/10000
    fill=raw_open*(1+slip);unit_cost=fill*(1+commission);equity=book['cash']+sum(v['quantity']*v['mark'] for v in book['positions'].values())
    risk_share=unit_cost-stop*(1-slip)*(1-commission)
    existing=sum(v['planned_risk_cash'] for v in book['positions'].values())
    allowed=min(equity*p['maximum_planned_risk_per_trade_pct']/100,max(0,equity*p['maximum_aggregate_planned_risk_pct']/100-existing))
    budget=min(book['cash'],equity*p['maximum_position_pct']/100)
    qty=math.floor(max(0,min(budget/unit_cost,allowed/risk_share))) if risk_share>0 else 0
    return {'quantity':qty,'entry_fill_price':fill,'cash_spent':qty*unit_cost,'planned_risk_cash':qty*risk_share,'equity_at_entry':equity,'aggregate_planned_risk_cash':existing+qty*risk_share}

def exit_rule(bar,stop,target):
    if bar['Open']<=stop:return bar['Open'],'gap_through_stop'
    if bar['Open']>=target:return target,'gap_target_capped'
    if bar['Low']<=stop:return stop,'stop_first_daily_ambiguity' if bar['High']>=target else 'stop'
    if bar['High']>=target:return target,'target'
    return None,None

def prediction(ledger,key,record,source,quality,version,now,cfg,protocol):
    """The entire original hypothesis is immutable, even if rejected."""
    strategy=record['strategy'];symbol=record['symbol'];scenario=record['scenario'];reasons=[]
    if not quality.get('signal_eligible'):reasons.extend(quality.get('eligibility_reasons',['signal_history_unverified']))
    obs=record.get('observations',{});price=float(record['close'])
    if not obs.get('price_confirmed'):reasons.append('price_not_confirmed')
    if float(obs.get('volume_ratio') or 0)<1.5:reasons.append('volume_below1.5x')
    if not levels_ok(price,scenario['invalidation'],scenario['conditional_target'],protocol):reasons.append('signal_target_or_risk_invalid')
    payload={**record,'strategy_version':version,'source_run_id':source['run_id'],'source_commit':source['head_sha'],'session':source['expected_session'],
      'session_timezone':'Asia/Riyadh','session_close_utc':source['session_close_utc'],'signal_recorded_utc':now,
      'next_execution_session':next_session(source['expected_session'],cfg),'entry_rule':'Only next-session independently corroborated raw open, after prior timestamped signal; no late entry',
      'eligibility':quality,'pre_execution_rejections':sorted(set(reasons)),'production_order_authorized':False,
      'label':record.get('production_classification') if strategy=='production_radar' else 'SHADOW_HYPOTHESIS'}
    ledger.append(key,'PREDICTION_RECORDED',payload,now,record.get('object_refs',[]))
    if reasons:ledger.append('reject:'+key,'REJECTED',{'prediction_id':key,'reason':';'.join(sorted(set(reasons)))},now)
    return not reasons

def advance(ledger,date,raws,references,protocol,cfg,now):
    """Only the current genuinely observed session; never replay unseen historical opens."""
    candidates,books=project(ledger.events,protocol);commission=protocol['commission_bps_per_side']/10000;slip=protocol['slippage_bps_per_side']/10000
    for strategy,book in books.items():
        if 'mark:'+strategy+':'+date in ledger.ids:continue
        opening_marks={}
        last=next((e['payload']['session'] for e in reversed(ledger.events) if e['kind']=='MARKED' and e['payload']['strategy']==strategy),None)
        for key,pos in book['positions'].items():
            if candidates[key]['status']=='DATA_UNVERIFIABLE':continue
            r=raws.get(pos['prediction']['symbol']);reason=None
            if last and date!=next_session(last,cfg):reason='missing_observed_holding_session'
            elif not r or not valid_daily_row(r.get('ohlcv',{}))[0]:reason='invalid_or_missing_holding_OHLCV'
            elif not any(cross_source(r,x) for x in references):reason='holding_bar_not_independently_corroborated'
            elif r.get('dividend') or r.get('split'):reason='capital_action_requires_reconciliation'
            if reason:ledger.append('unverifiable:'+key+':'+date,'DATA_UNVERIFIABLE',{'prediction_id':key,'session':date,'reason':reason},now)
            else:opening_marks[key]=r['ohlcv']['Open']
        if opening_marks:ledger.append('opening-marks:'+strategy+':'+date,'OPEN_MARKED',{'strategy':strategy,'session':date,'marks':opening_marks},now)
    candidates,books=project(ledger.events,protocol)
    for key,c in sorted(candidates.items(),key=lambda x:(x[1]['strategy'],x[1].get('rank',0),x[1]['symbol'])):
        if c['status']!='PENDING' or date<c['next_execution_session'] or 'mark:'+c['strategy']+':'+date in ledger.ids:continue
        reason=None;r=raws.get(c['symbol'])
        if date!=c['next_execution_session']:reason='missing_first_seen_execution_session'
        elif datetime.fromisoformat(c['signal_recorded_utc'])>=open_utc(date):reason='prediction_recorded_after_execution_open'
        elif not r or not valid_daily_row(r.get('ohlcv',{}))[0]:reason='missing_invalid_or_zero_volume_open'
        elif not any(cross_source(r,ref) for ref in references):reason='open_lacks_independent_dated_corroboration'
        elif r.get('dividend') or r.get('split'):reason='capital_action_unverified'
        book=books[c['strategy']];stop=c['scenario']['invalidation'];target=c['scenario']['conditional_target']
        if not reason:
            fill=r['ohlcv']['Open']*(1+slip)
            if not levels_ok(fill,stop,target,protocol):reason='next_open_fails10pct_RR2_or_stop_cap'
            elif book['invalid']:reason='portfolio_has_unverifiable_outcome'
            elif len(book['positions'])>=protocol['maximum_positions'] or any(x['prediction']['symbol']==c['symbol'] for x in book['positions'].values()):reason='position_limit_or_duplicate_position'
        if reason:
            ledger.append('not-executable:'+key,'NOT_EXECUTABLE',{'prediction_id':key,'session':date,'reason':reason},now);continue
        size=risk_size(book,r['ohlcv']['Open'],stop,protocol)
        if size['quantity']<1:ledger.append('not-executable:'+key,'NOT_EXECUTABLE',{'prediction_id':key,'session':date,'reason':'risk_or_cash_budget_exhausted'},now);continue
        payload={'prediction_id':key,'session':date,'raw_entry_price':r['ohlcv']['Open'],'raw_bar_hash':sha(r),'commission_bps':protocol['commission_bps_per_side'],'slippage_bps':protocol['slippage_bps_per_side'],**size}
        ledger.append('open:'+key,'OPENED',payload,now)
        candidates,books=project(ledger.events,protocol)
    # Process same-day stops after openings, conservatively stop first; existing positions may not skip a session.
    candidates,books=project(ledger.events,protocol)
    for strategy,book in books.items():
        if 'mark:'+strategy+':'+date in ledger.ids:continue
        for key,pos in list(book['positions'].items()):
            c=pos['prediction']
            if c['status']=='DATA_UNVERIFIABLE':continue
            last_mark=next((e['payload']['session'] for e in reversed(ledger.events) if e['kind']=='MARKED' and e['payload']['strategy']==strategy),None)
            expected=pos['session'] if last_mark is None else next_session(last_mark,cfg)
            if pos['session']==date:expected=date
            r=raws.get(c['symbol']);reason=None
            if date!=expected:reason='missing_observed_holding_session'
            elif not r or not valid_daily_row(r.get('ohlcv',{}))[0]:reason='invalid_or_missing_holding_OHLCV'
            elif not any(cross_source(r,ref) for ref in references):reason='holding_bar_not_independently_corroborated'
            elif r.get('dividend') or r.get('split'):reason='capital_action_requires_reconciliation'
            if reason:
                ledger.append('unverifiable:'+key+':'+date,'DATA_UNVERIFIABLE',{'prediction_id':key,'session':date,'reason':reason},now);continue
            price,why=exit_rule(r['ohlcv'],c['scenario']['invalidation'],c['scenario']['conditional_target'])
            # Count real recorded sessions only; a missing session already freezes the outcome above.
            age=1+sum(e['kind']=='MARKED' and e['payload']['strategy']==strategy and key in e['payload']['marks'] for e in ledger.events)
            kind='CLOSED'
            if price is None and age>=protocol['maximum_hold_sessions']:price=r['ohlcv']['Close'];why='maximum_hold_sessions';kind='TIMED_OUT'
            if price is not None:
                fill=price*(1-slip);received=pos['quantity']*fill*(1-commission)
                stress=protocol['stress_slippage_bps_per_side']/10000
                stress_cost=pos['quantity']*pos['raw_entry_price']*(1+stress)*(1+commission);stress_received=pos['quantity']*price*(1-stress)*(1-commission)
                ledger.append('close:'+key,kind,{'prediction_id':key,'session':date,'raw_exit_price':price,'exit_fill_price':fill,'cash_received':received,'net_pnl':received-pos['cash_spent'],
                  'net_return_pct':100*(received/pos['cash_spent']-1),'stress_net_return_pct':100*(stress_received/stress_cost-1),'stress_net_pnl':stress_received-stress_cost,'reason':why,
                  'holding_sessions':age,'daily_intrabar_path_known':False,'exit_bar_hash':sha(r)},now)
        candidates,updated=project(ledger.events,protocol);b=updated[strategy]
        marks={key:raws[pos['prediction']['symbol']]['ohlcv']['Close'] for key,pos in b['positions'].items() if candidates[key]['status']!='DATA_UNVERIFIABLE' and pos['prediction']['symbol'] in raws}
        invalid=b['invalid'];nav=None if invalid else b['cash']+sum(pos['quantity']*marks.get(key,pos['mark']) for key,pos in b['positions'].items())
        exposure=None if invalid or not nav else 100*sum(pos['quantity']*marks.get(key,pos['mark']) for key,pos in b['positions'].items())/nav
        ledger.append('mark:'+strategy+':'+date,'MARKED',{'strategy':strategy,'session':date,'marks':marks,'nav':nav,'exposure_pct':exposure,'valid':not invalid},now)
