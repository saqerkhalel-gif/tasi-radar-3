"""Raw-vintage acquisition and fail-closed quality gates; no repairs or interpolation."""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from phase3.quality_recheck import valid_daily_row
from phase4.data_audit import probe,SOURCES
from phase5.data import historical_window
from research import quality_audit
from phase6.ledger import sha,canonical,derived

FIELDS=('Open','High','Low','Close','Volume')

def raw_row(row):
    return {k:float(row[k]) if k in row and pd.notna(row[k]) and np.isfinite(float(row[k])) else None for k in FIELDS}

def cross_source(raw,reference):
    if not reference or reference.get('provider')==raw.get('provider') or not reference.get('usage_permitted') or not reference.get('retrieved_utc') or not reference.get('content_sha256') or not reference.get('url'):return False
    if raw['symbol']!=reference.get('symbol') or raw['date']!=reference.get('date'):return False
    a=raw['ohlcv'];b=reference.get('ohlcv',{})
    if not valid_daily_row(a)[0] or not valid_daily_row(b)[0]:return False
    return all(abs(a[k]/b[k]-1)<=.001 for k in FIELDS[:4]) and abs(a['Volume']-b['Volume'])<=max(1,.001*b['Volume'])

def worker(specfile,resultfile):
    import yfinance as yf
    spec=json.loads(Path(specfile).read_text());end=pd.Timestamp(spec['expected_session']);start=end-pd.Timedelta(days=540);symbols=spec['symbols']
    downloaded=yf.download([s+'.SR' for s in symbols]+['^TASI.SR'],start=str(start.date()),end=str((end+pd.Timedelta(days=1)).date()),auto_adjust=False,repair=False,actions=True,threads=4,group_by='ticker',progress=False,timeout=15)
    records={};at=datetime.now(timezone.utc).isoformat()
    for symbol in symbols+['^TASI']:
        try:
            d=downloaded[symbol+'.SR'].copy();d.index=pd.to_datetime(d.index).tz_localize(None);d=d.loc[d[list(FIELDS)].notna().any(axis=1)]
            bars={}
            for date,row in d.tail(65).iterrows():
                bars[str(date.date())]={'provider':'Yahoo Finance','symbol':symbol,'date':str(date.date()),'ohlcv':raw_row(row),
                  'dividend':float(row.get('Dividends',0)) if pd.notna(row.get('Dividends',0)) else 0.,
                  'split':float(row.get('Stock Splits',0)) if pd.notna(row.get('Stock Splits',0)) else 0.}
            factor=d['Adj Close']/d.Close if 'Adj Close' in d else pd.Series(np.nan,index=d.index)
            records[symbol]={'fetch_success':bool(len(d)),'source_sha256':hashlib.sha256(d.to_csv().encode()).hexdigest(),'rows':len(d),'bars':bars,
              'first_date':str(d.index[0].date()) if len(d) else None,'last_date':str(d.index[-1].date()) if len(d) else None,
              'duplicate_dates':int(d.index.duplicated().sum()),'zero_volume_rows':int(d.Volume.eq(0).sum()),
              'invalid_raw_rows':sum(not valid_daily_row(r)[0] for _,r in d.iterrows()),'adjustment_factor_available_rows':int(np.isfinite(factor).sum()),
              'adjustment_factor_changes':int(factor.pct_change(fill_method=None).abs().gt(1e-6).sum()),'basis':'unadjusted published OHLCV; Adj Close inspected, never used to rescale ledger levels'}
        except Exception as e:records[symbol]={'fetch_success':False,'reason':str(e)[:220],'bars':{}}
    result={'provider':'Yahoo Finance','fetched_utc':at,'expected_session':spec['expected_session'],'records':records,'references':[],
      'rights':'Unofficial personal/research-use access; provider terms apply. No automatic redistribution licence; no quote substitute, no repair, no interpolation.'}
    Path(resultfile).write_bytes(canonical(result))

