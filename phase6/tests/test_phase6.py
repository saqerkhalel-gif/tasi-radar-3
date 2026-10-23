import copy,json,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import pytest
from phase6.ledger import Ledger,sha,write_exclusive
from phase6.calendar import next_session,prospective_source
from phase6.quality import cross_source
from phase6.engine import prediction,advance,project
from phase6.pipeline import load_snapshot

P=json.loads(Path('phase6/protocol.json').read_text())
CFG=json.loads(Path('config.json').read_text())
NOW='2026-10-25T15:00:00+00:00'

def row(date='2026-10-26',o=100,h=101,l=99,c=100,v=100,split=0,dividend=0):
    return {'provider':'Yahoo Finance','symbol':'X','date':date,'ohlcv':{'Open':o,'High':h,'Low':l,'Close':c,'Volume':v},'split':split,'dividend':dividend}

def ref(r):
    return {**copy.deepcopy(r),'provider':'Independent fixture only','usage_permitted':True,'retrieved_utc':NOW,'content_sha256':'a'*64,'url':'https://example.test/fixture-not-live-data'}

def seed(root):
    ledger=Ledger(root)
    source={'run_id':'fixture','head_sha':'code','expected_session':'2026-10-25','session_close_utc':'2026-10-25T12:20:00+00:00'}
    record={'strategy':'phase5_failed_breakdown','symbol':'X','close':100.,'scenario':{'trigger':100.,'invalidation':95.,'conditional_target':112.,'upside_pct':12.,'reward_risk':2.4},
      'observations':{'price_confirmed':True,'volume_ratio':2.},'entry_context':{'market_regime':'Risk_ON'},'object_refs':[]}
    prediction(ledger,'prediction:X',record,source,{'signal_eligible':True},'fixture-v1',NOW,CFG,P)
    return ledger

def test_exclusive_idempotence_and_changed_payload_rejection(tmp_path):
    path=tmp_path/'immutable.json';assert write_exclusive(path,{'x':1});assert not write_exclusive(path,{'x':1})
    with pytest.raises(ValueError):write_exclusive(path,{'x':2})
    ledger=Ledger(tmp_path/'ledger');a=ledger.append('x','TEST',{'x':1},NOW);assert ledger.append('x','TEST',{'x':1},'later')['hash']==a['hash']
    with pytest.raises(ValueError):ledger.append('x','TEST',{'x':2},NOW)

def test_hash_chain_and_truncation_anchor_detect_tampering(tmp_path):
    ledger=Ledger(tmp_path);ledger.append('a','TEST',{},NOW);ledger.append('b','TEST',{},NOW)
    write_exclusive(tmp_path/'checkpoints/a.json',ledger.manifest())
    last=sorted((tmp_path/'events').glob('*.json'))[-1];last.unlink()
    with pytest.raises(ValueError,match='CHECKPOINT'):Ledger(tmp_path)

def test_object_and_event_corruption_detected(tmp_path):
    ledger=Ledger(tmp_path);key=ledger.object({'price':100});ledger.append('a','TEST',{},NOW,[key])
    (tmp_path/'objects'/(key+'.json')).write_text('{"price":101}')
    with pytest.raises(ValueError,match='OBJECT'):Ledger(tmp_path)

def test_parallel_append_has_one_contiguous_chain(tmp_path):
    def add(i):return Ledger(tmp_path).append(str(i),'TEST',{'n':i},NOW)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(add,range(8)))
    ledger=Ledger(tmp_path);assert len(ledger.events)==8 and [e['sequence'] for e in ledger.events]==list(range(1,9))

def test_weekend_holiday_and_late_source_not_prospective():
    assert next_session('2026-10-22',CFG)=='2026-10-25'
    cfg={**CFG,'extra_closed_dates':['2026-10-25']};assert next_session('2026-10-22',cfg)=='2026-10-26'
    source={'expected_session':'2026-10-25','run_utc':'2026-10-25T14:35:00+00:00','event':'schedule','conclusion':'success','head_branch':'main','workflow_name':'TASI Radar 3.0'}
    now=datetime(2026,10,25,15,tzinfo=timezone.utc)
    assert prospective_source(source,now,'2026-10-23T13:40:00+00:00',CFG)[0]
    assert not prospective_source({**source,'event':'workflow_dispatch'},now,'2026-10-23T13:40:00+00:00',CFG)[0]
    assert not prospective_source(source,datetime(2026,10,26,8,tzinfo=timezone.utc),'2026-10-23T13:40:00+00:00',CFG)[0]

def test_independent_reference_must_be_dated_complete_and_distinct():
    r=row();assert cross_source(r,ref(r))
    assert not cross_source(r,{**ref(r),'provider':'Yahoo Finance'})
    assert not cross_source(r,{**ref(r),'date':'2026-10-25'})
    bad=ref(r);bad['ohlcv']['Open']=50;assert not cross_source(r,bad)
    assert not cross_source(r,{**ref(r),'usage_permitted':False})

@pytest.mark.parametrize('r,reason',[(None,'missing_invalid_or_zero_volume_open'),(row(v=0),'missing_invalid_or_zero_volume_open'),(row(split=2),'capital_action_unverified')])
def test_missing_open_zero_volume_and_corporate_action_never_guessed(tmp_path,r,reason):
    ledger=seed(tmp_path);refs=[ref(r)] if r else []
    advance(ledger,'2026-10-26',{'X':r} if r else {},refs,P,CFG,'2026-10-26T15:00:00+00:00')
    candidates,_=project(ledger.events,P);assert candidates['prediction:X']['status']=='NOT_EXECUTABLE' and candidates['prediction:X']['outcome_reason']==reason
    assert not any(e['kind']=='OPENED' for e in ledger.events)

