"""Bounded free-source checks, isolated from frozen experiment inputs and live gates."""
import argparse, hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from radar import clean

OFFICIAL_URLS=[
 'https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/reports-publications/historical-reports',
 'https://www.saudiexchange.sa/wps/portal/saudiexchange/ourmarkets/main-market-watch']


def valid_daily_row(row):
    cols=('Open','High','Low','Close','Volume')
    if any(k not in row or pd.isna(row[k]) or not np.isfinite(float(row[k])) for k in cols):return False,'missing_or_nonfinite_OHLCV'
    o,h,l,c,v=(float(row[k]) for k in cols)
    if min(o,h,l,c)<=0 or v<=0 or not l<=min(o,c)<=max(o,c)<=h:return False,'invalid_OHLC_range_or_zero_volume'
    return True,'published_vendor_daily_bar_passes_internal_checks'


def yahoo_worker(request_path,result_path):
    import yfinance as yf
    spec=json.loads(Path(request_path).read_text());tickers=[s+'.SR' for s in spec['symbols']]
    start=pd.Timestamp(spec['expected_session'])-pd.Timedelta(days=7);end=pd.Timestamp(spec['expected_session'])+pd.Timedelta(days=1)
    downloaded=yf.download(tickers,start=str(start.date()),end=str(end.date()),auto_adjust=False,repair=False,threads=4,group_by='ticker',progress=False,timeout=15)
    rows=[]
    for symbol,ticker in zip(spec['symbols'],tickers):
        try:
            d=downloaded[ticker] if isinstance(downloaded.columns,pd.MultiIndex) else downloaded
            index=[i for i in d.index if str(i.date())==spec['expected_session']]
            if not index:raise ValueError('expected_session_absent')
            row=d.loc[index[-1]];valid,reason=valid_daily_row(row)
            rows.append({'symbol':symbol,'date':spec['expected_session'],'raw_published_daily_bar_valid':valid,'reason':reason,
                         'ohlcv':{k:row.get(k) for k in ('Open','High','Low','Close','Volume')}})
        except Exception as e:rows.append({'symbol':symbol,'raw_published_daily_bar_valid':False,'reason':str(e)[:180]})
    Path(result_path).write_text(json.dumps(clean(rows),allow_nan=False))


def run(snapshot,output,offline=False):
    p=json.loads((Path(snapshot)/'output/latest.json').read_text());symbols=[r['symbol'] for r in p['results'] if not r['data_quality']['entry_eligible']]
    run_id=os.getenv('GITHUB_RUN_ID','local')
    report={'run_id':run_id,'run_url':f'https://github.com/saqerkhalel-gif/tasi-radar-3/actions/runs/{run_id}' if run_id!='local' else None,'frozen_run_id':p['run_id'],'expected_session':p['expected_session'],'checked_utc':datetime.now(timezone.utc).isoformat(),
            'quarantined_in_frozen_snapshot':len(symbols),'official_sources':[],'vendor_recheck':{},'independently_verified_release_count':0,
            'live_gate_changes':False,'frozen_experiment_inputs_changed':False,
            'note':'Yahoo re-download is same-provider evidence, not independent exchange validation. No quote substitution, interpolation or automatic repair. A reachable HTML page without dated complete OHLCV is not a verified feed. All quarantines remain until the deployed scanner receives internally valid published bars or independently verified data.'}
    if offline:
        report['status']='offline_test_no_network';report['vendor_recheck']={'attempted':0,'rows':[]}
    else:
        for url in OFFICIAL_URLS:
            try:
                response=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
                report['official_sources'].append({'url':url,'http_status':response.status_code,'content_sha256':hashlib.sha256(response.content).hexdigest(),
                    'verified_dated_ohlcv_rows':0,'status':'access_denied' if response.status_code in (401,403) else 'no_machine_verified_dated_OHLCV_feed','independently_verified':False})
            except Exception as e:report['official_sources'].append({'url':url,'status':'request_failed','reason':str(e)[:220],'verified_dated_ohlcv_rows':0})
        with tempfile.TemporaryDirectory() as temp:
            request=Path(temp)/'request.json';result=Path(temp)/'result.json';request.write_text(json.dumps({'symbols':symbols,'expected_session':p['expected_session']}))
            try:
                completed=subprocess.run([sys.executable,'-m','phase3.quality_recheck','--yahoo-worker',str(request),str(result)],capture_output=True,text=True,timeout=180)
                if completed.returncode:raise RuntimeError(completed.stderr[-500:])
                rows=json.loads(result.read_text());valid=sum(r['raw_published_daily_bar_valid'] for r in rows)
                report['vendor_recheck']={'attempted':len(symbols),'raw_daily_bars_passing_checks':valid,'still_missing_or_invalid':len(rows)-valid,'rows':rows,'provider':'Yahoo Finance, same vendor as baseline'}
            except subprocess.TimeoutExpired:report['vendor_recheck']={'attempted':len(symbols),'status':'bounded_180_second_timeout','rows':[]}
            except Exception as e:report['vendor_recheck']={'attempted':len(symbols),'status':'failed','reason':str(e)[:600],'rows':[]}
        report['status']='completed_with_no_independently_verified_releases'
    out=Path(output);out.mkdir(parents=True,exist_ok=True);(out/'quality_recheck.json').write_text(json.dumps(clean(report),ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({k:v for k,v in report.items() if k!='vendor_recheck'},ensure_ascii=False))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot');p.add_argument('--output',default='output/phase3/current');p.add_argument('--offline',action='store_true');p.add_argument('--yahoo-worker',nargs=2);a=p.parse_args()
    if a.yahoo_worker:yahoo_worker(*a.yahoo_worker)
    else:run(a.snapshot,a.output,a.offline)
