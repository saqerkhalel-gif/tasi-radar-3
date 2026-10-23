"""Provenance audit and causal historical eligibility; never repair vendor prices."""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,sys,tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from phase3.experiment import load_snapshot
from phase4.research import dump
from phase4.data_audit import probe,SOURCES
from phase3.quality_recheck import valid_daily_row
from research import quality_audit


def historical_window(df,sessions,minimum=126):
    if df.empty:return {'eligible':False,'reasons':['empty_history']}
    grid=sessions[sessions<=df.index[-1]][-minimum:];q=quality_audit(df,sessions[sessions<=df.index[-1]])
    values=df.reindex(grid)[['Open','High','Low','Close','Volume']]
    finite=np.isfinite(values.to_numpy()).all();p=values[['Open','High','Low','Close']]
    valid=finite and p.gt(0).all().all() and values.Volume.ge(0).all() and (values.Low<=values[['Open','Close']].min(axis=1)).all() and (values.High>=values[['Open','Close']].max(axis=1)).all()
    reasons=[]
    if len(grid)<minimum or not grid.isin(df.index).all():reasons.append('missing_required_calendar_sessions')
    if not valid:reasons.append('invalid_historical_OHLCV')
    if not q['entry_eligible']:reasons.append('unverified_repairs_jump_or_current_zero_volume')
    if df.index.duplicated().any():reasons.append('duplicate_dates')
    if df.index.tz is not None:reasons.append('unexpected_noncanonical_timezone')
    return {'eligible':not reasons,'reasons':reasons,'required_sessions':minimum,'observed_in_window':int(grid.isin(df.index).sum()),'quote_repairs':len(q['unverified_quote_repairs']),'normalization':q['normalization']}


def eligibility_panel(data,benchmark,sessions):
    columns={}
    for symbol,df in data.items():
        x=df.reindex(sessions);prices=x[['Open','High','Low','Close']]
        valid=np.isfinite(x[['Open','High','Low','Close','Volume']]).all(axis=1)&prices.gt(0).all(axis=1)&x.Volume.ge(0)&x.Low.le(x[['Open','Close']].min(axis=1))&x.High.ge(x[['Open','Close']].max(axis=1))
        complete=valid.rolling(126,min_periods=126).sum().eq(126)
        repairs={pd.Timestamp(r['date']) for r in df.attrs.get('price_repairs',[])}
        jumps=df.Close.pct_change(fill_method=None).abs().gt(.22)
        flagged=pd.Series(df.index.isin(repairs)|jumps.to_numpy(),index=df.index).rolling(200,min_periods=1).max().reindex(sessions)
        columns[symbol]=complete&flagged.eq(0)&x.Volume.gt(0)
    benchmark_complete=benchmark.Close.reindex(sessions).notna().rolling(121,min_periods=121).sum().eq(121)
    panel=pd.DataFrame(columns,index=sessions).fillna(False)
    return panel.mul(benchmark_complete,axis=0).astype(bool)


