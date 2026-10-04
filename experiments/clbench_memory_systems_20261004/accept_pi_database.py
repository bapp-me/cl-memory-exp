"""Mechanical admission for the Pi/database arms, with explicit evidence limits."""
import json
from prepare import ROOT, read, save, sha


def main():
    assert read(ROOT / 'records/database-fixtures.json')['status'] == 'passed'
    sdk = read(ROOT / 'records/pi-sdk-fixtures.json')
    assert any(c.get('controller_failure_stops_model_calls') for c in sdk['checks'])
    assert any(c.get('output_growth') for c in sdk['checks'])
    assert any(c.get('long_compaction') for c in sdk['checks'])
    live = read(ROOT / 'records/pi-live-capability.json')
    assert live['status'] == 'passed'
    assert all(c.get('wire_reasoning_effort') == 'high' for c in live['checks'])
    assert read(ROOT / 'records/protocol-chat-window.json')['context_window_verified']
    path = ROOT / 'records/compatibility.json'
    matrix = read(path) if path.exists() else {}
    evidence = []
    for method in ['pi_none', 'pi_notepad', 'pi_jaccard']:
        run_id = 'candidate-db-' + method.replace('_', '-') + '-v3'
        directory = ROOT / 'private-runs' / run_id
        results = read(directory / 'results.json')
        assert len(results) == 2
        assert read(directory / 'stream-status.json')['status'] == 'prefix_completed'
        ids = [row['session_id'] for row in results]
        assert len(set(ids)) == 2
        for index, row in enumerate(results):
            out = directory / f'task-{index:03d}'
            assert read(out / 'barrier.json')['durable']
            before = read(out / 'memory-before.json')
            after = read(out / 'memory-after.json')
            assert before['namespace'] == f'{method}/r1/database_exploration' == after['namespace']
            if method == 'pi_none': assert before['history'] == after['history'] == [] and after['notepad'] == ''
            if method == 'pi_jaccard':
                assert all(e['index'] < index for e in before['history'])
                assert [e['index'] for e in after['history']] == list(range(index + 1))
            for attempt in row['attempts']:
                assert attempt['returned_model'].lower() == 'glm-5.3-flash'
                assert attempt['usage'] is not None
                assert attempt['usage']['total_tokens'] <= 262144
            for payload_file in (out / 'requests').glob('*.request.json'):
                payload = read(payload_file)
                assert payload['model'] == 'glm-5.3-flash'
                assert set(t['function']['name'] for t in payload.get('tools', [])) <= {'CLBENCH_ACTION'}
        matrix.setdefault(method, {})['database_exploration'] = {'status': 'READY',
            'evidence': ['records/database-fixtures.json', 'records/pi-sdk-fixtures.json',
                         'records/pi-live-capability.json', 'records/protocol-chat-window.json',
                         'private-runs/' + run_id],
            'canary_prefix_reused': False,
            'allow': 'R1 full-system database results and all-attempt token accounting',
            'limitations': ['R1 cannot establish a stable ranking or pure memory causality',
                           'token estimator is native Pi, not exact GLM tokenizer',
                           'v3 database canaries prove task/session/state plumbing only; their effort mapping was incomplete and they are excluded from formal scores',
                           'corrected high mapping verified in current real-model capability calls and offline payload fixtures',
                           'final error-handling fixes verified offline; formal stream starts cold']}
        matrix[method].setdefault('codebase_adaptation', {'status': 'BLOCKED',
            'reason': 'acceptance in progress after WSL restart affected code canaries; not algorithm failure'})
        evidence.append({'method': method, 'run_id': run_id, 'instances': 2,
                         'all_http_attempts_have_usage': True, 'same_environment_only': True})
    for method in ['codex_memory_ready', 'claude_memory_ready', 'hermes_memory_ready']:
        matrix.setdefault(method, {env: {'status': 'BLOCKED', 'reason': 'native adapter and lifecycle acceptance not completed'}
                                  for env in ['database_exploration', 'codebase_adaptation']})
    save(path, matrix)
    save(ROOT / 'records/pi-database-acceptance.json', {'status': 'passed', 'evidence': evidence,
        'formal_policy': 'new clean streams; all earlier canaries remain test cost',
        'current_runtime_files': {name: sha(ROOT / name) for name in
            ['pi_session.mjs', 'run_pi_database.py', 'database_adapter.py', 'protocol.py']}})
    print({'database_READY': 3, 'formal_prefixes_reused': 0})


if __name__ == '__main__': main()
