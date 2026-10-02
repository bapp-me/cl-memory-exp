"""Fail closed if any frozen experimental component changes between stages."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    freeze=json.loads((ROOT/'records/pilot-freeze.json').read_text(encoding='utf-8'))
    changed=[name for name,expected in freeze['hashes'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected]
    print(json.dumps({'frozen_components':len(freeze['hashes']),'changed':changed}))
    raise SystemExit(1 if changed else 0)
