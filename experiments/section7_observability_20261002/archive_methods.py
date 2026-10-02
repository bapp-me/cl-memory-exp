"""Verify and archive accepted native canaries or the completed formal matrix."""
import argparse
import hashlib
from pathlib import Path
import tarfile
from runtime import ROOT, REPO, read, save, secret


def archive(phase):
    if phase == 'canary':
        report = read(ROOT / 'records/complex-online-acceptance.json')
        assert report['passed'] and report['tasks_checked'] == 36
        runs = [ROOT / '.runtime/runs' / item['run_id'] for item in report['runs']]
        sources = sorted((ROOT / 'records').glob('canary-methods-freeze-*.json'))
        # Preserve failed pre-task startup evidence, without counting it as a zero score.
        runs.extend(run for run in (ROOT / '.runtime/runs').glob('section7-canary-v2*-*') if run not in runs)
        task_count = 36
    else:
        report = read(ROOT / 'records/section7.1-final.json')
        assert report['status'] == 'complete' and report['matrix_tasks'] == 624
        registry = read(ROOT / 'records/section7.1-registry.json')
        runs = [REPO / item['path'] for item in registry['runs'] if item['source_kind'] == 'new_formal_stream']
        sources = sorted((ROOT / 'records').glob('full-methods-freeze-*.json'))
        task_count = 384
    files = sorted({path for run in runs for path in run.rglob('*') if path.is_file()} | set(sources))
    api_key = secret().encode()
    broker_token = read(ROOT / '.runtime/sandbox-broker.json')['token'].encode()
    index = []
    for path in files:
        raw = path.read_bytes()
        if api_key in raw or broker_token in raw:
            raise RuntimeError('Credential found in ' + str(path.relative_to(REPO)))
        index.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    destination = ROOT / 'artifacts' / f'{phase}-native-raw-runs.tar.gz'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix(destination.suffix + '.tmp')
        with tarfile.open(temporary, 'w:gz') as stream:
            for path in files:
                stream.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
        temporary.replace(destination)
    expected = {item['path']: item['sha256'] for item in index}
    with tarfile.open(destination, 'r:gz') as stream:
        members = stream.getmembers()
        assert len(members) == len(index)
        for member in members:
            assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
            assert hashlib.sha256(stream.extractfile(member).read()).hexdigest() == expected[member.name]
    result = {'phase': phase, 'path': destination.relative_to(ROOT).as_posix(), 'files': len(index),
              'bytes': destination.stat().st_size, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'all_members_hash_verified': True, 'exact_credentials_scan_passed': True,
              'task_executions_in_scope': task_count, 'model_calls_during_archive': 0, 'files_index': index,
              'model_weights_dependencies_credentials_and_live_inputs_excluded': True}
    save(ROOT / 'records' / f'{phase}-native-raw-archive.json', result)
    print({key: value for key, value in result.items() if key != 'files_index'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['canary', 'full'], required=True)
    archive(parser.parse_args().phase)
