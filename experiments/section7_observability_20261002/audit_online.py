"""Audit the confirmed batch without changing any online state or model input."""
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tarfile
from runtime import ROOT, REPO, read, save, digest, retrieval_record, normalized_usage


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main():
    config = read(ROOT / 'records/confirmed-config-v1.json')
    freeze = read(ROOT / 'records/online-freeze-v1.json')
    errors = []
    tasks = []
    identifiers = set()
    calls = []
    transport_intervals = []
    groups = defaultdict(list)
    reconciliations = []
    run_root = ROOT / '.runtime/runs'
    snapshot = read(ROOT / 'records/online-source-snapshot-v1.json')
    patch_path = ROOT / 'records/post-run-passive-repair.json'
    patch = read(patch_path) if patch_path.exists() else {}
    patch_files = patch.get('files', [patch] if patch.get('file') else [])
    expected = {(method, benchmark): 4 if benchmark == 'codeeval' else 8
                for method in ['no_memory', 'bounded_icl', 'episodic_retrieval'] for benchmark in ['codeeval', 'babyai']}
    for name, expected_hash in freeze['sources'].items():
        frozen = snapshot['files'][name]
        if frozen['sha256'] != expected_hash or hashlib.sha256(frozen['text'].encode()).hexdigest() != expected_hash:
            errors.append({'source': name, 'error': 'Frozen source snapshot hash mismatch'})
        current_hash = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if current_hash != expected_hash and not any(name == item.get('file') and current_hash == item.get('after_sha256') and expected_hash == item.get('before_sha256') for item in patch_files):
            errors.append({'source': name, 'error': 'Unregistered change after online freeze'})
    for (method, benchmark), count in expected.items():
        run_id = f'section7-v1-{benchmark}-{method}'
        folders = sorted((run_root / run_id).glob('[0-9][0-9][0-9]'))
        if len(folders) != count:
            errors.append({'run_id': run_id, 'expected': count, 'directories': len(folders)})
        previous = []
        for folder in folders:
            local_errors = []

            def check(name, condition):
                if not condition:
                    local_errors.append(name)

            needed = ['identity.json', 'legal-task.json', 'execution.json', 'pi-result.json', 'memory-before.json',
                      'memory-after.json', 'injected.json', 'retrieval.json', 'commit.json', 'submission-status.json',
                      'evaluator.json', 'input-public.json', 'call-ledger.json', 'events.jsonl', 'controller-events.jsonl',
                      'requests.jsonl', 'transport.jsonl', 'calls.jsonl', 'tools.jsonl']
            check('all_required_records_present', all((folder / name).exists() for name in needed))
            if local_errors:
                errors.append({'run_id': run_id, 'task_directory': folder.name, 'errors': local_errors})
                continue
            parsed = {name: jsonl(folder / name) if name.endswith('.jsonl') else read(folder / name) for name in needed}
            identity = parsed['identity.json']
            attempt_id = identity['attempt_id']
            check('unique_attempt_id', attempt_id not in identifiers)
            identifiers.add(attempt_id)
            before, after, injected = [parsed[name] for name in ['memory-before.json', 'memory-after.json', 'injected.json']]
            execution, commit = parsed['execution.json'], parsed['commit.json']
            check('config_hash', commit['config_hash'] == digest(config) == freeze['config_hash'])
            check('before_hash', digest(before) == commit['before_hash'] == execution['memory_hash'])
            check('after_hash', digest(after) == commit['after_hash'])
            check('injected_hash', digest(injected) == execution['injected_hash'])
            check('retrieval_and_packing', digest(retrieval_record(before, method, parsed['legal-task.json']['prompt'])[0]) == digest(injected))
            check('history_chain', before == ([] if method == 'no_memory' else previous))
            check('no_future_entries', all(entry in before for entry in injected))
            if method == 'no_memory':
                check('no_memory_channels_empty', before == after == injected == [])
            else:
                check('legal_one_episode_append', after[:-1] == before and len(after) == len(before) + 1)
                check('writer_excludes_evaluator_and_reasoning', set(json.loads(after[-1]['text'])) == {'task', 'trajectory'} and
                      all(not (isinstance(item, dict) and item.get('type') == 'thinking') for item in json.loads(after[-1]['text'])['trajectory']))
            previous = after
            memory_events = [e for e in parsed['controller-events.jsonl'] if e['event'] == 'memory_event']
            check('write_provenance', len(memory_events) == 1 and memory_events[0]['source_event_ids'] == [attempt_id] and
                  memory_events[0]['before_hash'] == digest(before) and memory_events[0]['after_hash'] == digest(after))
            check('terminal_state', commit['result']['terminal_state'] == 'completed')
            submission = parsed['submission-status.json']
            check('submission_status_matches', execution['submitted'] == submission['submitted'])
            if submission['submitted']:
                check('submission_tool_acknowledgement', any(e['event'] == 'submission' and e['tool_call_id'] == submission['tool_call_id']
                                                           for e in parsed['controller-events.jsonl']))
                if benchmark == 'codeeval':
                    submitted_tool = next((item for message in parsed['pi-result.json']['messages'] if message['role'] == 'assistant'
                                           for item in message.get('content', []) if item.get('type') == 'toolCall' and item.get('id') == submission['tool_call_id']), None)
                    submitted_text = submitted_tool['arguments']['code'] if submitted_tool else None
                    artifact = folder / 'submission.py'
                    check('submitted_text_matches_acknowledged_tool_argument', submitted_text is not None and
                          hashlib.sha256(submitted_text.encode()).hexdigest() == submission['artifact_sha256'])
                    raw_artifact = artifact.read_bytes() if artifact.exists() else None
                    normalized_file = raw_artifact.decode('utf-8').replace('\r\n', '\n') if raw_artifact else None
                    normalized_submit = submitted_text.replace('\r\n', '\n') if submitted_text is not None else None
                    check('submitted_file_matches_original_text', raw_artifact is not None and normalized_file == normalized_submit)
                    actual_hash = hashlib.sha256(raw_artifact).hexdigest() if raw_artifact is not None else None
                    reconciliations.append({'attempt_id': attempt_id, 'tool_call_id': submission['tool_call_id'],
                        'submitted_text_sha256': submission['artifact_sha256'], 'observed_file_bytes_sha256': actual_hash,
                        'exact_bytes_match': actual_hash == submission['artifact_sha256'],
                        'newline_normalized_text_matches': normalized_file == normalized_submit,
                        'sources': [(folder / 'pi-result.json').relative_to(REPO).as_posix(), artifact.relative_to(REPO).as_posix()],
                        'status': 'reconstructable_text_and_file_hashes', 'original_evidence_modified': False})
            expected_injection = set(parsed['retrieval.json']['injected_ids'])
            ledger = parsed['call-ledger.json']
            check('call_count', execution['calls'] == len(ledger))
            request_keys = {(r['call_id'], r['http_attempt']) for r in parsed['requests.jsonl']}
            ledger_keys = {(call['call_id'], attempt['http_attempt']) for call in ledger for attempt in call['http_attempts']}
            check('request_attempts_accounted', request_keys == ledger_keys)
            raw_usages = []
            for call in ledger:
                check('unique_call_id', call['call_id'] not in identifiers)
                identifiers.add(call['call_id'])
                check('call_identity_and_role', call['attempt_id'] == attempt_id and call['role'] == 'solver')
                check('generation_end_and_duration', call['finished_at'] is not None and call['duration_monotonic_ms'] is not None)
                calls.append(call)
                for attempt in call['http_attempts']:
                    raw_usages.append(normalized_usage(attempt['raw_usage']))
                    check('http_attempt_completion', attempt['finished_at'] is not None)
                    starts = [e for e in parsed['transport.jsonl'] if e['event'] == 'http_start' and e['call_id'] == call['call_id'] and e['http_attempt'] == attempt['http_attempt']]
                    ends = [e for e in parsed['transport.jsonl'] if e['event'] == 'http_end' and e['call_id'] == call['call_id'] and e['http_attempt'] == attempt['http_attempt']]
                    check('http_start_end_pair', len(starts) == len(ends) == 1)
                    transport_intervals.extend([(datetime.fromisoformat(attempt['started_at'].replace('Z', '+00:00')).timestamp(), 1),
                                                (datetime.fromisoformat(attempt['finished_at'].replace('Z', '+00:00')).timestamp(), -1)])
            known = [u for u in raw_usages if u is not None]
            total = {k: sum(u[k] for u in known) for k in ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens']}
            check('raw_usage_reconciliation', total == execution['known_usage_subtotal'])
            check('unknown_usage_count', len(raw_usages) - len(known) == execution['unknown_usage_http_attempts'])
            check('unknown_not_zero', execution['usage'] == (total if raw_usages and len(known) == len(raw_usages) else None))
            if execution['usage'] is not None:
                check('provider_usage_matches_pi', execution['usage'] == execution['pi_usage_unverified'])
            for request in parsed['requests.jsonl']:
                payload_path = folder / request['artifact']
                payload = read(payload_path)
                # Actual HTTP hash uses JSON.stringify escaping; recreate its ordinary string encoding.
                check('actual_body_sha256', hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() == request['actual_body_sha256'])
                check('candidate_to_actual_system_injection', request['all_injected_blocks_mapped'] and
                      {block['memory_id'] for block in request['blocks']} == expected_injection)
                check('credential_fields_excluded', not any(k.lower() in {'authorization', 'api_key', 'access_token'} for k in payload))
                check('model_identity', payload['model'] == config['model']['api_id'])
            if local_errors:
                errors.append({'run_id': run_id, 'task_id': identity['task_id'], 'errors': sorted(set(local_errors))})
            record = {'run_id': run_id, 'task_id': identity['task_id'], 'attempt_id': attempt_id, 'passed': not local_errors,
                      'correct': commit['result']['correct'], 'requests': len(parsed['requests.jsonl']),
                      'known_usage': total, 'unknown_usage_http_attempts': execution['unknown_usage_http_attempts'],
                      'injected_utf8_bytes': parsed['retrieval.json']['injected_utf8_bytes'],
                      'calls': len(ledger), 'path': folder.relative_to(REPO).as_posix()}
            tasks.append(record)
            groups[(method, benchmark)].append(record)
    active = 0
    api_peak = 0
    for _, delta in sorted(transport_intervals, key=lambda p: (p[0], p[1])):
        active += delta
        api_peak = max(api_peak, active)
    if api_peak > 50:
        errors.append({'api_peak': api_peak, 'error': 'Exceeds confirmed API cap'})
    summary = []
    for (method, benchmark), rows in sorted(groups.items()):
        summary.append({'method': method, 'benchmark': benchmark, 'tasks': len(rows),
                        'correct': sum(r['correct'] is True for r in rows), 'calls': sum(r['calls'] for r in rows),
                        'http_attempts': sum(r['requests'] for r in rows),
                        'known_usage': {k: sum(r['known_usage'][k] for r in rows) for k in ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens']},
                        'unknown_usage_http_attempts': sum(r['unknown_usage_http_attempts'] for r in rows)})
    report = {'schema_version': 'section7-observability-v1', 'passed': not errors and len(tasks) == 36,
              'model_calls_during_audit': 0, 'tasks_checked': len(tasks), 'calls': len(calls),
              'http_attempts': sum(len(c['http_attempts']) for c in calls), 'observed_api_peak': api_peak,
              'observed_api_peak_measurement': 'Overlap of HTTP start/end wall timestamps recorded in each process; millisecond precision',
              'errors': errors, 'summary': summary, 'tasks': tasks,
              'scope': 'Three simple methods only; Mem0/AWM/ACE not yet accepted',
              'monetary_cost': None, 'cost_unknown_reason': 'No verified price manifest or invoice',
              'performance_interpretation': 'Observability canary; 4 code tasks are not the 96-task formal stream; R=1, no ranking or stability claim'}
    report['submission_hash_reconciliation'] = {'code_submissions': len(reconciliations),
        'text_vs_file_byte_hash_mismatches': sum(not row['exact_bytes_match'] for row in reconciliations),
        'all_original_tool_texts_match_files_after_newline_normalization': all(row['newline_normalized_text_matches'] for row in reconciliations),
        'status': 'Original v1 hash denotes submitted text; exact disk-byte hashes reconstructed offline and kept separately'}
    cancellations = [attempt for call in calls for attempt in call['http_attempts'] if attempt.get('error') == 'consumer_cancelled']
    report['stream_close_reconciliation'] = {
        'legacy_consumer_cancelled_records': len(cancellations),
        'all_have_http_200_returned_usage_and_normal_model_stop': all(call.get('status') in {'stop', 'toolUse'} and attempt['status'] == 200 and attempt['raw_usage'] is not None
            for call in calls for attempt in call['http_attempts'] if attempt.get('error') == 'consumer_cancelled'),
        'interpretation': 'Normal SDK consumer closure inferred from HTTP 200, final provider usage and normal message stop; original strings preserved. Future recorder distinguishes received SSE DONE explicitly.',
        'inference_not_raw_done_evidence_for_v1': True}
    save(ROOT / 'records/submission-artifact-reconciliation.json', {'model_calls': 0, 'records': reconciliations})
    save(ROOT / 'records/online-acceptance.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in {'tasks'}}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
