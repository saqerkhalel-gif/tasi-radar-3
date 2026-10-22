"""Audit actual files; a green workflow is not a claim of full/fresh coverage."""
import json, collections, os
from pathlib import Path

def verify(root=Path('output')):
    p=json.loads((root/'latest.json').read_text())
    assert p['universe_count']==254
    if os.getenv('GITHUB_RUN_ID'): assert p['run_id']==os.environ['GITHUB_RUN_ID'], 'Output belongs to another run'
    r=p['results'];f=p['failures'];symbols=[x['symbol'] for x in r]+[x['symbol'] for x in f]
    assert len(symbols)==len(set(symbols))==254
    assert len(r)==p['scanned_successfully'] and len(f)==p['failed_count']
    assert round(100*len(r)/254,2)==p['coverage_pct']
    assert sum(x['data_fresh'] for x in r)==p['fresh_count']
    for x in r:
        assert x.get('nomination_reasons'), 'Missing explanation for ranked/monitored stock'
        assert x['data_fresh']==(x['date']==p['expected_session'])
        if x['classification'] in ('Entry','Partial Entry'):
            assert not x['entry_blockers'] and x['data_fresh'] and p['benchmark']['fresh']
            assert x['observations']['volume_confirmed'] and (x['observations']['breakout20_with_volume'] or x['observations']['reclaim_ema20_with_volume'])
            assert x['scenario']['upside_pct']>=10 and x['scenario']['reward_risk']>=2
            assert x['data_quality']['entry_eligible'] and p['benchmark_quality']['entry_eligible']
            assert not x['missing_indicators'] and x['bars']>=200
    for name in ('top20.json','watchlist.json'):
        q=json.loads((root/name).read_text());assert q['run_url']==p['run_url'] and q['run_utc']==p['run_utc']
    top=json.loads((root/'top20.json').read_text());assert top['count']==min(20,len(r))==len(top['results'])
    print(json.dumps({k:p[k] for k in ('run_url','expected_session','scanned_successfully','failed_count','coverage_pct','fresh_coverage_pct','classification_counts','benchmark','failures')},ensure_ascii=False,indent=2))
    for name in ('backtest.json','missed_opportunities.json','opportunity_ledger.json','quality_report.json'):
        doc=json.loads((root/name).read_text());assert doc['run_id']==p['run_id'] and doc['run_url']==p['run_url']
    bt=json.loads((root/'backtest.json').read_text())
    for section in ('full_period','chronological_last_30pct'):
        b=bt[section];assert b['trades_count']==len(b['trades'])
        for trade in b['trades']:
            assert trade['signal_date']<trade['entry_date']<=trade['exit_date']
            assert trade['target']/trade['entry_price']-1>=.10-1e-6
            assert (trade['target']-trade['entry_price'])/(trade['entry_price']-trade['stop'])>=2-1e-6
    # Zero successful stocks is a failed scan even though valid error files exist.
    assert r, 'No stock could be analyzed'
    summary=os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as out:
            out.write(f"## Actual data audit\n\nAnalyzed: {len(r)}/254 ({p['coverage_pct']}%). Fresh: {p['fresh_count']}/254 ({p['fresh_coverage_pct']}%). Failures: {len(f)}.\n\nExpected session: {p['expected_session']}. Price dates: {p['price_dates']}.\n\nClassifications: {p['classification_counts']}.\n\nTASI: {p['benchmark']}.\n")
if __name__=='__main__': verify()
