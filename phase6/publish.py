"""Publish only phase6 outputs atomically; refuse durable edits/deletions."""
import json,os,shutil,subprocess,tempfile
from pathlib import Path
from phase6.ledger import derived

def git(*args,check=True):return subprocess.run(['git',*args],check=check,capture_output=True,text=True)

def guard(previous,proposed):
    for folder in ('ledger','history'):
        for old in (Path(previous)/folder).rglob('*'):
            if not old.is_file() or old.name.startswith('.'):continue
            new=Path(proposed)/old.relative_to(previous)
            if not new.is_file() or old.read_bytes()!=new.read_bytes():raise ValueError('DURABLE_EDIT_OR_DELETION:'+str(old))

def publish():
    from phase6.verify import verify
    verify();root=Path('output/phase6');run=os.environ['GITHUB_RUN_ID']+'_'+os.environ['GITHUB_RUN_ATTEMPT']
    history=root/'history'/run;history.mkdir(parents=True,exist_ok=True)
    for path in (root/'current').glob('*'):
        target=history/path.name
        if target.exists() and target.read_bytes()!=path.read_bytes():raise ValueError('HISTORY_CHANGED')
        shutil.copy2(path,target)
    with tempfile.TemporaryDirectory() as temp:
        proposed=Path(temp)/'proposed';shutil.copytree(root,proposed,ignore=shutil.ignore_patterns('.*'))
        git('config','user.name','github-actions[bot]');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        for attempt in range(3):
            git('fetch','origin','main');git('reset','--hard','origin/main');guard(root,proposed)
            if root.exists():shutil.rmtree(root)
            shutil.copytree(proposed,root);verify();git('add',str(root))
            if git('diff','--cached','--quiet',check=False).returncode==0:break
            git('commit','-m',f'Save phase6 forward ledger {run} [skip ci]')
            if git('push','origin','HEAD:main',check=False).returncode==0:break
        else:raise RuntimeError('Publication failed; immutable artifact retains results')
        derived('phase6_publication_receipt.json',{'commit':git('rev-parse','HEAD').stdout.strip(),'run':run,'ledger':verify(),'owner_proof_worm':False})

if __name__=='__main__':publish()