def acquire(symbols,expected,out,benchmark,offline=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if offline:
        report={'provider':'not_fetched','fetched_utc':datetime.now(timezone.utc).isoformat(),'expected_session':expected,'records':{},'references':[],'status':'OFFLINE_NO_EXECUTION_EVIDENCE','independent_probes':[]}
    else:
        with tempfile.TemporaryDirectory() as tmp:
            spec=Path(tmp)/'spec.json';dest=Path(tmp)/'raw.json';spec.write_bytes(canonical({'symbols':list(symbols),'expected_session':expected}))
            try:
                cp=subprocess.run([sys.executable,'-m','phase6.quality','--worker',str(spec),str(dest)],capture_output=True,text=True,timeout=240)
                if cp.returncode:raise ValueError(cp.stderr[-500:])
                report=json.loads(dest.read_text());report['status']='RAW_DOWNLOAD_COMPLETED'
            except Exception as e:report={'provider':'Yahoo Finance','records':{},'references':[],'status':'RAW_DOWNLOAD_FAILED','reason':str(e)[:260],'fetched_utc':datetime.now(timezone.utc).isoformat(),'expected_session':expected}
        with ThreadPoolExecutor(max_workers=4) as pool:report['independent_probes']=list(pool.map(lambda s:probe(s,benchmark),SOURCES))
    derived(out/'raw_acquisition.json',report)
    return report

def inspect(data,benchmark,sessions,source,raw):
    expected=source['expected_session'];rows=[];records=raw.get('records',{});refs=raw.get('references',[]);thin={}
    for symbol,d in data.items():
        h=historical_window(d,sessions[sessions<=pd.Timestamp(expected)]);q=quality_audit(d,sessions[sessions<=pd.Timestamp(expected)]);r=records.get(symbol,{}).get('bars',{}).get(expected)
        current=d.loc[pd.Timestamp(expected)] if pd.Timestamp(expected) in d.index else None
        published=bool(r and valid_daily_row(r['ohlcv'])[0]);agrees=False
        if published and current is not None and valid_daily_row(current)[0]:
            agrees=all(abs(float(current[k])/r['ohlcv'][k]-1)<=.001 for k in FIELDS[:4]) and abs(float(current.Volume)-r['ohlcv']['Volume'])<=max(1,.001*r['ohlcv']['Volume'])
        independent=bool(r and any(cross_source(r,x) for x in refs))
        grid=sessions[sessions<=pd.Timestamp(expected)][-126:];v=d.reindex(grid)
        zero_history=not len(grid)==126 or not v.Volume.gt(0).all()
        reasons=list(h['reasons'])
        if zero_history:reasons.append('zero_missing_volume_in_required_history')
        if current is None or str(d.index[-1].date())!=expected:reasons.append('stale_or_missing_signal_bar')
        if not published:reasons.append('no_valid_published_raw_bar')
        elif not agrees:reasons.append('adjusted_decision_and_raw_current_bar_disagree')
        if r and (r['dividend'] or r['split']):reasons.append('capital_action_requires_verification')
        eligible=not reasons
        rows.append({'symbol':symbol,'fetched':True,'latest_valid':bool(current is not None and valid_daily_row(current)[0]),'last_date':str(d.index[-1].date()),
          'historical_vendor_window_eligible':h['eligible'],'signal_eligible':eligible,'independently_validated_historical_sequence':False,'eligible_for_historical_backtest':False,
          'published_raw_bar_valid':published,'raw_agrees_with_decision_bar':agrees,'independent_current_bar_match':independent,'execution_bar_verifiable':published and independent and agrees,
          'quarantined':not q['entry_eligible'],'repair_count':len(q['unverified_quote_repairs']),'zero_volume_rows':q['zero_volume_rows'],'missing_sessions':q['missing_session_count'],
          'duplicate_dates':int(d.index.duplicated().sum()),'capital_action_or_jump_dates':q['large_adjusted_price_jumps'],'eligibility_reasons':reasons,
          'price_basis':'Archived adjusted decision-time vintage; execution uses raw, never retrospectively rescaled','timezone':'Asia/Riyadh session labels; observations UTC'})
        thin[symbol]={'raw':r,'decision_bar':raw_row(current) if current is not None else None,'full_input_hash':hashlib.sha256(d.to_csv().encode()).hexdigest(),
          'raw_series_hash':records.get(symbol,{}).get('source_sha256'),'raw_audit':{k:v for k,v in records.get(symbol,{}).items() if k!='bars'}}
    zeros=pd.DataFrame({s:d.Volume for s,d in data.items()})
    count=zeros.notna().sum(axis=1);z=zeros.eq(0).sum(axis=1)
    anomalies=[{'date':str(t.date()),'observed':int(count[t]),'zero_volume':int(z[t])} for t in zeros.index[(count>=50)&(z/count>=.8)]]
    denominators={'configured_universe':254,'fetched':len(data),'latest_valid':sum(x['latest_valid'] for x in rows),'historical_vendor_window_eligible':sum(x['historical_vendor_window_eligible'] for x in rows),
      'independently_validated_historical':0,'historical_backtest_eligible':0,'signal_eligible':sum(x['signal_eligible'] for x in rows),
      'published_raw_bar_valid':sum(x['published_raw_bar_valid'] for x in rows),'independent_current_bar_matched':sum(x['independent_current_bar_match'] for x in rows),
      'execution_bar_verifiable':sum(x['execution_bar_verifiable'] for x in rows),'quarantined':sum(x['quarantined'] for x in rows)}
    report={'schema_version':1,'source_run_id':source['run_id'],'price_session':expected,'denominators':denominators,'symbols':rows,'market_wide_zero_volume_dates':anomalies,
      'source_inventory':{'decision_feed':'Yahoo via production yfinance auto-adjusted; archived vintage only; no claim of historical PIT availability',
        'execution_feed':{'provider':raw.get('provider'),'status':raw.get('status'),'fetched_utc':raw.get('fetched_utc'),'basis':'published raw OHLCV, no auto adjustment/repair','stock_raw_fetch_success':sum(r.get('fetch_success',False) for s,r in records.items() if s!='^TASI')},
        'independent_probes':raw.get('independent_probes',[]),'independent_references_accepted':len(refs),
        'rights':'Yahoo personal/research-only notice: https://ranaroussi.github.io/yfinance/ ; no source wall/403/paywall/rate-limit bypass. Public quote page does not establish a licensed historical feed. Saudi Exchange public historical/market-watch and Mubasher/Stooq probes report actual coverage, not assumed entitlement. Twelve Data XSAU paid entitlement is not a verified free alternative.',
        'limits':'One bounded Yahoo batch (internal4 threads,240s timeout); four public probes20s each, no retry on denied access; no paid data. Complete raw download hashes retained, current raw bars sealed; full inputs in artifact90days.',
        'corporate_actions':'Raw dividends/splits and factor changes inspected; full rights/capital-action/PIT vintages unavailable; active position freezes on an action/revision.'},
      'benchmark':{'symbol':'^TASI.SR','last_date':str(benchmark.index[-1].date()),'observed_rows':len(benchmark),'metadata':benchmark.attrs,'independently_verified_sequence':False,'performance_comparison_valid':False,'no_forward_fill':True},
      'sector_proxy':{'current_constituents_only':True,'point_in_time_membership_available':False,'method':'Existing leave-target-out equal-weight peers,>=3 and80% coverage; no historical official sector claim'},
      'lookahead_policy':'No phase6 historical backtest. Decision-time vintage sealed before next open; future adjusted revisions never rewrite past predictions/executions. Pre-registration historical values are unverified PIT and excluded from promotion.',
      'remaining_limits':['Current254 constituents omit historical delistings/survivors; never claim selection-bias eliminated.','Internal bar checks are not independent exchange reconciliation.','Independent complete historical coverage0; no promotion if benchmark/price histories unvalidated.']}
    return report,thin

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',nargs=2,required=True);a=p.parse_args();worker(*a.worker)
