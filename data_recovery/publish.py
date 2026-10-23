"""Atomic publication limited to recovery reports, preserving existing history."""
import os,shutil,tempfile
from pathlib import Path
from phase6.publish import git

def publish():
    run=os.environ['GITHUB_RUN_ID']+'_'+os.environ['GITHUB_RUN_ATTEMPT'];root=Path('output/data_recovery');current=root/'current'
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(current,Path(tmp)/'current')
        git('config','user.name','github-actions[bot]');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        for attempt in range(3):
            git('fetch','origin','main');git('reset','--hard','origin/main')
            history=root/'history'/run
            if history.exists():
                for p in (Path(tmp)/'current').glob('*'):
                    if not (history/p.name).exists() or (history/p.name).read_bytes()!=p.read_bytes():raise ValueError('IMMUTABLE_RECOVERY_HISTORY_CONFLICT')
            shutil.copytree(Path(tmp)/'current',history,dirs_exist_ok=True);shutil.copytree(Path(tmp)/'current',current,dirs_exist_ok=True)
            git('add',str(current),str(history))
            if git('diff','--cached','--quiet',check=False).returncode==0:return
            git('commit','-m',f'Save isolated data recovery evidence {run} [skip ci]')
            if git('push','origin','HEAD:main',check=False).returncode==0:return
        raise RuntimeError('Recovery publication failed; see artifact')
if __name__=='__main__':publish()
