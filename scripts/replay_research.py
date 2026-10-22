"""Replay artifact research inputs without any network access.
Usage: python scripts/replay_research.py /path/to/research_inputs --output replay
"""
import argparse, hashlib, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from radar import analyze, indicators, clean, session_calendar
from research import historical_research
from datetime import datetime, timezone

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('--output',type=Path,default=Path('replay'));a=p.parse_args()
    cfg=json.loads((a.inputs/'config.json').read_text());meta=json.loads((a.inputs/'stock_metadata.json').read_text())
    histories={}
    for path in sorted(a.inputs.glob('*.csv.gz')):
        d=pd.read_csv(path,index_col='Date',parse_dates=True,float_precision='round_trip');symbol=path.name.split('.')[0];d.attrs.update(meta[symbol]);histories[symbol]=d
    benchmark=pd.read_csv(a.inputs/'benchmark.csv',index_col='Date',parse_dates=True,float_precision='round_trip');benchmark.attrs.update(json.loads((a.inputs/'benchmark_metadata.json').read_text()))
    end=max(d.index[-1] for d in histories.values());now=datetime.fromisoformat(str(end.date())+'T20:00:00+00:00');sessions,_=session_calendar(now,cfg)
    backtest,missed=historical_research(histories,benchmark,sessions,cfg,analyze,indicators)
    a.output.mkdir(exist_ok=True,parents=True)
    for name,doc in [('backtest.json',backtest),('missed_opportunities.json',missed)]:
        (a.output/name).write_text(json.dumps(clean(doc),ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps(clean(backtest['full_period']),ensure_ascii=False))
