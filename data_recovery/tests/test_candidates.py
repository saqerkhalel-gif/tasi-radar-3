import json
import requests
import pytest
from data_recovery.provider_candidates import parse_history,probe


def payload():
    return {'symbol':'7200','start':'2026-01-01','end':'2026-10-22','count':1,'bars':[{'symbol':'7200','date':'2026-10-22','open':'100','high':'102','low':'99','close':'101','adj_close':'101','volume':1000}]}


def test_candidate_cannot_become_independent_validation():
    p=payload();r=parse_history(p,'7200',p['start'],p['end'])
    assert r['invalid_or_zero_volume_bars']==0 and r['independence_established'] is False and r['released_for_signals'] is False


@pytest.mark.parametrize('failure',['symbol','duplicate','count','nan','future'])
def test_candidate_response_validation(failure):
    p=payload()
    if failure=='symbol':p['bars'][0]['symbol']='9999'
    elif failure=='duplicate':p['bars']*=2;p['count']=2
    elif failure=='count':p['count']=9
    elif failure=='nan':p['bars'][0]['close']='nan'
    else:p['bars'][0]['date']='2027-01-01'
    if failure=='nan':assert parse_history(p,'7200',p['start'],p['end'])['invalid_or_zero_volume_bars']==1
    else:
        with pytest.raises(ValueError):parse_history(p,'7200',p['start'],p['end'])


class Response:
    def __init__(self,status,body):self.status_code=status;self.body=body;self.content=json.dumps(body).encode()
    def json(self):return self.body


class Transport:
    def __init__(self,status):self.calls=[];self.status=status
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if 'historical/' in url:return Response(self.status,{'detail':'auth required'})
        return Response(200,{})


def test_missing_key_and_denials_never_retry_or_place_orders():
    for code in (401,403,429):
        t=Transport(code);r=probe(t)
        assert len(t.calls)==3 and r['orders_sent']==0 and r['independent_coverage']==0
        assert '/orders' not in str(t.calls) and r['credential_value_recorded'] is False


def test_transport_error_never_leaks_credential():
    class Broken(Transport):
        def get(self,url,**kwargs):
            if 'historical/' in url:raise requests.RequestException('SECRET_FIXTURE_KEY')
            return Response(200,{})
    assert 'SECRET_FIXTURE_KEY' not in json.dumps(probe(Broken(200)))