def source_worker(specfile,resultfile):
    import yfinance as yf
    spec=json.loads(Path(specfile).read_text());symbols=spec['symbols'];end=pd.Timestamp(spec['expected']);start=end-pd.Timedelta(days=540)
    data=yf.download([s+'.SR' for s in symbols]+['^TASI.SR'],start=str(start.date()),end=str((end+pd.Timedelta(days=1)).date()),auto_adjust=False,repair=False,actions=True,threads=4,group_by='ticker',progress=False,timeout=15)
    rows=[]
    for symbol in symbols+['^TASI']:
        ticker=symbol+'.SR'
        try:
            d=data[ticker].dropna(how='all');action_only=int((~d[['Open','High','Low','Close','Volume']].notna().any(axis=1)).sum());d=d.loc[d[['Open','High','Low','Close','Volume']].notna().any(axis=1)];d.index=pd.to_datetime(d.index).tz_localize(None)
            raw=[valid_daily_row(v)[0] for _,v in d.iterrows()];last=d.loc[end] if end in d.index else {}
            valid,reason=valid_daily_row(last);factor=d['Adj Close']/d.Close if 'Adj Close' in d else pd.Series(np.nan,index=d.index)
            adjusted=d[['Open','High','Low','Close']].mul(factor,axis=0);adjusted['Volume']=d.Volume
            checks=np.array([valid_daily_row(v)[0] or (v.get('Volume')==0 and valid_daily_row({**v.to_dict(),'Volume':1.})[0]) for _,v in adjusted.iterrows()])
            repaired=[]
            for repair in spec.get('repairs',{}).get(symbol,[]):
                date=pd.Timestamp(repair['date']);old=repair.get('repaired_close',repair.get('close',repair.get('replacement_close')))
                published=float(adjusted.loc[date,'Close']) if date in adjusted.index and pd.notna(adjusted.loc[date,'Close']) else None
                repaired.append({'date':repair['date'],'published_adjusted_close_now':published,'frozen_repaired_close':old,
                    'relative_difference_pct':100*(published/old-1) if published and old else None,
                    'independently_reconciled':False,'same_vendor_published_now':published is not None})
            rows.append({'symbol':symbol,'fetch_success':bool(len(d)),'vendor':'Yahoo Finance via yfinance','fetched_rows':len(d),'first_date':str(d.index[0].date()) if len(d) else None,'last_date':str(d.index[-1].date()) if len(d) else None,
                'timezone':'Daily exchange-local dates normalized naive; XSAU/Riyadh calendar','raw_basis':'unadjusted OHLC + Adj Close; adjusted OHLC = raw OHLC*AdjClose/Close; volume as supplied',
                'corporate_action_only_rows':action_only,'duplicate_dates':int(d.index.duplicated().sum()),'raw_invalid_daily_rows':len(d)-sum(raw),'adjusted_invalid_daily_rows':len(d)-int(checks.sum()),
                'zero_volume_rows':int(d.Volume.eq(0).sum()),'latest_bar_valid':valid,'latest_reason':reason,
                'adjustment_factor_available_rows':int(np.isfinite(factor).sum()),'adjustment_factor_change_rows':int((factor.pct_change(fill_method=None).abs()>1e-6).sum()),
                'dividend_events':int(d.get('Dividends',pd.Series(dtype=float)).fillna(0).ne(0).sum()),'split_events':int(d.get('Stock Splits',pd.Series(dtype=float)).fillna(0).ne(0).sum()),
                'same_vendor_repaired_dates_recheck':repaired,'content_sha256':hashlib.sha256(d.to_csv().encode()).hexdigest(),
                'historical_series_independently_validated':False,'automatic_release':False})
        except Exception as e:rows.append({'symbol':symbol,'fetch_success':False,'latest_bar_valid':False,'reason':str(e)[:220],'historical_series_independently_validated':False,'automatic_release':False})
    Path(resultfile).write_text(json.dumps(rows,allow_nan=False))


