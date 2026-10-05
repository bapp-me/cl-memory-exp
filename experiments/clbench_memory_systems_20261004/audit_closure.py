"""Offline completion and exhaustive cost partition; never calls a model."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from prepare import ROOT, read, save, sha
from protocol import digest
from native_evidence import archive, validate, memory_snapshot, validate_attempt_accounting


def aggregate(calls):
    return {
        'attempts': len(calls),
        'unknown_usage_attempts': sum(c['total_tokens'] is None for c in calls),
        **{key + '_known': sum(c.get(key) or 0 for c in calls)
           for key in ['input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens']},
        'published_price_equivalent_known_usd': round(sum(c.get('published_price_estimate_usd') or 0 for c in calls), 6),
        'unpriced_attempts': sum(c.get('published_price_estimate_usd') is None for c in calls),
    }


def main():
    ledger = read(ROOT/'records/attempt-ledger.json')
    ids = {x['attempt_id'] for x in ledger}
    assert len(ids) == len(ledger)
    summary = read(ROOT/'records/progress-summary.json')
    details = read(ROOT/'records/corrected-task-index.json')
    selection = read(ROOT/'records/code-result-selection.json')['replacements']
    mechanical = read(ROOT/'records/mechanical-audit.json')
    expected_errors = {(r['parent_run_id'], r['index'], 'repository-switch notice matches actual schedule stage') for r in selection}
    errors = {(s['run_id'], e['index'], e['check']) for s in mechanical['streams'] for e in s['errors']}
    assert errors == expected_errors, 'Unexpected mechanical audit error or changed historical record'
    selected_ids = {i for r in details for i in r['attempt_ids']}
    assert sum(len(r['attempt_ids']) for r in details) == len(selected_ids)
    assert len(details) == 353 and len(summary['streams']) == 12
    assert sum(s['user_skipped_unscored'] for s in summary['streams']) == 1
    replacements = []; superseded_ids = set()
    for r in selection:
        parent = ROOT/'private-runs'/r['parent_run_id']
        directory = ROOT/'private-runs'/r['rerun_run_id']
        row, = read(directory/'results.json')
        assert row['index'] == r['index']
        out = directory/f"task-{r['index']:03d}"
        old = parent/out.name
        episode = read(out/'legal-episode.json'); barrier = read(out/'barrier.json')
        assert not episode['prompt'].startswith('NOTICE: We are now coding in a new repo.')
        assert episode['prompt'] == read(old/'legal-episode.json')['prompt'].removeprefix('NOTICE: We are now coding in a new repo.\n\n')
        assert read(out/'memory-before.json') == read(old/'memory-before.json')
        assert barrier['durable'] and barrier['source_watermark'] == digest(episode) == row['source_watermark']
        grade = read(directory/'evaluator-private'/f"result-{r['index']:03d}.json")['record']
        assert row['correct'] == grade['success'] and row['actions'] == grade['steps']
        prior = next(x for x in read(parent/'results.json') if x['index'] == r['index'])
        assert prior['session_id'] != row['session_id']
        superseded_ids.update(c['attempt_id'] for c in prior['attempts'])
        receipt = read(ROOT/r['audit']); assert receipt['status'] == 'passed'
        replacements.append({'run_id': r['rerun_run_id'], 'index': row['index'], 'barrier_sha256': sha(out/'barrier.json'), 'correct': row['correct']})
    native = []; skipped_ids = set()
    for stream in summary['streams']:
        directory = ROOT/'private-runs'/stream['run_id']
        boundary = read(directory/'boundary.json')
        rows = read(directory/'results.json')
        assert boundary['pending'] is None and boundary['next_index'] == stream['target']
        assert len(rows) + len(boundary.get('user_skips', [])) == stream['target']
        for skip in boundary.get('user_skips', []):
            assert skip['status'] == 'user_interrupted_unscored' and skip['correct'] is None and skip['reward'] is None
            assert skip['index'] not in {r['index'] for r in rows}
            skipped_ids.update(c['attempt_id'] for c in ledger if c['run_id'] == stream['run_id'] and c['task'] == f"task-{skip['index']:03d}")
        if stream['method'].startswith('pi_'):
            continue
        framework = stream['method'].removesuffix('_memory_ready')
        records = []
        for row in rows:
            out = directory/f"task-{row['index']:03d}"
            recovered = row.get('recovered_maintenance') or row.get('recovered_solver')
            snapshot = out/('recovered-native-state.tar.gz' if recovered else 'native-state.tar.gz')
            files = archive(snapshot)
            evidence = validate(files, out.name, framework, row['session_id'])
            assert memory_snapshot(files, framework) == read(out/'memory-after.json')
            accounting = validate_attempt_accounting(out, row['attempts'])
            records.append({'index': row['index'], 'kind': evidence['kind'], 'snapshot_sha256': sha(snapshot),
                            'attempts': accounting['attempts'], 'unknown_usage_attempts': len(accounting['failed_attempts_with_unknown_usage'])})
        native.append({'run_id': stream['run_id'], 'verified_tasks': len(records), 'records': records})
        print(json.dumps({'native_run_verified': stream['run_id'], 'tasks': len(records)}), flush=True)
    assert not (selected_ids & superseded_ids or selected_ids & skipped_ids or superseded_ids & skipped_ids)
    assert selected_ids | superseded_ids | skipped_ids <= ids
    groups = defaultdict(list)
    for call in ledger:
        ident = call['attempt_id']
        category = ('selected_scored_tasks' if ident in selected_ids else
                    'superseded_original_tasks' if ident in superseded_ids else
                    'user_interrupted_unscored_task' if ident in skipped_ids else
                    'acceptance_or_debug' if call['category'] == 'acceptance_or_debug' else 'unassigned')
        groups[category].append(call)
    assert not groups['unassigned'], 'Physical attempts missing a cost category'
    assert sum(len(v) for v in groups.values()) == len(ledger)
    # The discarded v1 canaries were killed by the erroneous 60-second deadline
    # before they could log a terminal event. Preserve that uncertainty; do not
    # turn their old "started" entries into fictional settled responses.
    started = [c for c in ledger if c['phase'] == 'started']
    incident = read(ROOT/'records/timeout-incident.json')
    truncated = {(c['run_id'], f"task-{c['index']:03d}") for c in incident['truncated_cases']}
    assert {(c['run_id'], c['task']) for c in started} == truncated
    assert all(c['category'] == 'acceptance_or_debug' and c['total_tokens'] is None for c in started)
    from native_gateway import gate
    live_gate = gate('status', {})
    assert live_gate['active'] == 0, 'Current shared gate has an active request'
    events = [json.loads(line) for line in (ROOT/'.local/request-gate-events.jsonl').read_text(encoding='utf8').splitlines() if line]
    acquisitions = [e for e in events if e['event'] == 'acquire']
    released = {e['lease'] for e in events if e['event'] == 'release'}
    assert not [e for e in acquisitions if e['lease'] not in released]
    gate_ids = {e.get('attempt_id') for e in acquisitions}
    assert all(c['attempt_id'] in gate_ids for c in ledger if c['category'] != 'acceptance_or_debug')
    report = {
        'as_of': datetime.now(timezone.utc).isoformat(), 'status': 'passed_with_disclosed_historical_deviations',
        'model_calls': 0, 'scored_tasks': len(details), 'user_interrupted_unscored': 1,
        'full_scored_streams': 11, 'streams_completed_with_user_skip': 1,
        'expected_original_mechanical_errors': len(errors), 'unexpected_mechanical_errors': 0,
        'replacement_results_verified': replacements, 'native_streams': native,
        'selected_output_budgets': dict(Counter(r['configured_initial_output_limit'] for r in details)),
        'physical_attempt_phases': dict(Counter(c['phase'] for c in ledger)), 'live_gate': live_gate,
        'current_formal_inflight_attempts': [],
        'historical_interrupted_attempts_without_terminal_log': [{k: c[k] for k in ['attempt_id','run_id','task','phase']} for c in started],
        'gate_observation': {'acquisitions': len(acquisitions), 'all_leases_released': True,
            'formal_and_rerun_attempts_without_receipt': 0,
            'early_acceptance_attempts_without_receipt': sum(c['attempt_id'] not in gate_ids for c in ledger),
            'maximum_wait_seconds': max(e['wait_seconds'] for e in acquisitions)},
        'all_campaign_attempts': aggregate(ledger),
        'cost_partition': {k: aggregate(v) for k, v in groups.items() if v},
        'selected_stream_costs': {s['run_id']: aggregate([c for c in ledger if c['attempt_id'] in selected_ids and any(r['run_id'] == s['run_id'] and c['attempt_id'] in r['attempt_ids'] for r in details)]) for s in summary['streams']},
        'limitations': [
            '353 scored tasks plus one user-interrupted unscored task; no imputed zero.',
            'All original attempts retained; corrected selection uses all three authorized reruns including the worse result.',
            'Known tokens omit missing usage; cached input is part of input, not an additional token category.',
            'Prices use the recorded 2026-10-04 public price snapshot, not verified account debits.',
            'Mixed output budgets, mixed Codex consolidation cadence, R=1, and different complete systems prevent a causal memory ranking.',
            'Historical capability/debug failures are retained; final scored native tasks alone must satisfy completion checks.',
            'Two discarded 60-second v1 canaries lack terminal request logs; usage remains unknown and raw phase is not rewritten.',
        ],
    }
    save(ROOT/'records/final-closure-audit.json', report)
    print(json.dumps({k: report[k] for k in ['status','scored_tasks','user_interrupted_unscored','all_campaign_attempts','cost_partition']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
