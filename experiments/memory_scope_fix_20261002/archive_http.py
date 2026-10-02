"""Losslessly gzip only completed-run HTTP bodies, with byte/hash verification."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
manifest_path = ROOT / 'results/http-archive-manifest.json'
records = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
for summary in sorted((ROOT / 'results/runs').glob('*/summary.json')):
    for file in sorted((summary.parent / 'http').glob('*')):
        if file.name == 'ledger.jsonl' or file.suffix not in ('.json', '.txt'):
            continue
        data = file.read_bytes()
        dest = file.with_suffix(file.suffix + '.gz')
        if dest.exists():
            if gzip.decompress(dest.read_bytes()) != data:
                raise ValueError(f'Conflicting archive {dest}')
        else:
            dest.write_bytes(gzip.compress(data, mtime=0))
        if gzip.decompress(dest.read_bytes()) != data:
            raise ValueError('Archive verification failed')
        records[str(dest.relative_to(ROOT)).replace('\\', '/')] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'gzip_sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}
        # Single owned file only, after verified byte-for-byte lossless preservation.
        file.unlink()
manifest_path.write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
print(f'{len(records)} HTTP bodies archived with verified exact bytes.')