def audit(snapshot,output,offline=False):
    data,b,sessions,cfg,p,bt=load_snapshot(snapshot);rows=[];repairs={}
    for symbol,d in data.items():
        q=quality_audit(d,sessions);w=historical_window(d,sessions);repairs[symbol]=[]
        for item in q['unverified_quote_repairs']:
            date=pd.Timestamp(item['date']);repairs[symbol].append({**item,'repaired_close':float(d.loc[date,'Close']) if date in d.index else None})
        rows.append({'symbol':symbol,'vendor':'Yahoo Finance via yfinance','price_basis':'vendor auto-adjusted OHLCV; quote-replaced closes explicitly quarantined',
            'timezone':'Asia/Riyadh daily session dates; stored naive date labels','first_observed_date':str(d.index[0].date()),'last_date':str(d.index[-1].date()),'rows':len(d),
            'fetch_success_frozen':True,'latest_bar_valid_frozen':valid_daily_row(d.iloc[-1])[0], 'fresh_frozen':str(d.index[-1].date())==p['expected_session'],
            'historical_vendor_window_eligible':w['eligible'],'historical_series_independently_validated':False,'backtest_eligible_current_window':w['eligible'],
            'live_entry_eligible_research':False,'entry_status_reason':'Research never authorizes production Entry; independent provenance incomplete',
            'window_reasons':';'.join(w['reasons']),'quote_repair_count':len(repairs[symbol]),'quarantined':not q['entry_eligible'],
            'missing_sessions':q['missing_session_count'],'zero_volume_rows':q['zero_volume_rows'],'duplicate_dates':int(d.index.duplicated().sum()),
            'unexplained_jump_dates':q['large_adjusted_price_jumps'],'normalization':q['normalization'],'repairs':repairs[symbol],'input_sha256':bt['data_hashes'][symbol]})
    fresh=[];providers=[];status='offline_fresh_coverage_unknown'
    if not offline:
        with ThreadPoolExecutor(max_workers=4) as pool:providers=list(pool.map(lambda s:probe(s,b),SOURCES))
        with tempfile.TemporaryDirectory() as tmp:
            spec=Path(tmp)/'spec.json';result=Path(tmp)/'result.json';spec.write_text(json.dumps({'symbols':list(data),'expected':p['expected_session'],'repairs':repairs}))
            try:
                cp=subprocess.run([sys.executable,'-m','phase5.data','--worker',str(spec),str(result)],capture_output=True,text=True,timeout=240)
                if cp.returncode:raise RuntimeError(cp.stderr[-500:])
                fresh=json.loads(result.read_text());status='completed'
            except Exception as e:status='fresh_request_failed_or_timed_out: '+str(e)[:260]
    now=datetime.now(timezone.utc).isoformat();stocks=[x for x in fresh if x['symbol']!='^TASI'];independent=False
    report={'schema_version':1,'run_id':os.getenv('GITHUB_RUN_ID','local'),'audit_utc':now,'snapshot_run_id':p['run_id'],'price_session':p['expected_session'],'status':status,
        'denominators':{'universe':254,'quarantined_frozen':sum(x['quarantined'] for x in rows),'frozen_fetch_success':len(rows),'frozen_latest_bar_valid':sum(x['latest_bar_valid_frozen'] for x in rows),
          'historical_vendor_window_eligible':sum(x['historical_vendor_window_eligible'] for x in rows),'independently_validated_historical_series':0,'live_entries_authorized':0,
          'fresh_stock_fetch_success':sum(x['fetch_success'] for x in stocks) if stocks else None,'fresh_latest_valid':sum(x['latest_bar_valid'] for x in stocks) if stocks else None},
        'symbols':rows,'fresh_same_vendor':fresh,'independent_provider_probes':providers,'releases':[],
        'benchmark':{'symbol':'^TASI.SR','frozen_rows':len(b),'first_date':str(b.index[0].date()),'last_date':str(b.index[-1].date()),'metadata':b.attrs,
          'close_sha256':hashlib.sha256(b.to_csv().encode()).hexdigest(),'complete_recent121_calendar_sessions':b.Close.reindex(sessions[-121:]).notna().all(),
          'entire_history_independently_validated':independent,'fresh_yahoo_index':[x for x in fresh if x['symbol']=='^TASI'],'note':'Merged Investing seed/cache plus sparse Yahoo observations; no forward fill; a current matching quote cannot validate every historical date.'},
        'sector_proxy':{'source':'data/tasi_symbols.csv current membership; leave-target-out equal-weight peers','membership_point_in_time_available':False,'survivorship_bias_unresolved':True,'minimum_other_peers':3,'minimum_coverage_each_session':.8,'used_for_core_entry_gate':False,'variant_with_missing_proxy':'blocked'},
        'terms_and_access':{'Yahoo':'yfinance is unofficial; research/personal-use only notice, provider terms control; access not redistribution permission. https://ranaroussi.github.io/yfinance/',
          'Saudi Exchange':'Official historical and corporate-action reference sought; no WAF/paywall/authentication bypass. Public site does not establish bulk automation entitlement.',
          'Stooq':'Public index CSV probe only; no assumed stock coverage or redistribution licence. https://stooq.com/q/d/?s=%5Etasi',
          'Mubasher':'Public quote page is not an established licensed historical OHLCV feed; no full-history claim.',
          'Twelve Data':'XSAU requires paid Pro+/Venture+ entitlement; no verified free Saudi EOD access. https://twelvedata.com/exchanges/XSAU'},
        'request_policy':{'public_probes':4,'timeout_seconds_each':20,'yahoo_download_batch_calls':0 if offline else 1,'yahoo_internal_threads':4,'yahoo_worker_timeout_seconds':240,'rate_limit_policy':'No retry on denial, no bypass; yfinance may batch internal ticker requests. No contractual public rate limit established; stop on error/timeout.'},
        'scope':'No frozen data, quarantine or production gate modified. Latest validity, causal-window eligibility and independent full-series verification are different denominators. Vendor-consistent causal-prefix tests are exploratory, not validated independent evidence.'}
    out=Path(output);panel=eligibility_panel(data,b,sessions);out.mkdir(parents=True,exist_ok=True);panel.sum(axis=1).rename('eligible_vendor_window_symbols').to_csv(out/'ELIGIBLE_UNIVERSE_BY_SESSION.csv');report['causal_eligibility_by_session']={str(date.date()):int(value) for date,value in panel.sum(axis=1).items()};dump(out/'data_provenance.json',report);pd.json_normalize(rows).to_csv(out/'QUARANTINE.csv',index=False)
    lines=['# DATA PROVENANCE — Phase 5','',f'Audit {now}; source run {p["run_id"]}; price session {p["expected_session"]}.',
      '', '## Separate denominators', '', '| Status | Stocks /254 |','|---|---:|']
    lines+=['| '+k+' | '+str(v)+' |' for k,v in report['denominators'].items()]
    lines+=['', '## Recovery decision', '', '**No historical quarantine released.** Fresh published closes, even when they now match an old quote replacement, are same-vendor evidence and do not establish an independently reconciled entire history. Every old repair is rechecked by date when available; disagreements remain visible in JSON. Missing data stays missing. No interpolation or price invention.',
      '', '## Historical eligibility', '', 'QUARANTINE.csv contains all254 names, observed date range, vendor/basis/timezone, normalization, missing sessions, zero volume, duplicate dates, repairs, jumps and separate statuses. Zero-volume historical sessions are recorded, not invented trades. Causal backtests assess the known prefix at each signal; a future repair must not retroactively disqualify an earlier signal. This remains a vendor-screened exploration, not independent validation.',
      '', '## Sources and reproducibility', '', *['- '+k+': '+v for k,v in report['terms_and_access'].items()],
      '', *['- '+x['source']+': HTTP '+str(x.get('http_status','unknown'))+'; '+x['status']+'; verified full stock histories: 0.' for x in providers],
      '', 'Each response/download is hashed and timestamped; frozen per-stock hashes bind every comparison. All access failures and unknown coverage remain explicit. No paid access or denied-page circumvention.',
      '', '## TASI and sector provenance', '', 'TASI uses the frozen observed seed/cache and sparse Yahoo quote merge. Recent121-session completeness is '+str(report['benchmark']['complete_recent121_calendar_sessions'])+'. Full history has NOT been independently exchange-reconciled. Sector proxies use current membership, not historical constituents; exclusion of the target and missing/quarantined peer observations reduces contamination but cannot remove survivorship bias. Core hypotheses report sectors without making this uncertain proxy mandatory; a separate registered gate tests sensitivity.',
      '', '## Remaining limits', '', 'Delisted/point-in-time universe and complete historical corporate-action vintages are unavailable. Fresh raw OHLC, Adj Close factors and reported split/dividend counts are audited, but rights issues and all adjustment revisions remain unverified. Independent full-series denominator is zero; no promotion is possible from this audit.']
    (out/'DATA_PROVENANCE.md').write_text('\n'.join(lines)+'\n');print(json.dumps(report['denominators']));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot');p.add_argument('--output',default='output/phase5/current');p.add_argument('--offline',action='store_true');p.add_argument('--worker',nargs=2);a=p.parse_args()
    if a.worker:source_worker(*a.worker)
    else:audit(a.snapshot,a.output,a.offline)
