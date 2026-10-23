"""Read-only GitHub source identity capture. Never write tokens to output."""
import argparse,json,os
from pathlib import Path
import requests
from phase6.ledger import derived

def fetch(run_id,destination):
    repo=os.getenv('GITHUB_REPOSITORY','saqerkhalel-gif/tasi-radar-3');token=os.environ['GH_TOKEN']
    r=requests.get(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'},timeout=30);r.raise_for_status();data=r.json()
    result={k:data[k] for k in ('id','event','conclusion','head_branch','head_sha','run_attempt','created_at','updated_at','name','html_url')}
    assert data['repository']['full_name']==repo
    derived(destination,result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--output',default='source_run.json');a=p.parse_args();fetch(a.run_id,a.output)
