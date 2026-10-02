"""Assemble the six-method matrix with fixed masks, paired provenance and costs."""
from collections import Counter
import json
from pathlib import Path
import re
from engine import ROOT, REPO, read, save, digest, USAGE_FIELDS


def optional_json(path):
    return read(path) if path.exists() else None


def main():
    registry = read(ROOT / 'records/section7.1-registry.json')
    assets = read(ROOT / '.cache/agentcl-codeeval.json')
    expected_code = [row['category'] + ':' + row['id'] for row in assets]
    baby_ids = ['38', '39', '36', '37', '53', '52', '54', '55']
    all_rows, pair_rows, summaries, issues = [], [], [], []
    for entry in registry['runs']:
        path = REPO / entry['path']
        rows = []
        for folder in sorted(path.glob('[0-9][0-9][0-9]')):
            if not (folder / 'commit.json').exists():
                issues.append({'run': entry['path'], 'folder': folder.name, 'error': 'Missing final commit'})
                continue
            commit = read(folder / 'commit.json')
            result = commit['result']
            task_id = str(result['task_id'])
            record = {'method': entry['method'], 'benchmark': entry['benchmark'], 'task_id': task_id,
                      'index': int(folder.name), 'source_kind': entry['source_kind'],
                      'source_path': folder.relative_to(REPO).as_posix(),
                      'correct': result['correct'], 'scorable': result['scorable'],
                      'terminal_state': result.get('terminal_state', 'historical_committed'),
                      'response_timed_out': result.get('response_timed_out'),
                      'context_exceeded': result.get('context_exceeded'),
                      'solver_error': result.get('error'), 'memory_error': result.get('memory_error'),
                      'submitted': result.get('submitted'), 'tool_calls': result.get('tool_calls'),
                      'turns': result.get('turns'), 'solver_seconds': result.get('seconds'),
                      'total_system_seconds': result.get('total_system_seconds'),
                      'usage': result.get('usage'),
                      'known_usage_subtotal': result.get('known_usage_subtotal', result.get('usage')),
                      'role_accounting': result.get('role_accounting'),
                      'unknown_usage_http_attempts': result.get('unknown_usage_http_attempts'),
                      'money': None, 'money_reason': 'No verified runtime price/invoice',
                      'historical_usage_status': 'retained SDK counters; raw provider and failed-request usage not verified' if entry['source_kind'] == 'legacy_descriptive_reuse' else None}
            payload = optional_json(folder / 'pi-result.json')
            if payload:
                if record['response_timed_out'] is None:
                    record['response_timed_out'] = payload.get('responseTimedOut')
                if record['context_exceeded'] is None:
                    record['context_exceeded'] = payload.get('contextExceeded')
            tools = []
            if payload:
                tools = [item for message in payload['messages'] if message['role'] == 'assistant'
                         for item in message.get('content', []) if item.get('type') == 'toolCall']
            record['tools_by_name'] = dict(Counter(item['name'] for item in tools))
            record['working_tool_calls'] = sum(item['name'] in ['PYTHON', 'ACTION', 'QUERY'] for item in tools)
            record['submit_calls'] = sum(item['name'] == 'SUBMIT' for item in tools)
            rows.append(record)
        expected = expected_code if entry['benchmark'] == 'codeeval' else baby_ids
        if [row['task_id'] for row in rows] != expected:
            issues.append({'run': entry['path'], 'error': 'Incomplete or wrong task ID/order',
                           'expected': len(expected), 'actual': len(rows)})
        effective = [row for row in rows if row['scorable'] is True]
        targets = [row for row in effective if row['task_id'].startswith('new:')]
        if entry['benchmark'] == 'codeeval' and (len(effective) != 93 or len(targets) != 46):
            issues.append({'run': entry['path'], 'error': 'Wrong scoring mask denominators',
                           'full_effective': len(effective), 'target_effective': len(targets)})
        known_tokens = {key: sum((row['known_usage_subtotal'] or {}).get(key, 0) for row in rows) for key in USAGE_FIELDS}
        target_tokens = {key: sum((row['known_usage_subtotal'] or {}).get(key, 0) for row in targets) for key in USAGE_FIELDS}
        roles = sorted({role for row in rows for role in (row['role_accounting'] or {})})
        all_roles = {role: {
            'logical_call_attempts': sum((row['role_accounting'] or {}).get(role, {}).get('calls', 0) for row in rows),
            'http_attempts': sum((row['role_accounting'] or {}).get(role, {}).get('http_attempts', 0) for row in rows),
            'unknown_usage_http_attempts': sum((row['role_accounting'] or {}).get(role, {}).get('unknown_usage_attempts', 0) for row in rows),
            'known_usage': {key: sum((row['role_accounting'] or {}).get(role, {}).get('known_usage', {}).get(key, 0) for row in rows) for key in USAGE_FIELDS}
        } for role in roles}
        summary = {'method': entry['method'], 'benchmark': entry['benchmark'], 'tasks': len(rows),
                   'response_timeout_tasks': sum(row['response_timed_out'] is True for row in rows),
                   'response_timeout_observation_missing_tasks': sum(row['response_timed_out'] is None for row in rows),
                   'context_budget_exceeded_tasks': sum(row['context_exceeded'] is True for row in rows),
                   'unsubmitted_tasks': sum(row['submitted'] is False for row in rows),
                   'terminal_states': dict(Counter(row['terminal_state'] for row in rows)),
                   'memory_failures_retained_in_scores_and_costs': sum(row['terminal_state'] == 'memory_failure' for row in rows),
                   'effective_tasks': len(effective), 'correct': sum(row['correct'] is True for row in effective),
                   'effective_complex_targets': len(targets) if entry['benchmark'] == 'codeeval' else None,
                   'correct_complex_targets': sum(row['correct'] is True for row in targets) if entry['benchmark'] == 'codeeval' else None,
                   'retained_usage_total': known_tokens, 'usage_missing_tasks': sum(row['usage'] is None for row in rows),
                   'all_role_accounting': all_roles if roles else None,
                   'effective_complex_target_usage_subtotal': target_tokens if entry['benchmark'] == 'codeeval' else None,
                   'effective_complex_target_usage_missing_tasks': sum(row['usage'] is None for row in targets) if entry['benchmark'] == 'codeeval' else None,
                   'effective_complex_target_working_tool_calls': sum(row['working_tool_calls'] for row in targets) if entry['benchmark'] == 'codeeval' else None,
                   'usage_provenance': 'unverified historical SDK counters' if entry['source_kind'] == 'legacy_descriptive_reuse' else 'returned raw HTTP usage, all roles included',
                   'working_tool_calls': sum(row['working_tool_calls'] for row in rows),
                   'submit_calls': sum(row['submit_calls'] for row in rows), 'source_kind': entry['source_kind'],
                   'money': None, 'latency_cross_method_comparable': entry['source_kind'] != 'legacy_descriptive_reuse'}
        summaries.append(summary)
        all_rows.extend(rows)
        if entry['benchmark'] != 'codeeval':
            continue
        raw_map = {row['task_id'].split(':', 1)[1]: row for row in rows if row['task_id'].startswith('raw:')}
        for target in [row for row in rows if row['task_id'].startswith('new:')]:
            target_asset = assets[target['index']]
            source = raw_map[target_asset['corresponding_raw_id']]
            folder = REPO / target['source_path']
            before = read(folder / 'memory-before.json')
            injected = read(folder / 'injected.json')
            retrieval = optional_json(folder / 'retrieval.json')
            source_attempt = entry['run_id'] + f".task-{source['index']:03d}.attempt-1"
            retained, injected_provenance = None, None
            if entry['method'] in ['bounded_icl', 'episodic_retrieval', 'no_memory']:
                source_text = assets[source['index']]['problem']
                def has_episode(episodes):
                    return any(json.loads(episode['text'])['task'] == source_text for episode in episodes)
                retained, injected_provenance = has_episode(before), has_episode(injected)
                raw_episode_retained = retained
                source_ids = {digest(episode) for episode in before if has_episode([episode])}
                candidate_provenance = bool(source_ids & {item['memory_id'] for item in retrieval['observable_candidates']}) if retrieval else None
            else:
                provenance = before.get('provenance', {})
                retained = any(source_attempt in origins for origins in provenance.values())
                selected_ids = [item['memory_id'] for item in injected]
                injected_provenance = any(source_attempt in provenance.get(memory_id, []) for memory_id in selected_ids)
                raw_episode_retained = source_attempt in before['source_attempts'] if entry['method'] == 'awm' else False
                candidate_provenance = any(source_attempt in provenance.get(item['memory_id'], []) for item in retrieval['observable_candidates']) if retrieval else None
            pair_rows.append({'method': entry['method'], 'source_task_id': source['task_id'], 'target_task_id': target['task_id'],
                              'source_index': source['index'], 'target_index': target['index'],
                              'distance': target['index'] - source['index'], 'source_correct': source['correct'],
                              'source_scorable': source['scorable'], 'target_correct': target['correct'], 'target_scorable': target['scorable'],
                              'source_experience_legally_executed_before_target': True,
                              'raw_source_episode_retained_in_method_state': raw_episode_retained,
                              'source_provenance_retained': retained, 'source_provenance_injected': injected_provenance,
                              'source_provenance_in_observable_retrieval_candidates': candidate_provenance,
                              'candidate_observation_unknown_reason': 'No per-task candidate artifact in this historical result' if retrieval is None else None,
                              'content_fidelity_of_source': None, 'semantic_applicability': None,
                              'unknown_reason': 'Provenance does not prove required source content survived abstraction or is useful to target',
                              'target_usage': target['usage'], 'target_known_usage_subtotal': target['known_usage_subtotal'],
                              'target_unknown_usage_http_attempts': target['unknown_usage_http_attempts'],
                              'target_tools': target['tools_by_name'],
                              'memory_before_path': (folder / 'memory-before.json').relative_to(REPO).as_posix(),
                              'injection_path': (folder / 'injected.json').relative_to(REPO).as_posix()})
    assert len(registry['runs']) == 12
    if len(all_rows) != 624:
        issues.append({'error': 'Formal matrix is incomplete', 'expected': 624, 'actual': len(all_rows)})
    report = {'phase': '7.1', 'status': 'complete' if not issues else 'incomplete', 'repetitions': 1,
              'matrix_tasks': len(all_rows), 'methods': 6, 'issues': issues, 'summary': summaries,
              'results': all_rows, 'paired_source_target_rows': pair_rows, 'money': None,
              'limits': ['R=1; no stability or causal advantage claim.', 'Old No Memory/episodic are descriptive historical reuse with alias and cost/latency limits.',
                         'Canary full BabyAI families reused explicitly; short code canaries not used as formal streams.',
                         'Source provenance retained/injected is not semantic fidelity or causally effective use.',
                         'Fixed scoring mask retained all executions and costs; unscorable results stay null.']}
    save(ROOT / 'records/section7.1-final.json', report)
    save(ROOT / 'records/section7.1-pairs.json', pair_rows)
    print(json.dumps({key: value for key, value in report.items() if key not in ['results', 'paired_source_target_rows']}))
    if issues:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