def test_vendor_only_open_is_not_execution_evidence(tmp_path):
    ledger=seed(tmp_path);r=row();advance(ledger,r['date'],{'X':r},[],P,CFG,'2026-10-26T15:00:00+00:00')
    candidates,_=project(ledger.events,P);assert candidates['prediction:X']['status']=='NOT_EXECUTABLE'

def test_stop_first_costs_caps_and_idempotent_new_session(tmp_path):
    ledger=seed(tmp_path);r=row(h=113,l=94,c=108)
    advance(ledger,r['date'],{'X':r},[ref(r)],P,CFG,'2026-10-26T15:00:00+00:00')
    candidates,books=project(ledger.events,P);trade=books['phase5_failed_breakdown']['trades'][0]
    assert trade['exit']['reason']=='stop_first_daily_ambiguity' and trade['exit']['net_return_pct']< -5
    assert trade['entry']['planned_risk_cash']<=.005*trade['entry']['equity_at_entry']
    assert trade['entry']['aggregate_planned_risk_cash']<=.03*trade['entry']['equity_at_entry']
    before=ledger.head;advance(ledger,r['date'],{'X':r},[ref(r)],P,CFG,'2026-10-26T16:00:00+00:00');assert ledger.head==before

def test_gap_through_stop_can_exceed_planned_risk(tmp_path):
    ledger=seed(tmp_path);first=row();advance(ledger,first['date'],{'X':first},[ref(first)],P,CFG,'2026-10-26T15:00:00+00:00')
    gap=row('2026-10-27',o=92,h=94,l=90,c=93);advance(ledger,gap['date'],{'X':gap},[ref(gap)],P,CFG,'2026-10-27T15:00:00+00:00')
    _,books=project(ledger.events,P);t=books['phase5_failed_breakdown']['trades'][0]
    assert t['exit']['reason']=='gap_through_stop' and -t['exit']['net_pnl']>t['entry']['planned_risk_cash']

def test_unknown_holding_bar_freezes_forever_and_no_missing_day_skip(tmp_path):
    ledger=seed(tmp_path);r=row();advance(ledger,r['date'],{'X':r},[ref(r)],P,CFG,'2026-10-26T15:00:00+00:00')
    later=row('2026-10-28');advance(ledger,later['date'],{'X':later},[ref(later)],P,CFG,'2026-10-28T15:00:00+00:00')
    c,b=project(ledger.events,P);assert c['prediction:X']['status']=='DATA_UNVERIFIABLE' and b['phase5_failed_breakdown']['invalid']
    assert b['phase5_failed_breakdown']['curve'][-1]['nav'] is None and not b['phase5_failed_breakdown']['trades']

def test_duplicate_active_symbol_and_material_prediction_changes_are_separate(tmp_path):
    ledger=seed(tmp_path);r=row();advance(ledger,r['date'],{'X':r},[ref(r)],P,CFG,'2026-10-26T15:00:00+00:00')
    first=ledger.ids['prediction:X'];original=copy.deepcopy(first)
    ledger.append('change:X','HYPOTHESIS_CHANGE_OBSERVED',{'original_prediction':'prediction:X','new_target':120},'2026-10-26T16:00:00+00:00')
    assert ledger.ids['prediction:X']==original and first['payload']['scenario']['conditional_target']==112


def test_publisher_rejects_history_and_ledger_changes(tmp_path):
    from phase6.publish import guard
    old=tmp_path/'old';new=tmp_path/'new'
    for root in (old,new):
        (root/'ledger/events').mkdir(parents=True)
        (root/'ledger/events/one.json').write_text('original')
    guard(old,new)
    (new/'ledger/events/one.json').write_text('changed')
    with pytest.raises(ValueError,match='DURABLE_EDIT'):guard(old,new)
    (new/'ledger/events/one.json').unlink()
    with pytest.raises(ValueError,match='DURABLE_EDIT'):guard(old,new)


def test_no_signal_session_and_zero_trade_metrics(tmp_path):
    from phase6.report import make_reports
    ledger=Ledger(tmp_path/'ledger')
    ledger.append('session:2026-10-25','SESSION_RECORDED',{'session':'2026-10-25','source_event':'schedule','no_eligible_signal_day':True},NOW)
    quality={'price_session':'2026-10-25','denominators':{},'symbols':[],'source_inventory':{},'market_wide_zero_volume_dates':[]}
    info={'run_id':'fixture','run_attempt':1,'run_url':None}
    summary=make_reports(ledger,quality,P,tmp_path,info)
    assert summary['prospective_session_count']==1
    assert len(summary['strategies'])==6
    assert all(r['completed_valid']==0 and r['win_rate_pct'] is None and r['net_expectancy_pct'] is None and not r['adopted'] for r in summary['strategies'])
    assert json.loads((tmp_path/'current/production_alerts.json').read_text())['events']==[]


def test_invalid_source_rejected_before_loading_data(tmp_path):
    (tmp_path/'output').mkdir();(tmp_path/'output/latest.json').write_text('{"schema_version":0}')
    with pytest.raises(ValueError,match='INVALID_SOURCE_IDENTITY'):load_snapshot(tmp_path,{})


def test_failed_transaction_never_installs_partial_events(tmp_path,monkeypatch):
    import phase6.pipeline as pipeline
    target=tmp_path/'accepted';Ledger(target/'ledger').append('original','TEST',{},NOW)
    before={str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*.json')}
    def bad(snapshot,identity,staged,*args):
        Ledger(staged/'ledger').append('partial','TEST',{},NOW)
        raise RuntimeError('fixture failure')
    monkeypatch.setattr(pipeline,'_run',bad)
    with pytest.raises(RuntimeError):pipeline.run('unused',{},target)
    assert before=={str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*.json')}
