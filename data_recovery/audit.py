"""Reconcile fresh unmodified full histories with archived decision vintages.
No quote substitution, fill, quarantine release, or strategy promotion.
"""
import argparse,gzip,hashlib,json,os,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from phase6.ledger import derived,canonical
from phase6.pipeline import load_snapshot
from phase6.quality import raw_row
from phase3.quality_recheck import valid_daily_row
from radar import session_calendar

FIELDS=['Open','High','Low','Close','Volume']

def digest(b):return hashlib.sha256(b).hexdigest()

def close_match(a,b):
    return bool(a is not None and b is not None and np.isfinite(a) and np.isfinite(b) and a>0 and b>0 and abs(a/b-1)<=.001)

def classify_basis(archived,raw,adjusted):
    if close_match(archived,raw):return 'RAW_CLOSE_AGREES'
    if close_match(archived,adjusted):return 'ADJUSTED_BASIS_ONLY_DIFFERENCE'
    return 'UNRESOLVED_PRICE_DIFFERENCE'

def worker(specfile,out):
    import yfinance as yf
    spec=json.loads(Path(specfile).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=True)
    end=pd.Timestamp(spec['session']);start=end-pd.Timedelta(days=540)
    tickers=[s+'.SR' for s in spec['symbols']]+['^TASI.SR']
    panel=yf.download(tickers,start=str(start.date()),end=str((end+pd.Timedelta(days=1)).date()),auto_adjust=False,repair=False,actions=True,threads=4,group_by='ticker',progress=False,timeout=15)
    manifest={}
    for symbol in spec['symbols']+['^TASI']:
        try:
            frame=panel[symbol+'.SR'].copy();frame.index=pd.to_datetime(frame.index).tz_localize(None);frame.index.name='Date'
            # Remove outer-join rows where this security has no field. Retain partially missing bars.
            frame=frame.loc[frame[FIELDS].notna().any(axis=1)]
            blob=frame.to_csv().encode();path=out/(symbol+'.csv.gz');path.write_bytes(gzip.compress(blob,mtime=0))
            manifest[symbol]={'rows':len(frame),'csv_sha256':digest(blob),'archive_sha256':digest(path.read_bytes())}
        except Exception as exc:manifest[symbol]={'rows':0,'error':type(exc).__name__+':'+str(exc)[:180]}
    derived(out/'manifest.json',{'provider':'Yahoo Finance','retrieved_utc':datetime.now(timezone.utc).isoformat(),'session':spec['session'],'price_basis':'raw OHLCV plus separate published Adj Close; no repairs or fills','files':manifest})

def window_audit(frame,grid):
    required=grid[-126:]
    if frame.index.duplicated().any():return {'complete_window':False,'missing_sessions':None,'invalid_bars':None,'zero_volume':None,'duplicate_dates':True}
    view=frame.reindex(required)
    missing=int((~required.isin(frame.index)).sum())
    invalid=sum(not valid_daily_row(row)[0] for _,row in view.iterrows())
    return {'complete_window':len(required)==126 and missing==0 and invalid==0,'missing_sessions':missing,'invalid_bars':invalid,'zero_volume':int(view.Volume.eq(0).sum()),'duplicate_dates':False}

def load_references(folder):
    """Optional independently supplied dated CSVs with explicit provenance and rights.
    Absence, changed checksums, unknown upstream or ambiguous adjustment => no acceptance.
    Never accepts a current quote as historical-series confirmation.
    """
    folder=Path(folder);manifest=folder/'manifest.json';accepted={};rejected=[]
    if not manifest.exists():return accepted,[{'reason':'NO_INDEPENDENT_REFERENCE_MANIFEST'}]
    for item in json.loads(manifest.read_text()).get('series',[]):
        symbol=str(item.get('symbol',''));reason=None
        if not symbol or not (symbol.isdigit() or symbol=='^TASI'):reason='INVALID_SYMBOL'
        if item.get('basis')!='raw' or item.get('timezone')!='Asia/Riyadh':reason='AMBIGUOUS_BASIS_OR_TIMEZONE'
        if not all(item.get(k) for k in ('provider','upstream_provider','source_url','retrieved_utc','usage_authorization','csv_sha256')):reason='INCOMPLETE_PROVENANCE'
        if 'yahoo' in (str(item.get('provider'))+' '+str(item.get('upstream_provider'))).lower():reason='NOT_INDEPENDENT_OF_YAHOO'
        if item.get('independence_attested') is not True:reason='INDEPENDENCE_NOT_ATTESTED'
        try:
            stamp=datetime.fromisoformat(item['retrieved_utc'].replace('Z','+00:00'))
            if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):reason='INVALID_REFERENCE_TIMESTAMP'
            path=folder/(symbol+'.csv');blob=path.read_bytes()
            if digest(blob)!=item['csv_sha256']:reason='REFERENCE_HASH_MISMATCH'
            frame=pd.read_csv(path,index_col='Date',parse_dates=True)
            if not set(FIELDS)<=set(frame) or frame.index.duplicated().any() or frame.index.tz is not None:reason='INVALID_REFERENCE_SCHEMA'
        except Exception:reason='UNREADABLE_REFERENCE'
        if reason:rejected.append({'symbol':symbol,'reason':reason})
        else:accepted[symbol]=(frame,item)
    return accepted,rejected

