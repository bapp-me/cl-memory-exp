"""Download pinned SQLite assets and archive native question metadata privately."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

def main():
    repo = 'continual-learning-bench/database-exploration'
    meta = json.load(urlopen(f'https://huggingface.co/api/datasets/{repo}', timeout=45))
    revision = meta['sha']
    tree = json.load(urlopen(f'https://huggingface.co/api/datasets/{repo}/tree/{revision}', timeout=45))
    root = ROOT / '.cache/clbench'
    records = []
    for name in ['products.db', 'products_drifted.db']:
        item = next(x for x in tree if x['path'] == name)
        path = root / name
        prior = ROOT.parent / 'memory_direction_20261002/.cache/clbench' / name
        if not path.exists() and prior.exists():
            shutil.copyfile(prior, path)
        if path.exists() and path.stat().st_size != item['size']:
            path.replace(path.with_suffix('.part'))
        if not path.exists():
            part=path.with_suffix('.part')
            for attempt in range(3):
                offset=part.stat().st_size if part.exists() else 0
                req=Request(f'https://huggingface.co/datasets/{repo}/resolve/{revision}/{name}',headers={'Range':f'bytes={offset}-'} if offset else {})
                with urlopen(req, timeout=120) as response:
                    mode='ab' if offset and response.status==206 else 'wb'
                    with part.open(mode) as out:shutil.copyfileobj(response,out,length=4*1024*1024)
                print(json.dumps({'file':name,'bytes':part.stat().st_size,'expected':item['size'],'attempt':attempt+1}),flush=True)
                if part.stat().st_size==item['size']:break
            if part.stat().st_size!=item['size']:raise RuntimeError(f'Incomplete asset {name}')
            part.replace(path)
        with path.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if digest != item['lfs']['oid']:
            raise RuntimeError(f'Hash mismatch for {name}')
        records.append({'file': name, 'sha256': digest, 'bytes': path.stat().st_size})
        print(json.dumps(records[-1]), flush=True)
    report = {'revision': revision, 'repo': repo, 'files': records, 'checked_at': datetime.now(timezone.utc).isoformat()}
    (ROOT / 'records/database-assets.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

if __name__ == '__main__':
    main()
