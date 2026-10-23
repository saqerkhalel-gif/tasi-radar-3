import argparse,json
from pathlib import Path
import pandas as pd
from phase3.experiment import load_snapshot
from phase5.hypotheses import prepare
from phase5.missed import review

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',default='output/phase5/current');a=p.parse_args()
    data,b,sessions,cfg,latest,bt=load_snapshot(a.snapshot);prepared={s:prepare(d,b,sessions) for s,d in data.items()}
    stored=json.loads((Path(a.output)/'candidate_signals.json').read_text());signals={}
    for day,rows in stored.items():
        for r in rows:signals.setdefault(r['engine'],{}).setdefault(pd.Timestamp(day),[]).append((r['symbol'],r))
    result=review(data,prepared,sessions,signals,a.output);print(json.dumps({k:v for k,v in result.items() if k!='events'}))
