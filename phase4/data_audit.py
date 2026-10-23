"""Dated provider coverage, unmodified frozen history and bounded public probes."""
from __future__ import annotations
import argparse,hashlib,io,json,os,subprocess,sys,tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from phase3.experiment import load_snapshot
from phase3.quality_recheck import valid_daily_row,OFFICIAL_URLS
from phase4.research import dump
from research import quality_audit

SOURCES=[('Saudi Exchange historical reports',OFFICIAL_URLS[0]),('Saudi Exchange market watch',OFFICIAL_URLS[1]),
         ('Mubasher public stock page','https://www.mubasher.info/markets/TDWL/stocks/7200/'),
         ('Stooq TASI CSV','https://stooq.com/q/d/l/?s=%5Etasi&i=d&d1=20250501&d2=20261022')]

def independent_index(text,benchmark):
    try:
        d=pd.read_csv(io.StringIO(text));assert {'Date','Close'}<=set(d)
        d['Date']=pd.to_datetime(d.Date,errors='raise');assert not d.Date.duplicated().any()
        d=d.set_index('Date');d.Close=pd.to_numeric(d.Close,errors='raise');assert np.isfinite(d.Close).all() and d.Close.gt(0).all()
        ix=d.index.intersection(benchmark.index);assert len(ix)>=61
        differences=(d.loc[ix,'Close']/benchmark.loc[ix,'Close']-1).abs()*100
        return {'status':'dated_index_overlap_compared','observed_overlap_sessions':len(ix),'maximum_absolute_difference_pct':float(differences.max()),
                'sessions_exceeding_0_1pct_tolerance':int((differences>.1).sum()),'entire_historical_index_independently_reconciled':bool(len(ix)==len(benchmark) and (differences<=.1).all()),
                'stock_ohlcv_coverage_count':0}
    except Exception as e:return {'status':'no_validated_machine_readable_index_history','reason':str(e)[:150],'observed_overlap_sessions':0,'stock_ohlcv_coverage_count':0}

def probe(source,benchmark):
    name,url=source
    try:
        r=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
        detail=independent_index(r.text,benchmark) if name=='Stooq TASI CSV' and r.ok else {'status':'access_denied' if r.status_code in (401,403) else 'no_complete_dated_OHLCV_feed_verified','stock_ohlcv_coverage_count':0}
        return {'source':name,'url':url,'http_status':r.status_code,'response_sha256':hashlib.sha256(r.content).hexdigest(),**detail,'access_wall_bypassed':False}
    except Exception as e:return {'source':name,'url':url,'status':'request_failed','reason':str(e)[:200],'stock_ohlcv_coverage_count':0,'access_wall_bypassed':False}

def yahoo_worker(specfile,resultfile):
    import yfinance as yf
    spec=json.loads(Path(specfile).read_text());symbols=spec['symbols'];end=pd.Timestamp(spec['expected_session']);start=end-pd.Timedelta(days=540)
    data=yf.download([s+'.SR' for s in symbols],start=str(start.date()),end=str((end+pd.Timedelta(days=1)).date()),auto_adjust=False,repair=False,actions=True,threads=4,group_by='ticker',progress=False,timeout=15)
    rows=[]
    for s in symbols:
        try:
            d=data[s+'.SR'] if isinstance(data.columns,pd.MultiIndex) else data;d=d.dropna(how='all');checks=[valid_daily_row(r)[0] for _,r in d.iterrows()]
            expected=d.loc[end] if end in d.index else {};valid,reason=valid_daily_row(expected)
            dividends=pd.to_numeric(d.get('Dividends',pd.Series(dtype=float)),errors='coerce').fillna(0)
            splits=pd.to_numeric(d.get('Stock Splits',pd.Series(dtype=float)),errors='coerce').fillna(0)
            rows.append({'symbol':s,'downloaded_rows':len(d),'internally_valid_rows':sum(checks),'invalid_rows':len(d)-sum(checks),
                         'expected_session':str(end.date()),'expected_session_raw_bar_valid':valid,'reason':reason,
                         'dividend_events':int(dividends.ne(0).sum()),'split_events':int(splits.ne(0).sum()),
                         'raw_download_sha256':hashlib.sha256(d.to_csv().encode()).hexdigest(),'independently_verified':False})
        except Exception as e:rows.append({'symbol':s,'expected_session_raw_bar_valid':False,'reason':str(e)[:180],'downloaded_rows':0,'internally_valid_rows':0})
    Path(resultfile).write_text(json.dumps(rows))

