"""Continue after a verified, committed auxiliary timeout; never rerun a task.

The frozen solver, adapters, prompts and budgets are unchanged. A timeout is
retained as a memory_failure with unknown usage, not changed to a success.
"""
import argparse
import hashlib
import json
from pathlib import Path
from engine import ROOT, read, save, digest, secret, load_babyai, run_task
from complex_memory import make_adapter
from run_methods import task_rows


def review(folder):
    commit = read(folder / 'commit.json')
    execution = read(folder / 'execution.json')
    before, after = [read(folder / name) for name in ['memory-before.json', 'memory-after.json']]
    events = [json.loads(line) for line in (folder / 'controller-events.jsonl').read_text(encoding='utf-8').splitlines()]
    ledgers = [read(path) for path in folder.glob('auxiliary/*/call-ledger.json')]
    aborted = [call for ledger in ledgers for call in ledger if call['status'] == 'aborted']
    assert commit['result']['terminal_state'] == 'memory_failure'
    assert execution['memory_error'] == 'AuxiliaryCallError: Request was aborted'
    assert digest(before) == digest(after) == commit['before_hash'] == commit['after_hash']
    assert len(aborted) == 1 and aborted[0]['duration_monotonic_ms'] >= 179000
    assert all(item['status'] == 200 and item['raw_usage'] is None and not item['provider_finish_reasons']
               and item['error'].startswith('AbortError:') for item in aborted[0]['http_attempts'])
    assert any(item['event'] == 'memory_exception' and item['after_hash'] == commit['after_hash'] for item in events)
    assert not any(item['event'] == 'memory_event' for item in events)
    files = ['commit.json', 'execution.json', 'memory-before.json', 'memory-after.json', 'controller-events.jsonl']
    return {'task_id': commit['result']['task_id'], 'attempt_id': execution['attempt_id'],
            'terminal_state': 'memory_failure', 'classification': 'auxiliary_response_deadline',
            'recovery': 'Continue from the committed unchanged state; no task or auxiliary regeneration',
            'unchanged_state_hash': commit['after_hash'], 'usage_unknown': True,
            'native_operation_journal': 'not_produced: exception before native mutation',
            'hashes': {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in files}}


def main(run_id, review_only=False):
    directory = ROOT / '.runtime/runs' / run_id
    config = read(directory / 'manifest.json')
    assert config['method'] == 'ace' and config['phase'] == 'full'
    prefix = run_id.rsplit('-' + config['benchmark'] + '-', 1)[0]
    version = prefix.removeprefix('section7-full-')
    freeze = read(ROOT / 'records' / f'full-methods-freeze-{version}.json')
    for name, entry in freeze['sources'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == entry['sha256'], name
    reviewed = [review(folder) for folder in sorted(directory.glob('[0-9][0-9][0-9]'))
                if (folder / 'commit.json').exists() and read(folder / 'commit.json')['result']['terminal_state'] != 'completed']
    assert reviewed, 'No stopped committed timeout to recover'
    recovery_path = directory / 'timeout-recovery.json'
    report = {'run_id': run_id, 'configuration_hash': digest(config),
              'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'frozen_model_inputs_and_budgets_unchanged': True, 'task_regeneration': False,
              'reviewed_timeouts': reviewed, 'status': 'reviewed_pending_continuation'}
    save(recovery_path, report)
    if review_only:
        print(json.dumps(report))
        return
    api_key, wrapper = secret(), load_babyai()
    adapter = make_adapter(config['method'], run_id, config, api_key)
    initial = read(directory / 'initial-memory.json')
    adapter.restore(initial)
    history, summary = initial, []
    try:
        for index, row in enumerate(task_rows('full', config['benchmark'])):
            history, record = run_task(config, config['method'], config['benchmark'], index, row, history,
                                       api_key, wrapper, run_prefix=prefix, adapter=adapter)
            summary.append(record)
            save(directory / 'summary.json', summary)
            save(directory / 'final-memory.json', history)
            if record['terminal_state'] != 'completed':
                evidence = review(directory / f'{index:03d}')
                if evidence['attempt_id'] not in {item['attempt_id'] for item in report['reviewed_timeouts']}:
                    report['reviewed_timeouts'].append(evidence)
                save(recovery_path, report)
            save(ROOT / 'records' / 'full-codeeval-ace-progress.json',
                 {'phase': 'full', 'run_id': run_id, 'committed': len(summary), 'planned': config['stream_tasks'],
                  'correct': sum(item['correct'] is True for item in summary), 'terminal_state': record['terminal_state'],
                  'retained_timeout_tasks': len(report['reviewed_timeouts'])})
        report['status'] = 'complete_with_retained_timeouts'
        report['committed_tasks'] = len(summary)
        save(recovery_path, report)
        print(json.dumps(report), flush=True)
    finally:
        adapter.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--review-only', action='store_true')
    arguments = parser.parse_args()
    main(arguments.run_id, arguments.review_only)
