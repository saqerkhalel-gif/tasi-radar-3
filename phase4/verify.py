"""Fail the research run on incorrect counts, insufficient audit or live mutation."""
import argparse,hashlib,json
from pathlib import Path

def verify(output='output/phase4/current'):
    root=Path(output);r=json.loads((root/'comparison.json').read_text());q=json.loads((root/'data_quality.json').read_text());d=json.loads((root/'trade_diagnostics.json').read_text())
    assert r['frozen_baseline_reproduced'] and not r['adopted'] and not r['live_strategy_changed']
    assert len(r['variants'])==16 and len(r['all_registered_experiments'])==16
    assert d['count']==len(d['trades'])==25
    assert q['universe_count']==len(q['frozen_stock_audit'])==254 and q['frozen_quarantined_count']==239
    assert q['run_id']==r['run_id']==d['run_id'] and q['independently_verified_stock_release_count']==0
    assert r['plan_sha256']==hashlib.sha256(Path('phase4/plan.json').read_bytes()).hexdigest()
    production=json.loads(Path('phase3/production_baseline.json').read_text())
    for path,sha in production['files'].items():
        b=Path(path).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==sha,'Production changed: '+path
    for name,v in r['variants'].items():
        assert len(v['walk_forward'])==3 and v['adopted'] is False
        for result in [v['full_period'],v['stress_costs']]+[f[k] for f in v['walk_forward'] for k in ('test','stress_test')]:
            assert result['trades_count']==len(result['trades'])
            if not result['trades']:assert result['win_rate_pct'] is None and result['expectancy_pct'] is None
            for t in result['trades']:
                assert t['signal_date']<t['entry_date']<=t['exit_date']
                assert t['target']/t['entry_price']-1>=.1-1e-6 and (t['target']-t['entry_price'])/(t['entry_price']-t['stop'])>=2-1e-6
                if name!='original':assert t['planned_risk_cash']<=t['equity_at_entry']*.005+1e-4 and (t['entry_price']-t['stop'])/t['entry_price']<=.08+1e-6
            if name!='original':assert result['maximum_aggregate_planned_risk_pct']<=3+1e-6
        for f in v['walk_forward']:
            assert f['training_end']<f['purge_start']<=f['purge_end']<f['test']['start_date']
            assert f['purge_sessions']==20 and not f['virgin_out_of_sample'] and not f['parameters_fitted']
    for name in ('RESEARCH_REVIEW','DATA_QUALITY','STRATEGY_COMPARISON','WALK_FORWARD_RESULTS','DEVELOPMENT_ROADMAP'):assert (root/(name+'.md')).stat().st_size>200
    print(json.dumps({'verified_variants':16,'original_trades':25,'data_audited':254,'quarantined':239,'live_files_unchanged':True,'adopted':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='output/phase4/current');a=p.parse_args();verify(a.output)
