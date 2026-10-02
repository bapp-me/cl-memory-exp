"""Package completed raw evidence; refuse unfinished confirmation streams."""
import hashlib
import json
import tarfile
from pathlib import Path
from core import ROOT,get_secret,save

if __name__=='__main__':
    decision=json.loads((ROOT/'records/benchmark-decision.json').read_text(encoding='utf-8'))
    method=decision['confirmation_memory_method']
    required=[(f'full-codeeval-glm-{m}',96) for m in ['no_memory',method]]+[(f'noncode-babyai-glm-{m}',8) for m in ['no_memory',method]]+[(f'readonly12-codeeval-glm-{method}',12)]
    for name,total in required:
        path=ROOT/'runs'/name/'summary.json'
        if not path.exists() or len(json.loads(path.read_text(encoding='utf-8')))!=total:raise RuntimeError('Incomplete '+name)
    keys=[get_secret(p).encode() for p in ['deepseek','glm']]
    files=sorted(p for p in (ROOT/'runs').rglob('*') if p.is_file())
    for path in files:
        data=path.read_bytes()
        if any(k in data for k in keys):raise RuntimeError('Credential detected in '+str(path.relative_to(ROOT)))
    target=ROOT/'artifacts/00-06-raw-runs.tar.gz';target.parent.mkdir(exist_ok=True)
    with tarfile.open(target.with_suffix('.part'),'w:gz',compresslevel=9) as archive:
        for path in files:archive.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
    target.with_suffix('.part').replace(target)
    with target.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    record={'path':str(target.relative_to(ROOT)),'files':len(files),'bytes':target.stat().st_size,'sha256':digest,
            'credential_scan_passed':True,'confirmation_scope':'User-revised: 192 first-pass code tasks, 16 noncode tasks, 12 memory-only readonly probes; no no-memory second pass',
            'scope':'raw model/tool trajectories, snapshots, evaluator logs, source snapshots and execution summaries; excludes credentials, task sandboxes, downloaded hidden source assets and dependency runtimes'}
    save(ROOT/'records/raw-archive.json',record)
    print(json.dumps(record))
