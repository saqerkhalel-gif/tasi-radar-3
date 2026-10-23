"""Verify protected production blobs and complete, hash-linked phase6 transactions."""
import hashlib,json
from pathlib import Path
from phase6.ledger import Ledger

def verify(root='output/phase6'):
    protected=json.loads(Path('phase6/protected_files.json').read_text())
    for name,expected in protected.items():
        content=Path(name).read_bytes();actual=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        if actual!=expected:raise ValueError('PROTECTED_FILE_CHANGED:'+name)
    root=Path(root);ledger=Ledger(root/'ledger')
    for event in ledger.events:
        if event['kind']=='SOURCE_SEALED' and 'source-complete:'+event['payload']['source_run_id'] not in ledger.ids:raise ValueError('INCOMPLETE_SOURCE_TRANSACTION')
        if event['kind']=='SESSION_RECORDED' and event['payload']['source_event']!='schedule':raise ValueError('NON_SCHEDULED_PROSPECTIVE_SESSION')
    summary=json.loads((root/'current/summary.json').read_text());manifest=json.loads((root/'current/manifest.json').read_text())
    if manifest['ledger']!=ledger.manifest():raise ValueError('MANIFEST_MISMATCH')
    if summary['prospective_session_count']!=sum(e['kind']=='SESSION_RECORDED' for e in ledger.events):raise ValueError('SESSION_COUNT_MISMATCH')
    return ledger.manifest()

if __name__=='__main__':print(json.dumps(verify()))
