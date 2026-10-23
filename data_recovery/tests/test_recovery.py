import json,hashlib
from datetime import datetime,timezone
import pandas as pd
import pytest
from data_recovery.audit import classify_basis,window_audit,load_references,reconciliation


def fixture():
    grid=pd.date_range('2025-01-01',periods=126,freq='B')
    return pd.DataFrame({'Open':100.,'High':102.,'Low':99.,'Close':101.,'Volume':1000.},index=grid),grid


def test_basis_differences_not_treated_as_raw_price_errors():
    assert classify_basis(95,100,95)=='ADJUSTED_BASIS_ONLY_DIFFERENCE'
    assert classify_basis(100,100,95)=='RAW_CLOSE_AGREES'
    assert classify_basis(90,100,95)=='UNRESOLVED_PRICE_DIFFERENCE'
    assert classify_basis(100,float('nan'),float('nan'))=='UNRESOLVED_PRICE_DIFFERENCE'


def test_full_window_zero_volume_and_missing_not_deleted():
    frame,grid=fixture();assert window_audit(frame,grid)['complete_window']
    frame.loc[grid[2],'Volume']=0
    assert not window_audit(frame,grid)['complete_window']
    assert window_audit(frame,grid)['zero_volume']==1
    frame=frame.drop(grid[3]);assert window_audit(frame,grid)['missing_sessions']==1


def test_duplicate_dates_rejected_without_silent_deduplication():
    frame,grid=fixture();assert window_audit(pd.concat([frame,frame.iloc[-1:]]),grid)['duplicate_dates']


def test_current_match_cannot_certify_full_history():
    frame,grid=fixture();ref=frame.iloc[-1:]
    result=reconciliation(frame,ref,grid)
    assert result['latest_independent_match'] and not result['full126_independent_match']
    ref=frame.copy();ref.loc[grid[2],'Close']=100
    assert not reconciliation(frame,ref,grid)['full126_independent_match']


def test_ref_manifest_hash_provenance_and_upstream_required(tmp_path):
    frame,grid=fixture();frame.index.name='Date';blob=frame.to_csv().encode();(tmp_path/'7200.csv').write_bytes(blob)
    meta={'symbol':'7200','basis':'raw','timezone':'Asia/Riyadh','provider':'Fixture','upstream_provider':'Independent fixture source','source_url':'https://example.test/fixture','retrieved_utc':datetime.now(timezone.utc).isoformat(),'usage_authorization':'fixture only','csv_sha256':hashlib.sha256(blob).hexdigest(),'independence_attested':True}
    def write(): (tmp_path/'manifest.json').write_text(json.dumps({'series':[meta]}))
    write();accepted,rejected=load_references(tmp_path);assert len(accepted)==1 and not rejected
    meta['upstream_provider']='Yahoo Finance';write();assert not load_references(tmp_path)[0]
    meta['upstream_provider']='Independent fixture source';meta['csv_sha256']='wrong';write();assert not load_references(tmp_path)[0]
    meta['csv_sha256']=hashlib.sha256(blob).hexdigest();meta['basis']='adjusted';write();assert not load_references(tmp_path)[0]


def test_missing_reference_stays_missing(tmp_path):
    accepted,rejected=load_references(tmp_path);assert not accepted and rejected
