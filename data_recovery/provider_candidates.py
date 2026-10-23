"""Bounded read-only candidate-provider assessment. Never orders or auto-release.
Upstream independence and redistribution rights require separate verification.
"""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import requests
from phase6.ledger import derived
from phase3.quality_recheck import valid_daily_row

BASE='https://api.tasilab.com'

def parse_history(payload,symbol,start,end):
    if payload.get('symbol')!=symbol or payload.get('start')!=start or payload.get('end')!=end:raise ValueError('RESPONSE_IDENTITY_OR_RANGE_MISMATCH')
    bars=payload.get('bars');seen=set();invalid=0
    if not isinstance(bars,list) or payload.get('count')!=len(bars):raise ValueError('RESPONSE_COUNT_MISMATCH')
    for row in bars:
        if row.get('symbol')!=symbol:raise ValueError('WRONG_BAR_SYMBOL')
        date=row['date'];pd.Timestamp(date)
        if date in seen or date<start or date>end:raise ValueError('DUPLICATE_OR_OUT_OF_RANGE_DATE')
        seen.add(date)
        values={k.capitalize():float(row[k]) for k in ('open','high','low','close','volume')}
        if not valid_daily_row(values)[0]:invalid+=1
    return {'observed_bars':len(bars),'invalid_or_zero_volume_bars':invalid,'first_date':min(seen) if seen else None,'last_date':max(seen) if seen else None,'data_version':payload.get('data_version'),'payload_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),'independence_established':False,'released_for_signals':False}

def probe(session=None,symbol='7200',end='2026-10-22'):
    transport=session or requests.Session();start=str((pd.Timestamp(end)-pd.Timedelta(days=365)).date())
    result={'provider':'Tasilab','observed_utc':datetime.now(timezone.utc).isoformat(),'sample_symbol':symbol,'sample_start':start,'sample_end':end,'read_only':True,'orders_sent':0,'independent_coverage':0,'production_changed':False,'redistribution_permission_established':False,'upstream_independence':'UNVERIFIED','requests_made':0}
    for path,name in [('/v1/config/tiers','tier_probe'),('/openapi.json','schema_probe')]:
        try:
            response=transport.get(BASE+path,timeout=25,allow_redirects=False);result['requests_made']+=1
            result[name]={'http_status':response.status_code,'sha256':hashlib.sha256(response.content).hexdigest()}
            if response.status_code==200:
                body=response.json()
                if name=='tier_probe':result['advertised_free_tier']={'meta':body.get('tier_meta',{}).get('free'),'values':body.get('values',{}).get('free'),'sandbox_mode':body.get('sandbox_mode')}
                else:result['historical_endpoint_documented']='/v1/historical/{symbol}' in body.get('paths',{})
            elif response.status_code in (401,403,429):result['status']='ACCESS_OR_QUOTA_DENIED_STOP';return result
        except requests.RequestException:
            result['status']='PUBLIC_METADATA_NETWORK_FAILURE';return result
    try:
        response=transport.get(BASE+'/v1/historical/'+symbol,params={'start':start,'end':end},timeout=30,allow_redirects=False);result['requests_made']+=1
        result['historical_http_status']=response.status_code
        if response.status_code==401:result['status']='ACCOUNT_KEY_REQUIRED'
        elif response.status_code in (403,429):result['status']='ENTITLEMENT_OR_QUOTA_DENIED_NO_RETRY'
        elif response.status_code!=200:result['status']='HISTORY_UNAVAILABLE'
        else:
            try:result['sample_audit']=parse_history(response.json(),symbol,start,end);result['status']='SAMPLE_RETRIEVED_NOT_INDEPENDENTLY_APPROVED'
            except (ValueError,KeyError,TypeError):result['status']='INVALID_HISTORY_RESPONSE'
    except requests.RequestException:
        # Exception text can include prepared headers or user credentials; never persist it.
        result['status']='HISTORY_NETWORK_FAILURE'
    result['credential_value_recorded']=False
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-info',required=True);a=p.parse_args()
    source=json.loads(Path(a.source_info).read_text());sourceid=str(source['id'])
    # Current recovery run binds to the completed daily source's session, not wall-clock date.
    report=json.loads(Path('output/data_recovery/current/summary.json').read_text());assert report['source_run_id']==sourceid
    result=probe(end=report['source_session'])
    derived('output/data_recovery/current/TASILAB_CANDIDATE.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('advertised_free_tier','sample_audit')}))
