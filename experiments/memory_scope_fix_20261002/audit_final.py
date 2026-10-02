"""Independent artifact/transport/snapshot audit; does not make model calls."""
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'memory_direction_20261002'
sys.path.insert(0, str(OLD))
from lab_common import get_secret
from environment import Environment


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def body(path):
    return gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()


def main():
    errors, runs, requests, models = [], 0, 0, Counter()
    truncations, agent_failures = [], []
    response_models = set()
    native_reasoning_history_requests = 0
    snapshots = []
    for directory in sorted((ROOT / 'results/runs').iterdir()):
        if not (directory / 'summary.json').exists():
            errors.append({'run': directory.name, 'error': 'missing terminal summary'})
            continue
        runs += 1
        config = load(directory / 'input.json')
        s = load(directory / 'summary.json')
        agent_result = load(directory / 'agent-result.json')
        if s.get('error') or agent_result.get('failed') or agent_result.get('partial') or agent_result.get('interrupted'):
            agent_failures.append(directory.name)
        if load(directory / 'process.json')['status'] != 'finished':
            errors.append({'run': directory.name, 'error': 'nonterminal process state'})
        before = load(directory / 'memory_before/entries.json')
        source = config.get('repair_from') or config.get('writer_from') or config.get('memory_from')
        if source:
            if before != load(ROOT / 'results/runs' / source / 'memory_after/entries.json'):
                errors.append({'run': directory.name, 'error': 'seed differs from immutable source'})
        if config.get('writer_from'):
            if load(ROOT / 'results/runs' / source / 'input.json')['stage'] != 'a':
                errors.append({'run': directory.name, 'error': 'writer exposed to non-a source'})
        after = load(directory / 'memory_after/entries.json')
        index = load(directory / 'memory_after/index.json')
        if {k: v['version'] for k, v in after.items()} != {k: v['version'] for k, v in index.items()}:
            errors.append({'run': directory.name, 'error': 'index version mismatch'})
        snapshots.append({'run': directory.name, 'before_sha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(), 'after_sha256': hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest()})
        for request in sorted((directory / 'http').glob('*-request.json*')):
            payload = json.loads(body(request))['effective_payload']
            if request.name.endswith('.json') and request.with_suffix('.json.gz').exists():
                errors.append({'run': directory.name, 'error': 'duplicate HTTP source and archive'})
            requests += 1
            models[payload['model']] += 1
            if config.get('transport') == 'native' and any(m.get('reasoning_content') for m in payload['messages']):
                native_reasoning_history_requests += 1
            effort_ok = payload.get('reasoning_effort') == 'high' if config.get('transport') == 'native' else payload.get('output_config', {}).get('effort') == 'high'
            if payload['thinking'].get('type') != 'enabled' or not effort_ok or payload['max_tokens'] != 32768:
                errors.append({'run': directory.name, 'error': 'unexpected effective model parameters', 'file': request.name})
            if config['agent'] == 'hermes' and directory.name != 'cal-hermes-01-b-none':
                expected = {t['name'] for t in load(directory / 'exposed-tools.json')}
                actual = {t['name'] for t in payload['tools']}
                if actual != expected:
                    errors.append({'run': directory.name, 'error': 'Hermes HTTP tool surface mismatch'})
                sys_text = payload['system'] if isinstance(payload['system'], str) else '\n'.join(x.get('text', '') for x in payload['system'])
                if sys_text != config['system']:
                    errors.append({'run': directory.name, 'error': 'Hermes HTTP system differs from controlled prompt'})
        for response in sorted((directory / 'http').glob('*-response.txt*')):
            for line in body(response).decode('utf-8').splitlines():
                if not line.startswith('data: '):
                    continue
                try:
                    event = json.loads(line[6:])
                except ValueError:
                    continue
                stop = event.get('delta', {}).get('stop_reason') or event.get('message', {}).get('stop_reason')
                response_model = event.get('model') or event.get('message', {}).get('model')
                if response_model:
                    response_models.add(response_model)
                if stop == 'max_tokens' or any(c.get('finish_reason') == 'length' for c in event.get('choices', [])):
                    truncations.append({'run': directory.name, 'response': response.name})
    archived = 0
    manifest_file = ROOT / 'results/http-archive-manifest.json'
    for name, expected in load(manifest_file).items() if manifest_file.exists() else []:
        data = body(ROOT / name)
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            errors.append({'file': name, 'error': 'archive byte/hash mismatch'})
        archived += 1
    reproducibility_path = ROOT / 'results/reproducibility-hashes.json'
    reproducibility_entries = load(reproducibility_path) if reproducibility_path.exists() else {}
    for name, expected in reproducibility_entries.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            errors.append({'file': name, 'error': 'code/config/data reproducibility hash mismatch'})
    secrets = [get_secret(p).encode() for p in ('deepseek', 'glm')]
    scanned = 0
    for file in ROOT.rglob('*'):
        if not file.is_file() or any(p in {'.runtime', '.cache', '.private', '__pycache__', 'workspaces'} for p in file.relative_to(ROOT).parts):
            continue
        data = body(file)
        if any(key in data for key in secrets):
            errors.append({'file': str(file.relative_to(ROOT)), 'error': 'secret detected; value withheld'})
        scanned += 1
    output = {'complete_run_directories': runs, 'effective_requests_checked': requests, 'models': dict(models),
              'verified_archived_http_bodies': archived, 'files_scanned_for_actual_credentials': scanned,
              'verified_code_config_data_hashes': len(reproducibility_entries),
              'truncated_responses': truncations, 'failed_or_partial_agents': agent_failures,
              'response_model_names': sorted(response_models), 'native_requests_preserving_reasoning_content': native_reasoning_history_requests,
              'errors': errors, 'snapshots': snapshots,
              'limitations': 'Automated integrity and protocol checks do not establish semantic scope correctness or causal memory dependence.'}
    (ROOT / 'results/final-audit.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in output.items() if k != 'snapshots'}))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
