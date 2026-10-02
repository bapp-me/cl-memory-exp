"""Verify byte-exact imported evidence without loading credentials or models."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'docs/export-manifest.json').read_text(encoding='utf-8'))
errors = []
for item in manifest['files']:
    path = (ROOT / item['path']).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        errors.append(item['path'])
        continue
    if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
        errors.append(item['path'])
print(json.dumps({'files': len(manifest['files']), 'passed': not errors, 'errors': errors}, ensure_ascii=True))
if errors:
    raise SystemExit(1)
