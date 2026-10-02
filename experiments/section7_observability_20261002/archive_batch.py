"""Archive the completed batch with per-file hashes and an exact credential scan."""
import hashlib
import json
from pathlib import Path
import tarfile
from runtime import ROOT, read, save, secret


def main():
    acceptance = read(ROOT / 'records/online-acceptance.json')
    assert acceptance['passed'] and acceptance['tasks_checked'] == 36
    roots = sorted((ROOT / '.runtime/runs').glob('section7-v1-*'))
    assert len(roots) == 6
    files = sorted(path for run in roots for path in run.rglob('*') if path.is_file())
    files.append(ROOT / 'records/online-source-snapshot-v1.json')
    api_key = secret().encode()
    broker_token = read(ROOT / '.runtime/sandbox-broker.json')['token'].encode()
    entries = []
    for path in files:
        raw = path.read_bytes()
        if api_key in raw or broker_token in raw:
            raise RuntimeError('Credential found in archive member: ' + str(path.relative_to(ROOT)))
        entries.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': len(raw),
                        'sha256': hashlib.sha256(raw).hexdigest()})
    destination = ROOT / 'artifacts/first-three-raw-runs.tar.gz'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        with tarfile.open(destination, 'r:gz') as archive:
            observed = {member.name: hashlib.sha256(archive.extractfile(member).read()).hexdigest() for member in archive.getmembers() if member.isfile()}
        assert observed == {entry['path']: entry['sha256'] for entry in entries}, 'Existing archive differs; preserve and investigate'
    else:
        temporary = destination.with_suffix(destination.suffix + '.tmp')
        with tarfile.open(temporary, 'w:gz') as archive:
            for path in files:
                archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
        temporary.replace(destination)
    with tarfile.open(destination, 'r:gz') as archive:
        members = archive.getmembers()
        assert len(members) == len(entries) and all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
        expected = {entry['path']: entry['sha256'] for entry in entries}
        for member in members:
            assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == expected[member.name]
    report = {'path': destination.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'bytes': destination.stat().st_size, 'files': len(entries), 'members_verified': True,
              'exact_current_api_and_broker_credential_scan_passed': True, 'tasks': 36, 'model_calls': 206,
              'model_calls_during_archive': 0, 'files_index': entries,
              'scope': 'Six simple-method canary runs and their frozen source snapshot; excludes credentials, broker config, live private inputs, sandbox host assets and model runtimes'}
    save(ROOT / 'records/raw-archive.json', report)
    print(json.dumps({key: value for key, value in report.items() if key != 'files_index'}))


if __name__ == '__main__':
    main()
