"""Derived, reproducible forward projections. No historical folds relabelled as unseen."""
import json,math,os
from pathlib import Path
import numpy as np
import pandas as pd
from phase5.evaluate import wilson
from phase6.engine import project
from phase6.ledger import derived,write_exclusive,sha

def overlap_clusters(trades):
    intervals=sorted((t['entry']['session'],t['exit']['session']) for t in trades);clusters=0;end=''
    for start,finish in intervals:
        if start>end:clusters+=1
        end=max(end,finish)
    return clusters

def make_reports(ledger,quality,protocol,output,run_info):
    out=Path(output);current=out/'current';current.mkdir(parents=True,exist_ok=True)
    candidates,books=project(ledger.events,protocol)
    sessions=[e['payload'] for e in ledger.events if e['kind']=='SESSION_RECORDED']
    audit=[e for e in ledger.events if e['kind']=='SOURCE_AUDIT_ONLY']
    rows=[];details={}
    for strategy,book in books.items():
        allc=[c for c in candidates.values() if c['strategy']==strategy]
        totalclosed=book['trades'];trades=[t for t in totalclosed if t['status'] in ('CLOSED','TIMED_OUT')]
        returns=[t['exit']['net_return_pct'] for t in trades];stress=[t['exit']['stress_net_return_pct'] for t in trades];wins=[x for x in returns if x>0];losses=[x for x in returns if x<=0]
        positive=sum(max(0,t['exit']['net_pnl']) for t in trades);negative=-sum(min(0,t['exit']['net_pnl']) for t in trades)
        curve=book['curve'];valid=bool(curve and not book['invalid'] and all(x['valid'] and x['nav'] is not None for x in curve))
        nav=np.array([protocol['initial_capital_per_strategy']]+[x['nav'] for x in curve]) if valid else None
        dd=float(100*np.min(nav/np.maximum.accumulate(nav)-1)) if valid else None
        equity_return=float(100*(nav[-1]/nav[0]-1)) if valid else None
        turnover=sum(c.get('entry',{}).get('quantity',0)*c.get('entry',{}).get('raw_entry_price',0) for c in allc)+sum(t['entry']['quantity']*t['exit']['raw_exit_price'] for t in totalclosed)
        byregime={}
        for t in trades:byregime.setdefault(t.get('entry_context',{}).get('market_regime','UNKNOWN'),[]).append(t['exit']['net_return_pct'])
        gap=[t for t in trades if t['exit']['reason']=='gap_through_stop']
        row={'strategy':strategy,'signal_count':len(allc),'eligible_signals':sum(not c['pre_execution_rejections'] for c in allc),
          'new_openings_this_session':sum(c.get('entry',{}).get('session')==quality['price_session'] for c in allc),'opened_total':sum('entry' in c for c in allc),
          'completed_total_including_disputed':len(totalclosed),'completed_valid':len(trades),'wins':len(wins),'losses':len(losses),
          'win_rate_pct':100*len(wins)/len(returns) if returns else None,'wilson95':wilson(len(wins),len(returns)),
          'net_expectancy_pct':float(np.mean(returns)) if returns else None,'average_gain_pct':float(np.mean(wins)) if wins else None,'average_loss_pct':float(np.mean(losses)) if losses else None,
          'profit_factor_cash':positive/negative if negative>0 else None,'payoff_ratio':abs(np.mean(wins)/np.mean(losses)) if wins and losses and np.mean(losses)!=0 else None,
          'net_portfolio_return_pct':equity_return,'maximum_drawdown_pct':dd,'mean_exposure_pct':float(np.mean([x['exposure_pct'] for x in curve])) if valid else None,
          'turnover_pct_initial_nav':100*turnover/protocol['initial_capital_per_strategy'],'average_holding_sessions':float(np.mean([t['exit']['holding_sessions'] for t in trades])) if trades else None,
          'stress_net_expectancy_pct':float(np.mean(stress)) if stress else None,'gap_stop_losses':sum(t['exit']['net_pnl']<0 for t in gap),'gap_stop_pnl':sum(t['exit']['net_pnl'] for t in gap),
          'pending':sum(c['status']=='PENDING' for c in allc),'not_executable':sum(c['status']=='NOT_EXECUTABLE' for c in allc),'rejected':sum(c['status']=='REJECTED' for c in allc),
          'data_unverifiable':sum(c['status']=='DATA_UNVERIFIABLE' for c in allc),'open_positions':len(book['positions']),'portfolio_valuation_valid':valid,
          'overlapping_time_clusters':overlap_clusters(trades),'independence_established':False,
          'performance_by_market_regime':{k:{'count':len(v),'net_expectancy_pct':float(np.mean(v)),'win_rate_pct':100*sum(x>0 for x in v)/len(v)} for k,v in byregime.items()},
          'target100_completed_reached':len(trades)>=100,'decision':'KEEP_SHADOW','adopted':False}
        rows.append(row);details[strategy]={'summary':row,'predictions':allc,'trades':totalclosed,'equity_observations':curve}
    # An index-close reference is reported only if every new sealed session has an independently corroborated close.
    closes=[x.get('benchmark',{}) for x in sessions];bm=None
    if len(closes)>=2 and all(x.get('independently_corroborated') and x.get('close',0)>0 for x in closes):
        commission=protocol['commission_bps_per_side']/10000;slip=protocol['slippage_bps_per_side']/10000
        bm=100*(closes[-1]['close']*(1-slip)*(1-commission)/(closes[0]['close']*(1+slip)*(1+commission))-1)
    manifest=ledger.manifest()
    snapshot={'schema_version':1,**run_info,'prospective_session_count':len(sessions),'audit_only_snapshots':len(audit),'last_real_session':sessions[-1]['session'] if sessions else None,
      'data_denominators':quality['denominators'],'strategies':rows,'ledger':manifest,'benchmark':{'net_close_to_close_return_pct':bm,'valid':bm is not None,'note':'Price-index reference from first sealed forward close; portfolios wait for next verifiable open. Not a tradable index fund or total-return dividend series.'},
      'historical_results':'Phase4/5 reused2026 studies remain separate; no phase6 historical result labelled untouched.',
      'decision':{'status':'KEEP_SHADOW','automatic_promotion':False,'independent_evidence_established':False,'completed_target':100,
        'blockers':['Independent full-history provenance and benchmark validation incomplete.','At least100 reasonably independent forward completions across diverse regimes required; count alone insufficient.','Missing/disputed outcomes and correlated exposures must be resolved; positive base/stress net expectancy and robust risk-adjusted comparison are unproved.']},
      'acceptance':{'pipeline_completed':True,'real_scheduled_session_observed':bool(sessions),'new_forward_snapshot_present':bool(sessions),'production_schedule_changed':False,'strategies_promoted':False},
      'chatgpt_automation_integration':'NOT_TESTED; no second task or delivery channel created.',
      'immutability':'Application append-only; verifiable hash chain, retained source objects and Git/artifact anchors. Owner-proof WORM and external anchor retention are not configured.'}
    derived(current/'summary.json',snapshot);derived(current/'strategies.json',details);derived(current/'DATA_QUALITY.json',quality)
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in rows]).to_csv(current/'strategies.csv',index=False)
    pd.DataFrame(quality['symbols']).to_csv(current/'OHLCV_ELIGIBILITY.csv',index=False)
    pd.json_normalize(ledger.events).to_csv(current/'ledger_events.csv',index=False)
    revisions=[e for e in ledger.events if 'REVISION' in e['kind'] or e['kind'] in ('DATA_UNVERIFIABLE','OPERATIONAL_FAILURE')]
    derived(current/'data_revisions.json',{'events':revisions})
    latestday=sessions[-1]['session'] if sessions else None
    production=[]
    for c in candidates.values():
        if c['id'] in run_info.get('new_prediction_ids',[]) and c['strategy']=='production_radar' and c['session']==latestday and not c['pre_execution_rejections']:
            production.append({'id':c['id'],'kind':'new_confirmed_production_opportunity','symbol':c['symbol'],'source_classification':c['production_classification'],'delivery':'file_only','shadow':False})
    derived(current/'production_alerts.json',{'events':production,'external_notifications_sent':0,'chatgpt_delivery_tested':False})
    derived(current/'operational_status.json',{'source_quality':quality['denominators'],'events':revisions,'separate_from_opportunities':True})
    lines=['# المرحلة السادسة — لوحة التحقق المستقبلي','',f"تشغيل القياس: {run_info.get('run_url')}",'',
      f"الجلسات المستقبلية المسجلة فعليًا: **{len(sessions)}**. لقطات التدقيق القديمة/اليدوية: **{len(audit)}**.",
      'الأصل والجدولة لم يتغيرا. الاستراتيجيات التجريبية في الظل، ولا تصدر منها توصيات شراء.','',
      '| الاستراتيجية | الإشارات المسجلة | افتتحت | مكتملة موثوقة | رابحة | خاسرة | التوقع الصافي % | غير قابلة للتنفيذ | نتائج غير قابلة للتحقق |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append('| '+r['strategy']+' | '+' | '.join('غير متاح' if r[k] is None else str(round(r[k],4)) for k in ('signal_count','opened_total','completed_valid','wins','losses','net_expectancy_pct','not_executable','data_unverifiable'))+' |')
    lines+=['','**القرار: الاستمرار في الظل؛ لم يثبت تحسن مستقل بعد التكاليف.**','',
      'الصفر في عدد الصفقات ليس نسبة نجاح0% ولا دليل ربحية. فترات الثقة وويلسون، عامل الربح، السحب، التعرض، الدوران، متوسط الاحتفاظ، حساسية الانزلاق، وفجوات الوقف في JSON/CSV؛ القيم غير القابلة للتقدير تظهر فارغة.',
      'أول جلسة جديدة مجدولة بعد التسجيل مطلوبة لاستكمال اختبار الربط الفعلي. التشغيل اليدوي بلقطة قديمة لا يستوفي هذا الشرط.',
      'لا يمكن ضمان عدم تعديل السجل ضد مالك يعيد كتابة المستودع وكل نقاط التثبيت؛ آلية التطبيق ترفض التعديل والحذف وتكشف العبث بالبصمات.',
      'مهمة تقرير ChatGPT القائمة لم يثبت تكاملها آليًا بهذا التغيير؛ لم تُنشأ مهمة أو قناة أخرى.']
    (current/'DASHBOARD_AR.md').write_text('\n'.join(lines)+'\n')
    (current/'DECISION.md').write_text('# Decision\n\nKEEP SHADOW / NO PROMOTION. No positive independent net-expectancy result has been established. At least100 completed reasonably independent forward trades across diverse regimes is a research target, not proof. Known historical tests are reused.\n\n'+ '\n'.join(snapshot['decision']['blockers'])+'\n\n'+snapshot['immutability']+'\n')
    (current/'DATA_QUALITY.md').write_text('# Data quality\n\n'+json.dumps(quality['denominators'],indent=2)+'\n\nWhole historical independent coverage remains0. Published latest validity, causal historical screening, point-in-time decision vintage, signal eligibility and independently executable raw bars are separate denominators. Look-ahead adjusted history is not replayed as new evidence. Current raw bars and candidate source windows are content-addressed objects; past predictions are never rescaled on revisions.\n\n'+json.dumps(quality['source_inventory'],ensure_ascii=False,indent=2)+'\n\nMarket-wide zero-volume dates:\n'+json.dumps(quality['market_wide_zero_volume_dates'],indent=2)+'\n')
    history=out/'history'/(str(run_info['run_id'])+'_'+str(run_info['run_attempt']))
    for name in ('summary.json','strategies.json','DATA_QUALITY.json'):
        write_exclusive(history/name,json.loads((current/name).read_text()))
    # Human/CSV immutable history copied by the publisher after content verification.
    return snapshot
