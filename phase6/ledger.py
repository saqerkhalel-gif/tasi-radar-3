"""Atomic append-only, hash-linked event storage and content-addressed objects."""
from __future__ import annotations
import hashlib,json,os,tempfile,fcntl
from contextlib import contextmanager
from pathlib import Path

ZERO='0'*64

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def sha(value):return hashlib.sha256(canonical(value)).hexdigest()

def write_exclusive(path,value):
    """Publish a fully-written inode atomically. Existing unequal bytes are forbidden."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);content=canonical(value)+b'\n'
    if path.exists():
        if path.read_bytes()!=content:raise ValueError('IMMUTABLE_PATH_CHANGED: '+str(path))
        return False
    fd,temp=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(content);stream.flush();os.fsync(stream.fileno())
        try:os.link(temp,path)
        except FileExistsError:
            if path.read_bytes()!=content:raise ValueError('Concurrent immutable conflict')
            return False
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return True

def derived(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.projection-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(canonical(value)+b'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

@contextmanager
def locked(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'.append.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)

class Ledger:
    def __init__(self,root):
        self.root=Path(root);self.events=[];self.ids={}
        prev=ZERO
        for i,path in enumerate(sorted((self.root/'events').glob('*.json')),1):
            e=json.loads(path.read_text());body={k:v for k,v in e.items() if k!='hash'}
            if e['sequence']!=i or e['previous_hash']!=prev or sha(body)!=e['hash']:raise ValueError('BROKEN_EVENT_CHAIN')
            if e['event_id'] in self.ids:raise ValueError('DUPLICATE_EVENT_ID')
            self.events.append(e);self.ids[e['event_id']]=e;prev=e['hash']
        self.verify_objects()
        self.verify_checkpoints()
    @property
    def head(self):return self.events[-1]['hash'] if self.events else ZERO
    def object(self,value):
        key=sha(value);write_exclusive(self.root/'objects'/(key+'.json'),value);return key
    def read_object(self,key):
        p=self.root/'objects'/(key+'.json');v=json.loads(p.read_text())
        if sha(v)!=key:raise ValueError('OBJECT_HASH_MISMATCH')
        return v
    def verify_objects(self):
        for p in (self.root/'objects').glob('*.json'):
            if sha(json.loads(p.read_text()))!=p.stem:raise ValueError('OBJECT_HASH_MISMATCH')
        for e in self.events:
            for key in e.get('object_refs',[]):self.read_object(key)
    def append(self,event_id,kind,payload,recorded_utc,object_refs=()):
        with locked(self.root):
            self.__init__(self.root)
            return self._append(event_id,kind,payload,recorded_utc,object_refs)
    def _append(self,event_id,kind,payload,recorded_utc,object_refs=()):
        if event_id in self.ids:
            old=self.ids[event_id]
            if old['kind']!=kind or old['payload']!=payload or old['object_refs']!=list(object_refs):raise ValueError('EVENT_ID_CONFLICT')
            return old
        body={'sequence':len(self.events)+1,'event_id':event_id,'kind':kind,'recorded_utc':recorded_utc,'previous_hash':self.head,'payload':payload,'object_refs':list(object_refs)}
        event={**body,'hash':sha(body)}
        write_exclusive(self.root/'events'/(f"{body['sequence']:010d}_"+sha(event_id)[:20]+'.json'),event)
        self.events.append(event);self.ids[event_id]=event;return event
    def verify_checkpoints(self):
        for path in (self.root/'checkpoints').glob('*.json'):
            cp=json.loads(path.read_text());n=cp['event_count']
            if n>len(self.events) or cp['head_hash']!=(self.events[n-1]['hash'] if n else ZERO):raise ValueError('CHECKPOINT_TRUNCATION_OR_REWRITE')
            for relative,digest in cp['durable_files'].items():
                target=self.root/relative
                if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('CHECKPOINT_FILE_CHANGED')
    def manifest(self):
        files={str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('events','objects') for p in sorted((self.root/folder).glob('*.json'))}
        return {'schema_version':1,'event_count':len(self.events),'head_hash':self.head,'durable_files':files,'manifest_hash':sha(files)}
