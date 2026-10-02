"""Audit native streams, including every auxiliary role and persisted mutation."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
from engine import ROOT, read, save, digest, normalized_usage, USAGE_FIELDS


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def audit(phase, prefixes, benchmarks=None, partial=False):
    benchmarks = benchmarks or ['codeeval', 'babyai']
    methods = ['mem0', 'awm', 'ace'] if phase == 'canary' else ['bounded_icl', 'mem0', 'awm', 'ace']
    errors, tasks, all_intervals = [], [], []
    by_role = defaultdict(lambda: {'generation_attempts': 0, 'http_attempts': 0, 'unknown_usage_attempts': 0, 'known_usage': {key: 0 for key in USAGE_FIELDS}})
    selected_runs = []
    call_ids = set()
    source_freezes = {}
    for prefix in prefixes:
        version = prefix.removeprefix('section7-' + phase + '-')
        path = ROOT / 'records' / f'{phase}-methods-freeze-{version}.json'
        if path.exists():
            freeze = read(path)
            for name, entry in freeze['sources'].items():
                if hashlib.sha256(entry['text'].encode()).hexdigest() != entry['sha256']:
                    errors.append({'freeze': str(path), 'file': name, 'error': 'Frozen source content/hash disagree'})
            source_freezes[prefix] = freeze
    for method in methods:
        for benchmark in benchmarks:
            candidates = [ROOT / '.runtime/runs' / f'{prefix}-{benchmark}-{method}' for prefix in prefixes]
            candidates = [run for run in candidates if (run / 'manifest.json').exists() and list(run.glob('*/commit.json'))]
            if not candidates:
                errors.append({'method': method, 'benchmark': benchmark, 'error': 'No committed stream'})
                continue
            run = candidates[-1]
            config = read(run / 'manifest.json')
            expected = config['stream_tasks']
            folders = sorted(run.glob('[0-9][0-9][0-9]'))
            if partial:
                folders = [folder for folder in folders if (folder / 'commit.json').exists()]
            if not partial and len(folders) != expected:
                errors.append({'run': run.name, 'expected': expected, 'directories': len(folders)})
            selected_runs.append({'run_id': run.name, 'method': method, 'benchmark': benchmark, 'tasks': expected,
                                  'config_hash': digest(config), 'source_freeze_prefix': run.name.rsplit('-' + benchmark + '-', 1)[0]})
            previous = read(run / 'initial-memory.json')
            recovery = read(run / 'timeout-recovery.json') if (run / 'timeout-recovery.json').exists() else {}
            for folder in folders:
                problems = []

                def check(name, condition):
                    if not condition:
                        problems.append(name)

                required = ['identity.json', 'legal-task.json', 'legal-episode.json', 'pi-result.json', 'execution.json',
                            'memory-before.json', 'memory-after.json', 'injected.json', 'retrieval.json', 'commit.json',
                            'submission-status.json', 'evaluator.json', 'call-ledger.json', 'controller-events.jsonl', 'requests.jsonl']
                if any(not (folder / name).exists() for name in required):
                    errors.append({'run': run.name, 'folder': folder.name, 'error': 'Required artifact missing',
                                   'missing': [name for name in required if not (folder / name).exists()]})
                    continue
                before, after, selected = [read(folder / name) for name in ['memory-before.json', 'memory-after.json', 'injected.json']]
                identity, execution, commit = [read(folder / name) for name in ['identity.json', 'execution.json', 'commit.json']]
                retrieval = read(folder / 'retrieval.json')
                check('history_chain', digest(before) == digest(previous) == commit['before_hash'] == execution['memory_hash'])
                check('committed_state_hash', digest(after) == commit['after_hash'])
                previous = after
                check('configuration_hash', commit['config_hash'] == digest(config))
                check('injection_hash', digest(selected) == retrieval['injected_hash'] == execution['injected_hash'])
                check('injection_byte_cap', len(json.dumps(selected, ensure_ascii=False).encode()) <= 48000)
                retained_timeout = False
                if phase == 'full' and commit['result']['terminal_state'] == 'memory_failure':
                    from continue_timeout_stream import review
                    try:
                        evidence = review(folder)
                        retained_timeout = evidence in recovery.get('reviewed_timeouts', [])
                    except (AssertionError, KeyError, FileNotFoundError):
                        retained_timeout = False
                check('terminal_completed_or_verified_retained_timeout',
                      commit['result']['terminal_state'] == 'completed' or retained_timeout)
                check('task_order', identity['task_id'] == config['ordered_task_ids'][int(folder.name)])
                episode = json.loads(read(folder / 'legal-episode.json')['text'])
                check('legal_episode_schema', set(episode) == {'task', 'trajectory'})
                check('hidden_reasoning_excluded', all(not (isinstance(item, dict) and item.get('type') == 'thinking') for item in episode['trajectory']))
                events = jsonl(folder / 'controller-events.jsonl')
                writes = [item for item in events if item['event'] == 'memory_event']
                if retained_timeout:
                    exceptions = [item for item in events if item['event'] == 'memory_exception']
                    check('timeout_exception_provenance_and_state', not writes and len(exceptions) == 1
                          and exceptions[0]['attempt_id'] == identity['attempt_id']
                          and exceptions[0]['before_hash'] == digest(before) == digest(after) == exceptions[0]['after_hash'])
                else:
                    check('write_provenance_and_state', len(writes) == 1 and writes[0]['source_event_ids'] == [identity['attempt_id']]
                          and writes[0]['before_hash'] == digest(before) and writes[0]['after_hash'] == digest(after))
                if method in ['mem0', 'awm', 'ace'] and not retained_timeout:
                    check('native_operation_journal', (folder / 'native-operations.json').exists())
                    journal = read(folder / 'native-operations.json')
                    check('native_operations_mapped_to_version', journal['before_hash'] == digest(before) and journal['after_hash'] == digest(after))
                    if method == 'mem0':
                        prior = {str(point['id']): point for point in before['points']}
                        changed = [point for point in after['points'] if prior.get(str(point['id'])) != point]
                        check('mem0_changed_point_sources', all(identity['attempt_id'] in after['provenance'].get(str(point['id']), []) for point in changed))
                        check('mem0_recoverable_native_history', (folder / 'native-history-after.sqlite').exists())
                        check('embedding_events_have_frozen_identity', all(item.get('dimensions') == 384 and item.get('max_seq_length') == 256
                              and item.get('billed_api_call') is False for item in events if item['event'] == 'embedding_call'))
                    elif method == 'ace':
                        check('native_no_ground_truth_reflection', read(folder / 'reflection.json')['ground_truth'] is None)
                submission = read(folder / 'submission-status.json')
                check('submission_status', submission['submitted'] == execution['submitted'])
                if benchmark == 'codeeval' and submission['submitted']:
                    check('exact_submitted_bytes', hashlib.sha256((folder / 'submission.py').read_bytes()).hexdigest() == submission['artifact_sha256'])
                ledger_paths = [folder / 'call-ledger.json', *sorted(folder.glob('auxiliary/*/call-ledger.json'))]
                reconstructed = defaultdict(lambda: {'calls': 0, 'http_attempts': 0, 'unknown_usage_attempts': 0, 'known_usage': {key: 0 for key in USAGE_FIELDS}, 'monetary_cost': None})
                for ledger_path in ledger_paths:
                    scope = ledger_path.parent
                    ledger = read(ledger_path)
                    requests = jsonl(scope / 'requests.jsonl') if (scope / 'requests.jsonl').exists() else []
                    recorded_pairs = {(item['call_id'], item['http_attempt']) for item in requests}
                    actual_pairs = {(call['call_id'], attempt['http_attempt']) for call in ledger for attempt in call['http_attempts']}
                    check('all_http_attempts_have_request', recorded_pairs == actual_pairs)
                    for request in requests:
                        payload = read(scope / request['artifact'])
                        check('actual_payload_sha256', hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() == request['actual_body_sha256'])
                        check('model_identity', payload['model'] == 'glm-5.3-flash')
                        check('injection_mapped', request['all_injected_blocks_mapped'])
                        if scope == folder:
                            check('candidate_to_injection_ids', {block['memory_id'] for block in request['blocks']} == set(retrieval['injected_ids']))
                    for call in ledger:
                        check('unique_call_id', call['call_id'] not in call_ids)
                        call_ids.add(call['call_id'])
                        check('role_and_owner', call['role'] in ['solver', 'writer', 'reflector', 'curator'] and
                              call['attempt_id'] == identity['attempt_id'] and call['run_id'] == run.name)
                        check('generation_terminal_record', call['finished_at'] is not None and call['duration_monotonic_ms'] is not None)
                        role = call['role']
                        reconstructed[role]['calls'] += 1
                        by_role[role]['generation_attempts'] += 1
                        for attempt in call['http_attempts']:
                            reconstructed[role]['http_attempts'] += 1
                            by_role[role]['http_attempts'] += 1
                            used = normalized_usage(attempt['raw_usage'])
                            if used is None:
                                reconstructed[role]['unknown_usage_attempts'] += 1
                                by_role[role]['unknown_usage_attempts'] += 1
                            else:
                                for key in USAGE_FIELDS:
                                    reconstructed[role]['known_usage'][key] += used[key]
                                    by_role[role]['known_usage'][key] += used[key]
                            check('http_terminal_record', attempt['finished_at'] is not None)
                            all_intervals.extend([(datetime.fromisoformat(attempt['started_at'].replace('Z', '+00:00')).timestamp(), 1),
                                                  (datetime.fromisoformat(attempt['finished_at'].replace('Z', '+00:00')).timestamp(), -1)])
                check('all_role_usage_matches', dict(reconstructed) == execution['role_accounting'])
                total = {key: sum(account['known_usage'][key] for account in reconstructed.values()) for key in USAGE_FIELDS}
                unknown = sum(account['unknown_usage_attempts'] for account in reconstructed.values())
                check('total_usage_including_auxiliary', total == execution['known_usage_subtotal'] and unknown == execution['unknown_usage_http_attempts'])
                check('unknown_usage_not_zero', execution['usage'] == (total if reconstructed and not unknown else None))
                if problems:
                    errors.append({'run': run.name, 'task_id': identity['task_id'], 'errors': sorted(set(problems))})
                tasks.append({'run_id': run.name, 'method': method, 'benchmark': benchmark, 'task_id': identity['task_id'],
                              'passed': not problems, 'correct': commit['result']['correct'], 'known_usage': total,
                              'terminal_state': commit['result']['terminal_state'], 'retained_timeout': retained_timeout,
                              'role_accounting': dict(reconstructed), 'unknown_usage_attempts': unknown})
    peak, active = 0, 0
    for _, delta in sorted(all_intervals, key=lambda item: (item[0], item[1])):
        active += delta
        peak = max(peak, active)
    if peak > 50:
        errors.append({'error': 'API concurrency exceeds authorized cap', 'observed': peak})
    for method in ['mem0', 'awm', 'ace']:
        rows = [row for row in tasks if row['method'] == method]
        roles = {role for row in rows for role, account in row['role_accounting'].items() if account['http_attempts']}
        required = {'writer'} if method in ['mem0', 'awm'] else {'reflector', 'curator'}
        if not required <= roles:
            errors.append({'method': method, 'error': 'No real native-role call', 'required': sorted(required), 'observed': sorted(roles)})
    expected_total = 36 if phase == 'canary' else sum(item['tasks'] for item in selected_runs)
    report = {'phase': phase, 'schema_version': 'section7-observability-v2', 'passed': not errors and (partial or len(tasks) == expected_total),
              'scope': 'committed_prefix_only' if partial else 'complete_streams', 'complete': len(tasks) == expected_total,
              'terminal_states': dict(Counter(row['terminal_state'] for row in tasks)),
              'tasks_checked': len(tasks), 'expected_tasks': expected_total, 'errors': errors, 'api_peak': peak,
              'role_accounting': dict(by_role), 'runs': selected_runs, 'tasks': tasks, 'model_calls_during_audit': 0,
              'limits': ['Method judgments of relevance/bullet use are self-assessment, not causal truth.',
                         'No price manifest; money remains unknown.', 'R=1; short code canaries do not replace formal streams.']}
    save(ROOT / 'records' / ('formal-prefix-observability.json' if partial else 'complex-online-acceptance.json' if phase == 'canary' else 'formal-new-streams-acceptance.json'), report)
    print(json.dumps({key: value for key, value in report.items() if key not in ['tasks']}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['canary', 'full'], required=True)
    parser.add_argument('--prefixes', nargs='+', required=True)
    parser.add_argument('--benchmarks', nargs='+', choices=['codeeval', 'babyai'])
    parser.add_argument('--partial', action='store_true')
    args = parser.parse_args()
    audit(args.phase, args.prefixes, args.benchmarks, args.partial)
