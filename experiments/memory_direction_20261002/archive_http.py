"""Losslessly compress completed HTTP traces while keeping a content manifest."""
import gzip
import hashlib
import json
from lab_common import ROOT, save_json


def main():
    root=(ROOT/'results/runs').resolve()
    rows=[]
    for run in sorted(root.iterdir()):
        if not (run/'summary.json').exists():continue
        for p in sorted((run/'http').glob('*')):
            if not p.name.endswith(('-request.json','-response.txt')):continue
            assert root in p.resolve().parents
            raw=p.read_bytes();target=p.with_name(p.name+'.gz')
            compressed=gzip.compress(raw,mtime=0)
            target.write_bytes(compressed)
            assert gzip.decompress(target.read_bytes())==raw
            rows.append({'path':str(target.relative_to(ROOT)), 'uncompressed_bytes':len(raw),
                         'sha256_uncompressed':hashlib.sha256(raw).hexdigest(),'bytes':len(compressed)})
            p.unlink()
    path=ROOT/'results/http-archive-manifest.json'
    old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    save_json(path,old+rows)
    print(json.dumps({'newly_compressed':len(rows),'raw_bytes':sum(x['uncompressed_bytes'] for x in rows),
                      'compressed_bytes':sum(x['bytes'] for x in rows)}))


if __name__=='__main__':main()
