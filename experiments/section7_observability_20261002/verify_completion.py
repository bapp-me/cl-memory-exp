"""Offline completion audit of the approved section 7.0/7.1 scope."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    records = ROOT / 'records'
    evidence = []

    def require(name, condition, paths):
        assert condition, name
        evidence.append({'requirement': name, 'verified': True,
                         'evidence': [{'path': path.relative_to(REPO).as_posix(), 'sha256': sha(path)} for path in paths]})

    common = read(records / 'confirmed-config-v1.json')
    native = read(records / 'complex-confirmed-config-v1.json')
    require('Human configuration approval and authorization for automatic 7.1 execution',
            bool(common['user_confirmation']) and bool(native['user_confirmation'])
            and native['scope']['section7_1_auto_start_after_7_0_pass'],
            [records / 'confirmed-config-v1.json', records / 'complex-confirmed-config-v1.json'])
    inventory = read(records / 'legacy-availability.json')
    reconstruction = read(records / 'legacy-payload-reconstruction.json')
    require('All 208 historical tasks inventoried, with zero-call reconstruction of 549 payloads',
            inventory['integrity_passed'] and inventory['tasks_checked'] == len(inventory['tasks']) == 208
            and not inventory['integrity_errors'] and reconstruction['tasks'] == 208
            and reconstruction['reconstructed_payloads'] == 549 and reconstruction['byte_checks_passed']
            and reconstruction['language_model_calls'] == reconstruction['http_calls'] == 0,
            [records / 'legacy-availability.json', records / 'legacy-payload-reconstruction.json'])
    for name in ['fixture-acceptance.json', 'complex-fixture-acceptance.json', 'parallel-embedding-fixture.json']:
        require('Offline gate: ' + name, read(records / name)['passed'], [records / name])
    for name in ['online-acceptance.json', 'complex-online-acceptance.json']:
        gate = read(records / name)
        require('Online gate: ' + name, gate['passed'] and gate['tasks_checked'] == len(gate['tasks']) == 36
                and not gate['errors'] and all(task['passed'] for task in gate['tasks']), [records / name])

    audit = read(records / 'formal-new-streams-acceptance.json')
    require('All four new 96-task streams pass complete observability audit, including failures',
            audit['passed'] and audit['complete'] and audit['scope'] == 'complete_streams'
            and audit['tasks_checked'] == len(audit['tasks']) == 384 and not audit['errors']
            and all(task['passed'] for task in audit['tasks']) and audit['api_peak'] <= 50,
            [records / 'formal-new-streams-acceptance.json'])
    frozen = read(records / 'full-methods-freeze-v3.json')
    require('Frozen model, adapter, recorder, runner and native configuration sources are unchanged',
            all(sha(ROOT / name) == source['sha256'] == hashlib.sha256(source['text'].encode()).hexdigest()
                for name, source in frozen['sources'].items()), [records / 'full-methods-freeze-v3.json'])

    final = read(records / 'section7.1-final.json')
    pairs = read(records / 'section7.1-pairs.json')
    require('Complete six-method 96-code plus 8-BabyAI R=1 matrix; exact preregistered reuse',
            final['status'] == 'complete' and final['matrix_tasks'] == len(final['results']) == 624
            and not final['issues'] and final['repetitions'] == 1 and len(final['summary']) == 12
            and Counter(row['source_kind'] for row in final['results']) == {
                'new_formal_stream': 384, 'legacy_descriptive_reuse': 208, 'accepted_complete_8_task_canary': 32},
            [records / 'section7.1-final.json', records / 'section7.1-registry.json'])
    excluded = {'raw:BigCodeBench/269', 'new:BigCodeBench/217', 'new:BigCodeBench/355'}
    for summary in final['summary']:
        rows = [row for row in final['results'] if row['method'] == summary['method'] and row['benchmark'] == summary['benchmark']]
        first = read(REPO / rows[0]['source_path'] / 'memory-before.json')
        empty = first == [] if isinstance(first, list) else (
            first['episode_count'] == 0 and not first['provenance']
            and not first.get('points') and not first.get('episodes')
            and not re.search(r'^\[', first.get('playbook', ''), re.MULTILINE))
        assert empty, 'Nonempty initial memory: ' + summary['method'] + ':' + summary['benchmark']
        if summary['benchmark'] == 'codeeval':
            assert len(rows) == 96 and summary['effective_tasks'] == 93 and summary['effective_complex_targets'] == 46
            assert {row['task_id'] for row in rows if row['scorable'] is not True} == excluded
            assert all(row['correct'] is None for row in rows if row['task_id'] in excluded)
            assert summary['all_complex_targets_including_unscorable'] == 48
        else:
            assert len(rows) == 8 and summary['effective_tasks'] == 8
    require('Empty independent initial memory and exact scoring mask, retaining every execution and its cost',
            True, [records / 'section7.1-final.json'])
    require('288 source-target pairs retained with provenance distinct from unknown semantic fidelity',
            len(pairs) == 288 and all(row['content_fidelity_of_source'] is None and row['semantic_applicability'] is None
                                    and row['source_index'] < row['target_index'] for row in pairs),
            [records / 'section7.1-pairs.json'])

    packets = 0
    for run in audit['runs']:
        directory = ROOT / '.runtime/runs' / run['run_id']
        manifest = read(directory / 'manifest.json')
        assert manifest['api_cap'] == 50 and manifest['stream_tasks'] == 96
        assert all(manifest[key] == common[key] for key in ['model', 'runtime', 'memory', 'budgets'])
        assert manifest['native_method_config'] == (None if run['method'] == 'bounded_icl' else native)
        for request_path in directory.glob('**/requests.jsonl'):
            for line in request_path.read_text(encoding='utf-8').splitlines():
                request = json.loads(line)
                payload = read(request_path.parent / request['artifact'])
                assert payload['model'] == 'glm-5.3-flash' and payload['max_tokens'] == 8192
                assert payload['reasoning_effort'] == 'high' and payload['thinking']['type'] == 'enabled'
                assert 'temperature' not in payload and 'seed' not in payload
                assert len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()) <= 320000
                packets += 1
    require('Every actual new request uses approved GLM/high/8192, omitted temperature/seed and byte guard',
            packets == sum(role['http_attempts'] for role in audit['role_accounting'].values()),
            [records / 'formal-new-streams-acceptance.json', records / 'full-methods-freeze-v3.json'])
    recovery_path = ROOT / '.runtime/runs/section7-full-v3-codeeval-ace/timeout-recovery.json'
    recovery = read(recovery_path)
    require('ACE continuation completed without task or auxiliary regeneration; original timeout attempts retained',
            recovery['status'] == 'complete_with_retained_timeouts' and recovery['committed_tasks'] == 96
            and recovery['task_regeneration'] is False and recovery['frozen_model_inputs_and_budgets_unchanged']
            and len(recovery['reviewed_timeouts']) == audit['terminal_states'].get('memory_failure', 0),
            [recovery_path, records / 'timeout-continuation-freeze.json'])
    require('Completed descriptive health statistics; monetary price/invoice remains unknown',
            read(records / 'memory-health.json')['status'] == 'complete' and final['money'] is None
            and all(row['money'] is None for row in final['results']), [records / 'memory-health.json', records / 'section7.1-final.json'])
    for name in ['raw-archive.json', 'canary-native-raw-archive.json', 'full-native-raw-archive.json']:
        index = read(records / name)
        archive = ROOT / index['path']
        require('Verified original evidence archive: ' + name,
                sha(archive) == index['sha256'] and len(index['files_index']) == index['files']
                and (index.get('all_members_hash_verified') or index.get('members_verified'))
                and (index.get('exact_credentials_scan_passed') or index.get('exact_current_api_and_broker_credential_scan_passed')),
                [records / name, archive])
    cleanup = read(records / 'runtime-cleanup.json')
    require('Owned experiment service stopped after both formal runners exited normally',
            cleanup['broker_stopped'] and cleanup['listener_closed']
            and cleanup['original_formal_runner_exit_code'] == cleanup['continuation_runner_exit_code'] == 0,
            [records / 'runtime-cleanup.json'])
    require('Current repository documentation reports completed baselines and preserves R=1 limitations',
            '第 7.0/7.1 节已完成' in (REPO / 'README.md').read_text(encoding='utf-8')
            and '第 7.2 及后续阶段仍待执行' in (REPO / 'Agent_Memory_Research_Plan_CN_v1.0_Final.md').read_text(encoding='utf-8'),
            [REPO / 'README.md', REPO / 'Agent_Memory_Research_Plan_CN_v1.0_Final.md'])
    result = {'objective': 'Approved section 7.0 acceptance and complete section 7.1 baseline matrix',
              'status': 'complete', 'audited_at_utc': datetime.now(timezone.utc).isoformat(),
              'requirements': evidence, 'online_acceptance_tasks': 72, 'new_formal_code_tasks': 384,
              'matrix_tasks': 624, 'actual_new_online_task_executions': 456, 'actual_new_http_requests_checked': packets,
              'additional_model_calls': 0,
              'limits': final['limits'], 'following_phase': '7.2 not executed; validation/final testing not part of this goal'}
    (records / 'section7-completion-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in ['requirements', 'limits']}))


if __name__ == '__main__':
    main()
