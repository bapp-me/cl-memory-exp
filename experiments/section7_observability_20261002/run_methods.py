"""Approved native canary/formal streams with isolated state and commit barriers."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import hashlib
import json
from pathlib import Path
import threading
import time
from engine import ROOT, read, save, digest, secret, load_babyai, run_task
from complex_memory import make_adapter


def task_rows(phase, benchmark):
    common = read(ROOT / 'records/confirmed-config-v1.json')
    if benchmark == 'codeeval':
        rows = read(ROOT / '.cache/agentcl-codeeval.json')
        return [rows[item['source_index']] for item in common['data']['code_ordered_tasks']] if phase == 'canary' else rows
    all_rows = [json.loads(line) for line in (ROOT / '.cache/agentcl-babyai.jsonl').read_text(encoding='utf-8').splitlines()]
    return [row for row in all_rows if row['id'] in common['data']['babyai_ordered_task_ids']]


def effective_config(phase, method, benchmark, rows):
    common = read(ROOT / 'records/confirmed-config-v1.json')
    native = read(ROOT / 'records/complex-confirmed-config-v1.json')
    return {**copy.deepcopy(common), 'config_id': f'section7-{phase}-{benchmark}-{method}-v2',
            'native_method_config': native if method in ['mem0', 'awm', 'ace'] else None,
            'phase': phase, 'method': method, 'benchmark': benchmark, 'stream_tasks': len(rows),
            'ordered_task_ids': [row['category'] + ':' + row['id'] if benchmark == 'codeeval' else str(row['id']) for row in rows],
            'status': 'user_confirmed', 'api_cap': 50, 'observability_schema_version': 'section7-observability-v2'}


def freeze(phase, jobs, version):
    paths = ['engine.py', 'complex_memory.py', 'aux_client.py', 'aux_runner.mjs', 'recorder_v2.mjs',
             'pi_runner_v2.mjs', 'run_methods.py', 'records/complex-confirmed-config-v1.json',
             'records/complex-environment.json', 'records/complex-requirements-lock.txt']
    report = {'phase': phase, 'schema_version': 'section7-observability-v2', 'api_cap': 50,
              'sources': {name: {'sha256': hashlib.sha256((ROOT / name).read_bytes()).hexdigest(),
                                'text': (ROOT / name).read_bytes().decode('utf-8')} for name in paths},
              'native_sources': read(ROOT / 'records/complex-source-audit.json'),
              'jobs': [{'method': method, 'benchmark': benchmark, 'tasks': len(rows), 'config_hash': digest(config)}
                       for method, benchmark, rows, config in jobs]}
    destination = ROOT / 'records' / f'{phase}-methods-freeze-{version}.json'
    if destination.exists():
        assert read(destination) == report, 'Sources changed after run freeze; version and rerun affected configuration'
    else:
        save(destination, report)


def run(phase, methods, benchmarks, version='v2'):
    native = read(ROOT / 'records/complex-confirmed-config-v1.json')
    assert native['user_confirmation']
    assert read(ROOT / 'records/complex-fixture-acceptance.json')['passed']
    if phase == 'full':
        assert native['scope']['section7_1_auto_start_after_7_0_pass']
        assert read(ROOT / 'records/complex-online-acceptance.json')['passed']
    jobs = []
    for method in methods:
        for benchmark in benchmarks:
            rows = task_rows(phase, benchmark)
            jobs.append((method, benchmark, rows, effective_config(phase, method, benchmark, rows)))
    freeze(phase, jobs, version)
    wrapper = load_babyai()
    api_key = secret()
    lock = threading.Lock()
    results, errors = [], []
    completed_streams = set()

    def stream(method, benchmark, rows, config):
        prefix = f'section7-{phase}-{version}'
        run_id = f'{prefix}-{benchmark}-{method}'
        directory = ROOT / '.runtime/runs' / run_id
        directory.mkdir(parents=True, exist_ok=True)
        save(directory / 'manifest.json', config)
        initialization_started = time.monotonic()
        try:
            adapter = make_adapter(method, run_id, config, api_key) if method in ['mem0', 'awm', 'ace'] else None
            save(directory / 'startup.json', {'startup_attempt_id': run_id + '.startup-1', 'terminal_state': 'ready',
                 'seconds': time.monotonic() - initialization_started, 'language_model_calls': 0})
        except Exception as error:
            save(directory / 'startup.json', {'startup_attempt_id': run_id + '.startup-1', 'terminal_state': 'failed',
                 'seconds': time.monotonic() - initialization_started, 'language_model_calls': 0,
                 'error': type(error).__name__ + ': ' + str(error)})
            raise
        # Rewind to the first logical snapshot, then replay only already committed states.
        initial = read(directory / 'initial-memory.json') if (directory / 'initial-memory.json').exists() else adapter.snapshot() if adapter else []
        if adapter:
            adapter.restore(initial)
        if not (directory / 'initial-memory.json').exists():
            save(directory / 'initial-memory.json', initial)
        history = initial
        summary = []
        try:
            for index, row in enumerate(rows):
                history, record = run_task(config, method, benchmark, index, row, history, api_key,
                                           wrapper, run_prefix=prefix, adapter=adapter)
                summary.append(record)
                save(directory / 'summary.json', summary)
                save(directory / 'final-memory.json', history)
                with lock:
                    progress = {'phase': phase, 'run_id': run_id, 'committed': len(summary), 'planned': len(rows),
                                'correct': sum(item['correct'] is True for item in summary),
                                'terminal_state': record['terminal_state']}
                    save(ROOT / 'records' / f'{phase}-{benchmark}-{method}-progress.json', progress)
                if record['terminal_state'] != 'completed':
                    break
            return summary
        finally:
            if adapter:
                adapter.close()

    status_name = f'{phase}-methods-status-{version}.json'
    save(ROOT / 'records' / status_name, {'status': 'running', 'phase': phase,
         'planned_tasks': sum(len(rows) for _, _, rows, _ in jobs), 'independent_streams': len(jobs), 'api_cap': 50})
    with ThreadPoolExecutor(max_workers=min(50, len(jobs))) as pool:
        futures = {pool.submit(stream, *job): job[:2] for job in jobs}
        for future in as_completed(futures):
            method, benchmark = futures[future]
            try:
                rows = future.result()
                results.extend(rows)
                completed_streams.add(method + ':' + benchmark)
            except Exception as error:
                errors.append({'method': method, 'benchmark': benchmark, 'error': type(error).__name__ + ': ' + str(error)})
            save(ROOT / 'records' / status_name, {'status': 'running', 'phase': phase,
                 'committed_returned': len(results), 'completed_streams': sorted(completed_streams), 'errors': errors, 'api_cap': 50})
    planned = sum(len(rows) for _, _, rows, _ in jobs)
    report = {'phase': phase, 'planned_tasks': planned, 'tasks_committed': len(results), 'errors': errors,
              'status': 'completed_pending_audit' if len(results) == planned and not errors else 'needs_repair', 'results': results}
    save(ROOT / 'records' / f'{phase}-methods-results-{version}.json', report)
    save(ROOT / 'records' / status_name, {key: value for key, value in report.items() if key != 'results'})
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['canary', 'full'], required=True)
    parser.add_argument('--version', default='v2')
    parser.add_argument('--methods', nargs='+', choices=['no_memory', 'bounded_icl', 'episodic_retrieval', 'mem0', 'awm', 'ace'], default=['mem0', 'awm', 'ace'])
    parser.add_argument('--benchmarks', nargs='+', choices=['codeeval', 'babyai'], default=['codeeval', 'babyai'])
    arguments = parser.parse_args()
    run(arguments.phase, arguments.methods, arguments.benchmarks, arguments.version)
