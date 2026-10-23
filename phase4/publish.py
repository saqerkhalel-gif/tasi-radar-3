"""Publish only this run's phase4 subtree; retry safely across daily publishers."""
import argparse,os,shutil,subprocess,tempfile
from pathlib import Path

def git(*args,check=True):return subprocess.run(['git',*args],check=check,capture_output=True,text=True)

def publish(research):
    run=os.environ['GITHUB_RUN_ID']+'_'+os.environ['GITHUB_RUN_ATTEMPT'];root=Path('output/phase4')
    paths=['shadow']
    if research:
        history=root/'history'/run;history.mkdir(parents=True,exist_ok=True)
        shutil.copytree(root/'current',history,dirs_exist_ok=True);paths+=['current','history/'+run]
    with tempfile.TemporaryDirectory() as tmp:
        for path in paths:shutil.copytree(root/path,Path(tmp)/path,dirs_exist_ok=True)
        git('config','user.name','github-actions[bot]');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        for attempt in range(3):
            git('fetch','origin','main');git('reset','--hard','origin/main')
            for path in paths:shutil.copytree(Path(tmp)/path,root/path,dirs_exist_ok=True)
            git('add',*[str(root/path) for path in paths])
            if git('diff','--cached','--quiet',check=False).returncode==0:return
            git('commit','-m',f'Save phase 4 shadow research {run} [skip ci]')
            result=git('push','origin','HEAD:main',check=False)
            if result.returncode==0:return
        raise RuntimeError('Phase4 publication failed after three fresh-head retries; artifact retains results.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--research',action='store_true');a=p.parse_args();publish(a.research)
