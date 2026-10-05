"""Export the authorized 320 Database memory snapshots without model calls.

Read only selected source records. Native payloads retain their original bytes;
Notepad strings are decoded from their state JSON and encoded as UTF-8 text.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile


ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'database-memory-snapshots'
METHODS = {
    'pi_notepad': 'notepad',
    'codex_memory_ready': 'codex',
    'claude_memory_ready': 'claude_code',
    'hermes_memory_ready': 'hermes',
}
EXPECTED_BYTES = {
    'notepad': {'before': 15220, 'after': 15690},
    'codex': {'before': 5870004, 'after': 6216687},
    'claude_code': {'before': 692991, 'after': 731522},
    'hermes': {'before': 1052559, 'after': 1114947},
}
PATTERNS = {
    'credential_pattern': r'\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'authorization_header': r'(?i)authorization\s*[:=]\s*["\x27]?(?:bearer|basic)\s+[^\s"\x27]{12,}',
}


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')


def safe_target(base, relative):
    name = PurePosixPath(relative)
    assert not name.is_absolute() and '..' not in name.parts
    assert '\\' not in relative and ':' not in relative
    target = base.joinpath(*name.parts).resolve()
    assert target.is_relative_to(base.resolve())
    return target


def inspect_credentials(payload, location, known=()):
    content = payload.decode('utf8')
    matches = [name for name, pattern in PATTERNS.items() if re.search(pattern, content)]
    if any(secret in content for secret in known):
        matches.append('known_local_credential')
    if matches:
        # Do not expose matching credential values in diagnostics.
        raise ValueError(f'Credential review required: {location}: {matches}')


def is_bookkeeping(name):
    return ('/.locks/' in name or name.endswith('.lock') or '/.git/' in name
            or name.endswith(('.usage.json', '.curator_ledger.jsonl')))


def write_exact(path, payload):
    if path.exists():
        assert path.read_bytes() == payload, f'Refuse to replace different export: {path}'
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def verify():
    """Verify a repository checkout without access to private source files."""
    manifest = read(DEST / 'manifest.json')
    assert len(manifest['snapshots']) == 320
    expected_paths = {DEST / 'manifest.json', DEST / 'README.md', DEST / '.gitattributes'}
    groups = Counter()
    byte_groups = Counter()
    identities = set()
    payload_files = payload_bytes = bookkeeping_bytes = empty_snapshots = 0
    for entry in manifest['snapshots']:
        meta_path = safe_target(DEST, entry['metadata_path'])
        assert meta_path not in expected_paths
        expected_paths.add(meta_path)
        assert file_digest(meta_path) == entry['metadata_sha256']
        snap = read(meta_path)
        method, phase, index = snap['method'], snap['phase'], snap['index']
        identity = (method, phase, index)
        assert identity not in identities and method in METHODS.values()
        assert phase in {'before', 'after'} and 0 <= index < 40
        assert meta_path.relative_to(DEST).as_posix() == f'{method}/task-{index:03d}/{phase}/.snapshot.json'
        identities.add(identity)
        groups[method, phase] += 1
        size = 0
        for item in snap['files']:
            target = safe_target(meta_path.parent, item['path'])
            assert target not in expected_paths
            expected_paths.add(target)
            data = target.read_bytes()
            assert len(data) == item['bytes'] and digest(data) == item['sha256']
            inspect_credentials(data, target.relative_to(DEST))
            size += len(data)
            payload_files += 1
            bookkeeping_bytes += len(data) if is_bookkeeping(item['path']) else 0
        assert size == snap['payload_bytes'] == entry['payload_bytes']
        assert len(snap['files']) == snap['payload_files']
        empty_snapshots += not snap['files']
        byte_groups[method, phase] += size
        payload_bytes += size
    assert groups == Counter({(m, p): 40 for m in METHODS.values() for p in ('before', 'after')})
    assert byte_groups == Counter({(m, p): n for m, phases in EXPECTED_BYTES.items() for p, n in phases.items()})
    assert payload_bytes == manifest['payload_bytes'] == 15709620
    assert payload_files == manifest['payload_files'] == 2905
    assert bookkeeping_bytes == manifest['bookkeeping_bytes'] == 1092275
    assert payload_bytes - bookkeeping_bytes == manifest['content_bytes_excluding_bookkeeping'] == 14617345
    assert empty_snapshots == manifest['empty_snapshots'] == 6
    actual = {path for path in DEST.rglob('*') if path.is_file()}
    assert actual == expected_paths, 'Unexpected or missing exported files'
    return {'status': 'passed', 'snapshots': len(identities), 'payload_files': payload_files,
            'payload_bytes': payload_bytes, 'sha256_verified': payload_files,
            'empty_snapshots_preserved': empty_snapshots, 'model_calls': 0}


def export():
    rows = [r for r in read(ROOT / 'records/corrected-task-index.json')
            if r['environment'] == 'database_exploration' and r['method'] in METHODS]
    assert len(rows) == 160
    assert len({(r['method'], r['index']) for r in rows}) == 160
    metrics = {r['unit_id']: r for r in read(ROOT / 'records/full-mechanical-task-metrics.json')}
    known = set()
    for row in rows:
        config = read(ROOT / 'private-runs' / row['source_run_id'] / f"task-{row['index']:03d}" / 'input.json')
        known.update(value for key, value in config.items() if isinstance(value, str) and len(value) > 12
                     and any(word in key.lower() for word in ('token', 'api_key', 'secret', 'password')))
    prepared = []
    source_records = {}
    for method, label in METHODS.items():
        previous = {}
        selected = sorted((r for r in rows if r['method'] == method), key=lambda r: r['index'])
        assert [r['index'] for r in selected] == list(range(40))
        for row in selected:
            index = row['index']
            out = ROOT / 'private-runs' / row['source_run_id'] / f'task-{index:03d}'
            states = {phase: read(out / f'memory-{phase}.json') for phase in ('before', 'after')}
            for phase in states:
                path = out / f'memory-{phase}.json'
                source_records[path.relative_to(ROOT).as_posix()] = file_digest(path)
            if method == 'pi_notepad':
                versions = {}
                for phase, state in states.items():
                    text = state.get('notepad', '')
                    versions[phase] = {'notepad.txt': (text.encode('utf8'), {
                        'kind': 'json_string_utf8', 'source_path': (out / f'memory-{phase}.json').relative_to(ROOT).as_posix(),
                        'json_field': 'notepad',
                    })} if text else {}
            else:
                archive = out / ('recovered-native-state.tar.gz'
                                 if row.get('recovered_maintenance') or row.get('recovered_solver') else 'native-state.tar.gz')
                source_path = archive.relative_to(ROOT).as_posix()
                source_records[source_path] = file_digest(archive)
                after = {}
                with tarfile.open(archive, 'r|gz') as tar:
                    for member in tar:
                        name = member.name.removeprefix('./')
                        if member.isfile() and name in states['after']:
                            assert name not in after, 'Ambiguous duplicate tar member'
                            payload = tar.extractfile(member).read()
                            assert digest(payload) == states['after'][name]
                            after[name] = (payload, {'kind': 'tar_member', 'source_path': source_path, 'member': member.name})
                assert set(after) == set(states['after'])
                before = {}
                for name, expected in states['before'].items():
                    candidate = previous.get(name)
                    if candidate is None or digest(candidate[0]) != expected:
                        candidate = after.get(name)
                    assert candidate is not None and digest(candidate[0]) == expected, 'Pre-task snapshot cannot be reconstructed'
                    before[name] = candidate
                versions = {'before': before, 'after': after}
                previous = after
            for phase, files in versions.items():
                directory = f'{label}/task-{index:03d}/{phase}'
                entries = []
                for name, (payload, source) in sorted(files.items()):
                    target = safe_target(DEST / directory, name)
                    inspect_credentials(payload, target.relative_to(DEST), known)
                    entry = {'path': name, 'bytes': len(payload), 'sha256': digest(payload), 'source': source}
                    entries.append(entry)
                    prepared.append((target, payload))
                size = sum(e['bytes'] for e in entries)
                assert size == metrics[f"{row['run_id']}-{index:03d}"][phase]['physical_bytes']
                meta = {
                    'schema_version': 1, 'method': label, 'source_method': method,
                    'environment': 'database_exploration', 'run_id': row['run_id'], 'source_run_id': row['source_run_id'],
                    'index': index, 'task_position': index + 1, 'phase': phase,
                    'source_state_index': (out / f'memory-{phase}.json').relative_to(ROOT).as_posix(),
                    'payload_files': len(entries), 'payload_bytes': size, 'files': entries,
                }
                prepared.append((DEST / directory / '.snapshot.json', json_bytes(meta)))
    # Finish all source/content checks before writing any export payload.
    for path, payload in prepared:
        if path.exists():
            assert path.read_bytes() == payload, f'Different existing export: {path}'
    snapshots = []
    payload_bytes = payload_files = bookkeeping_bytes = empty_snapshots = 0
    for path, payload in prepared:
        write_exact(path, payload)
        if path.name == '.snapshot.json':
            meta = json.loads(payload)
            snapshots.append({'metadata_path': path.relative_to(DEST).as_posix(), 'metadata_sha256': digest(payload),
                              'payload_bytes': meta['payload_bytes']})
            payload_bytes += meta['payload_bytes']
            payload_files += meta['payload_files']
            empty_snapshots += not meta['files']
            bookkeeping_bytes += sum(e['bytes'] for e in meta['files'] if is_bookkeeping(e['path']))
    manifest = {
        'schema_version': 1, 'exported_at': datetime.now(timezone.utc).isoformat(),
        'authorization': 'User explicitly requested uploading all 320 before/after Database memory snapshots totaling 15,709,620 payload bytes.',
        'scope': '40 Database tasks each for Notepad, Codex, Claude Code and Hermes; both before and after; bookkeeping included.',
        'snapshot_count': len(snapshots), 'payload_files': payload_files, 'payload_bytes': payload_bytes,
        'bookkeeping_bytes': bookkeeping_bytes, 'content_bytes_excluding_bookkeeping': payload_bytes - bookkeeping_bytes,
        'empty_snapshots': empty_snapshots, 'deduplicated': False, 'compressed': False,
        'native_payloads_byte_identical': True, 'notepad_encoding': 'UTF-8 value of the source notepad JSON string',
        'original_sources_modified': False, 'model_calls': 0,
        'credential_scan': {'common_patterns_and_all_selected_task_config_credentials': 'no_matches',
                            'limitation': 'Targeted scanning does not guarantee detection of every possible sensitive value.'},
        'excluded': ['Codebase snapshots', 'other methods', 'canaries and intermediate recovery checkpoints',
                     'session and provider request logs', 'native databases', 'Git internals', 'hidden evaluator records'],
        'groups': [{'method': label, 'snapshots': 80, 'before_bytes': counts['before'], 'after_bytes': counts['after'],
                    'payload_bytes': sum(counts.values())} for label, counts in EXPECTED_BYTES.items()],
        'source_sha256': source_records, 'snapshots': snapshots,
    }
    manifest_path = DEST / 'manifest.json'
    if manifest_path.exists():
        existing = read(manifest_path)
        manifest['exported_at'] = existing['exported_at']
    write_exact(manifest_path, json_bytes(manifest))
    return verify()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Check the export without private sources or model calls')
    args = parser.parse_args()
    print(json.dumps(verify() if args.verify else export(), ensure_ascii=False))
