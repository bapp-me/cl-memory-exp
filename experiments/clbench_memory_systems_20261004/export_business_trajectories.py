"""Export only the user-authorized task trajectories; no model calls.

Source records stay private and unchanged. Exported JSON bytes are copied
exactly, including the explicitly partial, unscored interruption record.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from prepare import ROOT, read, save, sha

DEST = ROOT / 'trajectories'
METHODS = {
    'pi_none': 'no_memory', 'pi_notepad': 'notepad', 'pi_jaccard': 'jaccard',
    'claude_memory_ready': 'claude_code', 'codex_memory_ready': 'codex',
    'hermes_memory_ready': 'hermes',
}
ENVIRONMENTS = {'database_exploration': 'database', 'codebase_adaptation': 'codebase'}
PATTERNS = {
    'credential_pattern': r'\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'authorization_header': r'(?i)authorization\s*[:=]\s*["\x27]?(?:bearer|basic)\s+[^\s"\x27]{12,}',
}


def inspect_credentials(source):
    text = source.read_text(encoding='utf8')
    matches = [name for name, pattern in PATTERNS.items() if re.search(pattern, text)]
    config = read(source.parent / 'input.json')
    known = [v for k, v in config.items() if isinstance(v, str) and len(v) > 12
             and any(key in k.lower() for key in ['gateway_token', 'tool_token', 'api_key'])]
    if any(value in text for value in known):
        matches.append('known_local_credential')
    if matches:
        # Report locations/pattern names only; never print a matching secret.
        raise ValueError(f'Credential review required: {source.relative_to(ROOT)}: {matches}')


def verify():
    manifest = read(DEST / 'manifest.json')
    entries = manifest['files']
    assert len(entries) == 354
    assert Counter(e['record_type'] for e in entries) == {'business_episode': 353, 'interrupted_actions': 1}
    paths = set()
    for entry in entries:
        target = (DEST / entry['path']).resolve()
        assert target.is_relative_to(DEST.resolve()) and target not in paths
        paths.add(target)
        assert target.stat().st_size == entry['bytes'] and sha(target) == entry['sha256']
        data = read(target)
        if entry['record_type'] == 'business_episode':
            assert set(data) == {'namespace', 'index', 'instance_id', 'prompt', 'assistant_text', 'tools', 'feedback'}
            assert data['index'] == entry['index']
        else:
            assert isinstance(data, list) and len(data) == 14
            assert entry['correct'] is None and entry['index'] == 15
    assert sum(e['bytes'] for e in entries) == manifest['trajectory_bytes'] == 7864387
    actual = {p.resolve() for p in DEST.rglob('*.json') if p.name != 'manifest.json'}
    assert actual == paths, 'Unexpected or missing trajectory files'
    assert sum(e['authorized_rerun_selected'] for e in entries) == 3
    return {'status': 'passed', 'trajectory_files': len(entries), 'trajectory_bytes': manifest['trajectory_bytes'],
            'sha256_verified': len(entries), 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true', help='Validate the exported files without private sources')
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify(), ensure_ascii=False))
        return
    rows = read(ROOT / 'records/corrected-task-index.json')
    assert len(rows) == 353
    rows.append({'run_id': 'candidate-code-hermes-64k-v2', 'source_run_id': 'candidate-code-hermes-64k-v2',
                 'method': 'hermes_memory_ready', 'environment': 'codebase_adaptation', 'index': 15,
                 'correct': None, 'user_interrupted': True})
    assert len({(r['run_id'], r['index']) for r in rows}) == 354
    prepared = []
    for row in sorted(rows, key=lambda r: (r['method'], r['environment'], r['index'])):
        interrupted = row.get('user_interrupted', False)
        source = ROOT / 'private-runs' / row['source_run_id'] / f"task-{row['index']:03d}" / (
            'business-actions.json' if interrupted else 'legal-episode.json')
        inspect_credentials(source)
        filename = f"task-{row['index']:03d}" + ('.interrupted-actions.json' if interrupted else '.json')
        relative = Path(METHODS[row['method']]) / ENVIRONMENTS[row['environment']] / filename
        entry = {'path': relative.as_posix(), 'method': row['method'], 'environment': row['environment'],
                 'run_id': row['run_id'], 'source_run_id': row['source_run_id'], 'index': row['index'],
                 'task_position': row['index'] + 1, 'correct': row['correct'],
                 'record_type': 'interrupted_actions' if interrupted else 'business_episode',
                 'authorized_rerun_selected': row['source_run_id'] != row['run_id'],
                 'source_path': source.relative_to(ROOT).as_posix(), 'bytes': source.stat().st_size,
                 'sha256': sha(source)}
        target = DEST / relative
        assert target.resolve().is_relative_to(DEST.resolve())
        if target.exists():
            assert sha(target) == entry['sha256'], 'Do not overwrite a different existing export'
        prepared.append((source, target, entry))
    assert sum(e['bytes'] for _, _, e in prepared) == 7864387
    for source, target, entry in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(source, target)
        assert sha(target) == sha(source) == entry['sha256']
    entries = [entry for _, _, entry in prepared]
    groups = []
    for method in METHODS:
        selected = [e for e in entries if e['method'] == method]
        groups.append({'method': method, 'files': len(selected), 'bytes': sum(e['bytes'] for e in selected),
                       'scored_episodes': sum(e['record_type'] == 'business_episode' for e in selected)})
    save(DEST / 'manifest.json', {
        'schema_version': 1, 'exported_at': datetime.now(timezone.utc).isoformat(),
        'authorization': 'User explicitly requested pushing the previously measured pure task trajectories to this repository.',
        'scope': '353 selected business episodes plus the interrupted Hermes Codebase task 16 action trace; both environments and all six methods.',
        'trajectory_files': 354, 'trajectory_bytes': 7864387, 'scored_episodes': 353, 'interrupted_action_traces': 1,
        'byte_identical_to_private_sources': True, 'original_sources_modified': False,
        'credential_scan': {'known_config_credentials_and_common_patterns': 'no_matches',
                            'limitation': 'A targeted scan is not a universal guarantee about all possible sensitive content.'},
        'excluded': ['provider request/response copies', 'native internal and memory-maintenance conversations',
                     'memory/state snapshots', 'database copies', 'hidden evaluator data', 'judge outputs',
                     'canaries/debug runs', 'superseded original versions of the three authorized reruns'],
        'groups': groups, 'files': entries,
    })
    print(json.dumps(verify(), ensure_ascii=False))


if __name__ == '__main__':
    main()
