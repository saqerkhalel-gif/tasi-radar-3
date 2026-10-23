"""Validate actual research files, original strategy invariance and entry/risk gates."""
import argparse,hashlib,json,os
from pathlib import Path
from phase3.experiment import load_snapshot


def verify(root,snapshot):
    root=Path(root);r=json.loads((root/'comparison.json').read_text());q=json.loads((root/'quality_recheck.json').read_text());lock=json.loads((root/'selection_lock.json').read_text())
    expected=os.getenv('GITHUB_RUN_ID','local');assert r['run_id']==q['run_id']==expected
    assert r['frozen_run_id']=='39870228858' and r['frozen_baseline_reproduced']
    assert not r['selection']['adopted'] and r['selection']['live_strategy']=='baseline'
    assert r['selection']==lock['selection'] and lock['created_before_candidate_test_evaluation']
    assert r['plan_sha256']==hashlib.sha256(Path('phase3/plan.json').read_bytes()).hexdigest()==lock['plan_sha256']
    production=json.loads(Path('phase3/production_baseline.json').read_text())
    for name,sha in production['files'].items():
        content=Path(name).read_bytes();assert hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()==sha,'Live source changed: '+name
    data,b,sessions,cfg,p,frozen=load_snapshot(snapshot)
    signals=json.loads((root/'baseline_signals.json').read_text());lookup={(s,item['date']):item for rows in signals.values() for s,item in rows}
    for name,sections in r['variants'].items():
        for period in ('development','full_period','reused_temporal_test'):
            result=sections[period];assert result['trades_count']==len(result['trades'])
            if not result['trades']:assert result['win_rate_pct'] is None
            for trade in result['trades']:
                signal=lookup[(trade['symbol'],trade['signal_date'])];assert not signal['entry_blockers']
                assert signal['data_quality']['entry_eligible'] and signal['data_fresh'] and signal['bars']>=200
                obs=signal['observations'];assert obs['volume_confirmed'] and (obs['breakout20_with_volume'] or obs['reclaim_ema20_with_volume'])
                assert trade['signal_date']<trade['entry_date']<=trade['exit_date']
                assert trade['target']/trade['entry_price']-1>=.10-1e-6
                assert (trade['target']-trade['entry_price'])/(trade['entry_price']-trade['stop'])>=2-1e-6
                if name.startswith('stop_'):
                    assert trade['planned_risk_cash']<=trade['same_signal_baseline_risk_cash']+1e-4
                    assert trade['planned_risk_cash']<=trade['equity_at_entry']*.005+1e-4
                    assert (trade['entry_price']-trade['stop'])/trade['entry_price']<=.08+1e-6
            if name.startswith('stop_'):assert result['maximum_aggregate_planned_risk_pct']<=3+1e-6
    assert r['split']['purge_sessions']==20 and r['split']['development_end']<r['split']['purge_start']<r['split']['test_start']
    diagnostics=json.loads((root/'trade_diagnostics.json').read_text());assert diagnostics['count']==len(diagnostics['trades'])==25
    assert diagnostics['run_id']==expected and q['frozen_experiment_inputs_changed'] is False
    assert q['quarantined_in_frozen_snapshot']==p['quarantined_stock_count'] and q['independently_verified_release_count']==0
    assert q['live_gate_changes'] is False
    for name in ('comparison.csv','REPORT.md','trade_diagnostics.csv'):assert (root/name).stat().st_size>0
    print(json.dumps({'research_run':r['run_url'],'baseline_trades_verified':25,'variant_count':len(r['variants']),
                      'adopted':False,'live_files_unchanged':True,'quality_status':q['status'],'split':r['split']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='output/phase3/current');p.add_argument('--snapshot',required=True);a=p.parse_args();verify(a.root,a.snapshot)
