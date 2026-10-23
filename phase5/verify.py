"""Verify actual files, all experiments, data denominators and immutable live source."""
import argparse,hashlib,json,os
from pathlib import Path

def verify(output='output/phase5/current'):
    root=Path(output);r=json.loads((root/'comparison.json').read_text());q=json.loads((root/'data_provenance.json').read_text());d=json.loads((root/'trade_diagnostics.json').read_text())
    assert r['run_id']==q['run_id']==d['run_id']==os.getenv('GITHUB_RUN_ID','local')
    assert len(r['variants'])==len(r['registry'])==24 and r['all24_cases_reported']
    assert r['legacy_reproductions']['original25']['trades_count']==25 and r['legacy_reproductions']['phase4_early31']['trades_count']==31
    assert d['cohort_counts']=={'baseline':25,'phase4_early_reversal':31} and len(d['trades'])==56
    assert len(q['symbols'])==254 and q['denominators']['quarantined_frozen']==239 and not q['releases']
    assert q['denominators']['independently_validated_historical_series']==0
    assert not r['adopted'] and not r['live_files_changed'] and r['fresh_completed_trades']==0
    assert r['protocol_sha256']==hashlib.sha256(Path('phase5/protocol.json').read_bytes()).hexdigest()
    production=json.loads(Path('phase5/protected_files.json').read_text())
    for path,sha in production.items():
        b=Path(path).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==sha,'Protected file changed: '+path
    for name,v in r['variants'].items():
        assert len(v['walk_forward'])==3
        for f in v['walk_forward']:
            assert f['training_end']<f['purge_start']<=f['purge_end']<f['test']['start_date'] and f['purge_sessions']==20
            assert f['prior_test_and_post_test20_labels_excluded_from_training'] and not f['virgin_OOS'] and not f['parameters_fitted']
        for result in [v['full_period'],v['stress_costs']]+[f[k] for f in v['walk_forward'] for k in ('test','stress_test')]:
            assert result['trades_count']==len(result['trades'])
            if not result['trades']:assert result['win_rate_pct'] is None and result['expectancy_pct'] is None
            if result['stale_mark_position_days']:assert result['comparison_valid'] is False
            assert result['maximum_aggregate_planned_risk_pct']<=3+1e-6
            for t in result['trades']:
                assert t['signal_date']<t['entry_date']<=t['exit_date']
                assert t['target']/t['entry_price']-1>=.1-1e-6 and (t['target']-t['entry_price'])/(t['entry_price']-t['stop'])>=2-1e-6
                assert (t['entry_price']-t['stop'])/t['entry_price']<=.08+1e-6
                assert t['planned_risk_cash']<=t['equity_at_entry']*.005+1e-4
    for v in r['decisions'].values():assert v['decision']=='KEEP SHADOW' and v['evidence_status']=='INCONCLUSIVE' and not v['promoted']
    for name in ('DATA_PROVENANCE.md','QUARANTINE.csv','TRADE_DIAGNOSTICS.csv','TRADE_EXCURSIONS.csv','HYPOTHESES.md','WALK_FORWARD.md','DECISION.md','MISSED_OPPORTUNITIES.csv'):
        assert (root/name).stat().st_size>0
    (root/'COMPLETION.md').write_text('# Phase5 completion record\n\n- [x] All254 symbols and239 quarantined histories audited with separate denominators.\n- [x] All25 baseline and31 phase4 early-reversal trades diagnosed.\n- [x] Three independent hypotheses and all24 registered comparisons executed.\n- [x] Tests and actual metrics verified; report run identity in comparison.json.\n- [x] Explicit KEEP SHADOW / INCONCLUSIVE decision; no independent improvement claimed.\n- [x] Production entry rules,254-symbol list, existing workflows and source plan hashes unchanged.\n\nUnresolved: independently reconciled full history, historical constituents/corporate-action vintages, and sufficient fresh unseen forward trades. These limits prevent promotion; successful Actions execution is not evidence of profitable trading.\n')
    print(json.dumps({'run_id':r['run_id'],'experiments':24,'diagnosed_trades':56,'audited_symbols':254,'protected_files_unchanged':True,'adopted':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='output/phase5/current');a=p.parse_args();verify(a.output)