def audit(snapshot,output,offline=False):
    histories,bench,sessions,cfg,latest,frozen=load_snapshot(snapshot);expected=latest['expected_session'];rows=[]
    for s,d in histories.items():
        q=quality_audit(d,sessions);repairs=q['unverified_quote_repairs'];rows.append({'symbol':s,'history_rows':len(d),'last_bar_date':str(d.index[-1].date()),
            'fresh':str(d.index[-1].date())==expected,'entry_eligible_vendor_checks':q['entry_eligible'],'repair_count':len(repairs),
            'quarantined_dates':q['quarantined_dates'],'unverified_quote_repairs':repairs,'large_adjusted_price_jumps':q['large_adjusted_price_jumps'],
            'missing_session_count':q['missing_session_count'],'zero_volume_rows':q['zero_volume_rows'],'normalization':q['normalization']})
    qsymbols={r['symbol'] for r in rows if not r['entry_eligible_vendor_checks']};assert len(qsymbols)==latest['quarantined_stock_count']
    providers=[];fresh=[];status='offline_no_fresh_source_claim'
    if not offline:
        with ThreadPoolExecutor(max_workers=4) as pool:providers=list(pool.map(lambda item:probe(item,bench),SOURCES))
        with tempfile.TemporaryDirectory() as tmp:
            spec=Path(tmp)/'request.json';result=Path(tmp)/'result.json';spec.write_text(json.dumps({'symbols':list(histories),'expected_session':expected}))
            try:
                completed=subprocess.run([sys.executable,'-m','phase4.data_audit','--worker',str(spec),str(result)],capture_output=True,text=True,timeout=240)
                if completed.returncode:raise RuntimeError(completed.stderr[-500:])
                fresh=json.loads(result.read_text());status='fresh_checks_completed'
            except Exception as e:status='fresh_vendor_check_failed_or_timed_out: '+str(e)[:240]
    passed=sum(r['expected_session_raw_bar_valid'] for r in fresh);qpassed=sum(r['expected_session_raw_bar_valid'] and r['symbol'] in qsymbols for r in fresh)
    benchmark_grid=bench.Close.reindex(sessions[sessions<=expected][-121:]);bmeta={k:v for k,v in bench.attrs.items() if k not in ('raw_data',)}
    report={'run_id':os.getenv('GITHUB_RUN_ID','local'),'created_utc':datetime.now(timezone.utc).isoformat(),'frozen_run_id':latest['run_id'],'expected_session':expected,
        'status':status,'universe_count':254,'frozen_quarantined_count':len(qsymbols),'frozen_vendor_eligible_count':254-len(qsymbols),
        'frozen_stock_audit':rows,'sources':providers,'fresh_yahoo_checks':fresh,
        'fresh_yahoo_expected_bar_passing_count':passed if fresh else None,'fresh_yahoo_coverage_pct':100*passed/254 if fresh else None,
        'fresh_quarantined_expected_bar_passing_count':qpassed if fresh else None,'fresh_quarantined_vendor_pass_coverage_pct':100*qpassed/len(qsymbols) if fresh else None,
        'fresh_checked_symbols':len(fresh),'independently_verified_stock_release_count':0,'frozen_inputs_modified':False,'live_gate_changes':False,
        'benchmark':{'source_metadata':bmeta,'rows':len(bench),'last_date':str(bench.index[-1].date()),'complete_recent_121_sessions':len(benchmark_grid)==121 and benchmark_grid.notna().all(),
                     'not_officially_reconciled_entire_history':True,'ffill_used':False},
        'provider_rights':{'Yahoo':'Unofficial yfinance research/personal-use access; Yahoo terms govern data use. Free access is not a redistribution licence. No automated repairs or quote substitutions in this fresh audit.',
          'Saudi Exchange':'Official source; public availability does not establish permission for a bulk automated historical feed. No authentication/WAF bypass.',
          'Mubasher':'Public quote page is not a verified, licensed full OHLCV historical feed; zero verified stock-history coverage in these probes.',
          'Stooq':'Index-only public CSV probe; site access/terms and dated overlap must pass. No assumed Saudi equity coverage.',
          'Twelve Data':'XSAU catalog requires Pro+/Venture+ entitlement; Basic free tier is not verified Saudi historical coverage. No entitlement or data downloaded; validated coverage unknown, not a proven alternative.'},
        'limitations':['Fresh same-vendor passes do not independently resolve earlier quarantined repairs or corporate actions.','A provider access failure means no validated coverage in this audit, not proof the provider has no data.','Previously adjusted history lacks point-in-time corporate-action vintages; survivorship bias remains.','Input hashes bind the research to the old frozen snapshot; fresh probes cannot improve its historical results.']}
    out=Path(output);dump(out/'data_quality.json',report);pd.json_normalize(rows).to_csv(out/'data_quality_stocks.csv',index=False)
    md=['# Data Quality — Phase 4','',f'Frozen run {latest["run_id"]}; price session {expected}; audit UTC {report["created_utc"]}.',
        f'254 current stocks; {len(qsymbols)} quarantined; {254-len(qsymbols)} pass existing vendor gates. Passing internal checks is not independent exchange certification. No quarantined price has been released by this research.',
        '', '## Fresh independent provider probes', '', '| Source | HTTP | Result | Verified stock histories /254 |','|---|---:|---|---:|']
    md+=['| '+p['source']+' | '+str(p.get('http_status','NA'))+' | '+p['status']+' | 0 |' for p in providers]
    md+=['',f'Fresh Yahoo checks: {len(fresh)}/254 attempted with results; valid expected-session bars {passed if fresh else "unknown"}; among the {len(qsymbols)} quarantined names, {qpassed if fresh else "unknown"} currently pass raw checks. These are SAME-provider checks, not independent releases. Status: {status}.',
          '', '## Audit scope and rights', '', *['- '+k+': '+v for k,v in report['provider_rights'].items()],
          '', 'Official historical: https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/reports-publications/historical-reports',
          'yfinance rights notice: https://ranaroussi.github.io/yfinance/ ; Saudi Twelve Data entitlement: https://twelvedata.com/exchanges/XSAU',
          '', '## Index and corporate actions', '', f'Benchmark {len(bench)} observed rows; latest {bench.index[-1].date()}; recent 121 synchronized sessions complete: {report["benchmark"]["complete_recent_121_sessions"]}. Existing merged Yahoo/Investing history carries source metadata in JSON. A single current overlapping quote cannot certify the whole history. Stooq overlap results, if accessible, are in data_quality.json. No forward-filled index values.',
          'Raw Yahoo dividend/split event counts are recorded when the fresh download succeeds; rights issues, complete exchange actions and historical adjustment vintages remain unverified. Existing repaired closes are logged per symbol/date; no interpolation, invented close or retrospective override.',
          '', *report['limitations']]
    (out/'DATA_QUALITY.md').write_text('\n'.join(md)+'\n');print(json.dumps({k:report[k] for k in ('status','frozen_quarantined_count','fresh_checked_symbols','fresh_yahoo_expected_bar_passing_count','independently_verified_stock_release_count')}))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot');p.add_argument('--output',default='output/phase4/current');p.add_argument('--offline',action='store_true');p.add_argument('--worker',nargs=2);a=p.parse_args()
    if a.worker:yahoo_worker(*a.worker)
    else:audit(a.snapshot,a.output,a.offline)
