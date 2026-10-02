"""Execute only the confirmed 36-task acceptance batch, with dependency barriers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import threading
from runtime import ROOT, REPO, read, save, digest, secret, load_babyai, run_task


def main():
    config = read(ROOT / 'records/confirmed-config-v1.json')
    assert config['user_confirmation'] and config['scope']['initial_online_task_executions'] == 36
    assert config['runtime']['concurrency_proposal']['global_inflight_model_or_embedding_requests'] == 50
    fixtures = read(ROOT / 'records/fixture-acceptance.json')
    assert fixtures['passed'] and fixtures['model_calls'] == 0
    source_names = ['runtime.py', 'pi_runner.mjs', 'recorder.mjs', 'broker.py', 'run_batch.py', 'records/confirmed-config-v1.json']
    freeze = {'schema_version': 'section7-observability-v1', 'config_hash': digest(config),
              'sources': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_names},
              'legacy_core_sha256': hashlib.sha256((REPO / 'experiments/agent_memory_plan_20261002/core.py').read_bytes()).hexdigest(),
              'api_cap': 50, 'planned_tasks': 36, 'planned_max_active_tasks': 16}
    freeze_path = ROOT / 'records/online-freeze-v1.json'
    if freeze_path.exists():
        assert read(freeze_path) == freeze, 'Online source changed after freeze; audit affected runs'
    else:
        save(freeze_path, freeze)
    all_code = read(ROOT / '.cache/agentcl-codeeval.json')
    code = [all_code[item['source_index']] for item in config['data']['code_ordered_tasks']]
    assert [r['category'] + ':' + r['id'] for r in code] == [x['task_id'] for x in config['data']['code_ordered_tasks']]
    baby = [json.loads(line) for line in (ROOT / '.cache/agentcl-babyai.jsonl').read_text(encoding='utf-8').splitlines()]
    baby = [row for row in baby if row['id'] in config['data']['babyai_ordered_task_ids']]
    assert [r['id'] for r in baby] == config['data']['babyai_ordered_task_ids']
    wrapper = load_babyai()
    api_key = secret()
    lock = threading.Lock()
    active = 0
    peak = 0
    results = []
    errors = []

    def execute(method, benchmark, index, row, history):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            return run_task(config, method, benchmark, index, row, history, api_key, wrapper)
        finally:
            with lock:
                active -= 1

    def independent(benchmark, index, row):
        return [execute('no_memory', benchmark, index, row, [])[1]]

    def online(method, benchmark, rows):
        history = []
        output = []
        for index, row in enumerate(rows):
            history, record = execute(method, benchmark, index, row, history)
            output.append(record)
            if record['terminal_state'] != 'completed':
                break
        save(ROOT / '.runtime/runs' / f'section7-v1-{benchmark}-{method}' / 'final-memory.json', history)
        return output

    save(ROOT / 'records/batch-status.json', {'status': 'running', 'planned_tasks': 36, 'api_cap': 50,
         'active_independent_units': 16, 'config_hash': digest(config)})
    with ThreadPoolExecutor(max_workers=50) as pool:
        jobs = [pool.submit(independent, benchmark, index, row) for benchmark, rows in [('codeeval', code), ('babyai', baby)] for index, row in enumerate(rows)]
        jobs.extend(pool.submit(online, method, benchmark, rows)
                    for method in ['bounded_icl', 'episodic_retrieval'] for benchmark, rows in [('codeeval', code), ('babyai', baby)])
        for future in as_completed(jobs):
            try:
                results.extend(future.result())
            except Exception as error:
                errors.append(type(error).__name__ + ': ' + str(error))
            save(ROOT / 'records/batch-status.json', {'status': 'running', 'planned_tasks': 36, 'tasks_committed': len(results),
                 'peak_active_tasks': peak, 'errors': errors})
    results.sort(key=lambda r: (r['run_id'], r['attempt_id']))
    report = {'schema_version': 'section7-observability-v1', 'config_hash': digest(config),
              'planned_tasks': 36, 'tasks_committed': len(results), 'peak_active_tasks': peak,
              'api_cap': 50, 'errors': errors, 'results': results,
              'status': 'completed_pending_audit' if len(results) == 36 and not errors else 'needs_audit'}
    save(ROOT / 'records/batch-results.json', report)
    save(ROOT / 'records/batch-status.json', {k: v for k, v in report.items() if k != 'results'})
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}), flush=True)


if __name__ == '__main__':
    main()