def reconciliation(frame,ref,grid):
    checked=matched=0;latest=False
    for date in grid:
        if date not in frame.index or date not in ref.index:continue
        a=frame.loc[date];b=ref.loc[date]
        if not valid_daily_row(a)[0] or not valid_daily_row(b)[0]:continue
        checked+=1
        ok=all(close_match(float(a[k]),float(b[k])) for k in FIELDS[:4]) and abs(a.Volume-b.Volume)<=max(1,.001*b.Volume)
        matched+=ok
        if date==grid[-1]:latest=ok
    return {'reference_checked_sessions':checked,'reference_matched_sessions':int(matched),'latest_independent_match':bool(latest),'full126_independent_match':len(grid)==126 and matched==126}

def run(snapshot,identity,output='output/data_recovery',references='data/independent',offline=False):
    root=Path(output);current=root/'current';current.mkdir(parents=True,exist_ok=True)
    frozen,benchmark,cfg,production,source,universe=load_snapshot(snapshot,identity)
    sessions,_=session_calendar(datetime.fromisoformat(production['completed_utc']),cfg);grid=sessions[sessions<=production['expected_session']]
    inputs=root/'inputs';status='NOT_FETCHED'
    if not offline:
        with tempfile.TemporaryDirectory() as temp:
            spec=Path(temp)/'spec.json';spec.write_bytes(canonical({'symbols':universe.symbol.tolist(),'session':production['expected_session']}))
            try:
                result=subprocess.run([sys.executable,'-m','data_recovery.audit','--worker',str(spec),str(inputs)],capture_output=True,text=True,timeout=240)
                if result.returncode:raise ValueError(result.stderr[-300:])
                status='FRESH_FULL_HISTORY_DOWNLOAD_COMPLETED'
            except Exception as exc:status='DOWNLOAD_FAILED:'+type(exc).__name__
    refs,reference_errors=load_references(references);rows=[];repairs=[];zeros={};fresh={}
    manifest=json.loads((inputs/'manifest.json').read_text()) if (inputs/'manifest.json').exists() else {'files':{}}
    for symbol in universe.symbol:
        old=frozen.get(symbol);path=inputs/(symbol+'.csv.gz');entry={'symbol':symbol,'fetched':False,'internal_window_eligible':False,'released_for_signals':False,'execution_authorized':False,'full126_independent_match':False,'latest_independent_match':False}
        if old is not None:
            entry['archived_repair_count']=len(old.attrs.get('price_repairs',[]));entry['archived_last_date']=str(old.index[-1].date())
        if path.exists():
            blob=gzip.decompress(path.read_bytes())
            assert digest(blob)==manifest['files'][symbol]['csv_sha256'],'Fresh CSV hash mismatch'
            frame=pd.read_csv(path,index_col='Date',parse_dates=True,float_precision='round_trip');fresh[symbol]=frame
            if not frame.empty:
                audit=window_audit(frame,grid);entry.update(fetched=True,fresh_rows=len(frame),fresh_last_date=str(frame.index[-1].date()),**audit)
                entry['internal_window_eligible']=audit['complete_window']
                entry['latest_raw_valid']=pd.Timestamp(source['expected_session']) in frame.index and valid_daily_row(frame.loc[source['expected_session']])[0]
                if old is not None and pd.Timestamp(source['expected_session']) in old.index and pd.Timestamp(source['expected_session']) in frame.index:
                    row=frame.loc[source['expected_session']];entry['last_price_basis_check']=classify_basis(float(old.loc[source['expected_session'],'Close']),float(row.Close),float(row.get('Adj Close',np.nan)))
                for date,row in frame.iterrows():
                    d=str(date.date());z=zeros.setdefault(d,{'date':d,'observed':0,'zero_volume':0,'invalid_OHLCV':0});z['observed']+=1;z['zero_volume']+=int(row.Volume==0);z['invalid_OHLCV']+=int(not valid_daily_row(row)[0])
                for repair in old.attrs.get('price_repairs',[]) if old is not None else []:
                    date=pd.Timestamp(repair['date']);r=frame.loc[date] if date in frame.index else None
                    value=float(old.loc[date,'Close']) if date in old.index else None
                    repairs.append({'symbol':symbol,'date':repair['date'],'archived_close':value,'raw_close_now':float(r.Close) if r is not None and pd.notna(r.Close) else None,'adjusted_close_now':float(r['Adj Close']) if r is not None and pd.notna(r.get('Adj Close')) else None,'same_vendor_basis_check':classify_basis(value,float(r.Close),float(r.get('Adj Close',np.nan))) if r is not None else 'MISSING_DATE','independently_resolved':False})
                if symbol in refs:entry.update(reconciliation(frame,refs[symbol][0],grid[-126:]))
        rows.append(entry)
    anomaly=[x for x in sorted(zeros.values(),key=lambda x:x['date']) if x['observed']>=50 and (x['zero_volume']/x['observed']>=.8 or x['invalid_OHLCV']/x['observed']>=.8)]
    counts={key:sum(bool(r.get(key)) for r in rows) for key in ('fetched','internal_window_eligible','latest_raw_valid','full126_independent_match','latest_independent_match','released_for_signals')}
    counts['configured_universe']=254
    bench_report={'independently_verified':False,'performance_eligible':False}
    bench_path=inputs/'^TASI.csv.gz'
    if bench_path.exists():
        fresh_b=pd.read_csv(bench_path,index_col='Date',parse_dates=True)
        dates=grid[-126:];a=benchmark.Close.reindex(dates);b=fresh_b.Close.reindex(dates)
        valid=a.notna()&b.notna()&a.gt(0)&b.gt(0)
        bench_report.update(fresh_rows=len(fresh_b),overlap_close_sessions=int(valid.sum()),same_vendor_close_mismatch_dates=[str(t.date()) for t in dates[valid & (a/b-1).abs().gt(.001)]],missing_required_close_dates=[str(t.date()) for t in dates[b.isna()|b.le(0)]])
    derived(current/'benchmark_audit.json',bench_report)
    summary={'schema_version':1,'run_id':os.getenv('GITHUB_RUN_ID','local'),'run_attempt':os.getenv('GITHUB_RUN_ATTEMPT','1'),'source_run_id':source['run_id'],'source_session':source['expected_session'],'created_utc':datetime.now(timezone.utc).isoformat(),'status':status,'counts':counts,'rows':rows,'repair_records_rechecked':len(repairs),'repair_basis_counts':pd.Series([r['same_vendor_basis_check'] for r in repairs],dtype=str).value_counts().to_dict(),'reference_errors':reference_errors,'adopted':False,'production_changed':False,'phase6_registered_versions_changed':False,'ledger_modified':False,'decision':'NO_RELEASE_WITHOUT_INDEPENDENT_SEQUENCE_AND_PIT_ACTION_REVIEW','limits':['Fresh raw history is candidate evidence from same vendor, not independent validation.','Do not delete widespread zero-volume dates or treat them as holidays without independent dated evidence.','Raw/adjusted basis differences alone do not prove corruption or validate old quote substitution.','No retrospective ledger rewrite or performance improvement claim.']}
    derived(current/'summary.json',summary);derived(current/'anomaly_dates.json',{'dates':anomaly});derived(current/'repair_reconciliation.json',{'rows':repairs});derived(current/'fresh_manifest.json',manifest)
    pd.DataFrame(rows).to_csv(current/'coverage.csv',index=False);pd.DataFrame(repairs).to_csv(current/'repair_reconciliation.csv',index=False);pd.DataFrame(anomaly).to_csv(current/'anomaly_dates.csv',index=False)
    text=['# معالجة عائق البيانات','',f"تشغيل التدقيق {summary['run_id']}، جلسة المصدر {source['expected_session']}.",'',json.dumps(counts,ensure_ascii=False,indent=2),'',f"إصلاحات قديمة أعيدت مقارنتها: {len(repairs)}.",'','أعيد جلب التاريخ الكامل دون إصلاح أو ملء، مع فصل الإغلاق الخام عن الإغلاق المعدل. لا تُحذف الأيام ذات الأحجام الصفرية لمجرد انتشارها. المقارنة على أساس سعري مختلف لا تثبت خطأ السعر.','', 'لم يُرفع العزل عن أي سلسلة ولم يتغير الإنتاج أو السجل المسجل مسبقًا. مطابقة المزود لنفسه لا تعوض المصدر المستقل.','', 'الخطوة المتبقية: مرجع تاريخي مستقل ذو ترخيص استخدام واضح، يتضمن OHLCV وتواريخ وأساس الأسعار وإجراءات رأس المال؛ ثم تسجيل مجموعة مستقبلية جديدة قبل أي تغيير في قواعد القياس.']
    (current/'REPORT_AR.md').write_text('\n'.join(text)+'\n')
    print(json.dumps({'counts':counts,'rechecked_repairs':len(repairs),'repair_basis_counts':summary['repair_basis_counts'],'anomalies':len(anomaly)}))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',nargs=2);p.add_argument('--snapshot');p.add_argument('--source-info');p.add_argument('--offline',action='store_true');a=p.parse_args()
    if a.worker:worker(*a.worker)
    else:run(a.snapshot,json.loads(Path(a.source_info).read_text()),offline=a.offline)
