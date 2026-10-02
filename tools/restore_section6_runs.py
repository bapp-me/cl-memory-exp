"""Verify and restore archive members without overwriting differing evidence."""
from pathlib import Path
import hashlib
import json
import tarfile

ROOT = Path(__file__).resolve().parents[1] / 'experiments/agent_memory_plan_20261002'
record = json.loads((ROOT / 'records/raw-archive.json').read_text(encoding='utf-8'))
archive_path = ROOT / record['path'].replace('\\', '/')
with archive_path.open('rb') as stream:
    if hashlib.file_digest(stream, 'sha256').hexdigest() != record['sha256']:
        raise SystemExit('Archive hash mismatch')
count = 0
with tarfile.open(archive_path, 'r:gz') as archive:
    # Preflight all destinations before writing any member.
    members = archive.getmembers()
    for member in members:
        target = (ROOT / member.name).resolve()
        if not member.isfile() or not target.is_relative_to(ROOT / 'runs'):
            raise SystemExit('Unsafe archive member')
        if target.exists():
            with archive.extractfile(member) as stream:
                incoming = hashlib.file_digest(stream, 'sha256').hexdigest()
            if hashlib.sha256(target.read_bytes()).hexdigest() != incoming:
                raise SystemExit('Existing evidence differs: ' + member.name)
    for member in members:
        target = (ROOT / member.name).resolve()
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as stream:
                target.write_bytes(stream.read())
        count += 1
print(json.dumps({'verified_members': count, 'restored': True}))
