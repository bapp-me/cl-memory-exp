"""Offline paired efficiency analysis. Never edits a run or invokes a model."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from statistics import median
from prepare import ROOT, read, save, sha


FIELDS = ['input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens', 'total_tokens']


def aggregate(rows):
    calls = [c for r in rows for c in r['calls']]
    result = {'tasks': len(rows), 'correct': sum(r['correct'] for r in rows),
              'actions': sum(r['actions'] for r in rows),
              'reward_sum': round(sum(r['reward'] for r in rows), 6), 'attempts': len(calls)}
    result['reward_mean'] = result['reward_sum'] / len(rows) if rows else None
    for field in FIELDS:
        result[field + '_known'] = sum(c.get(field) or 0 for c in calls)
        result[field + '_unknown_attempts'] = sum(c.get(field) is None for c in calls)
    result['price_equivalent_known_usd'] = round(sum(c.get('published_price_estimate_usd') or 0 for c in calls), 6)
    result['price_equivalent_unknown_attempts'] = sum(c.get('published_price_estimate_usd') is None for c in calls)
    for field in ['seconds', 'maintenance_seconds']:
        values = [r[field] for r in rows if r[field] is not None]
        result[field + '_known_sum'] = round(sum(values), 3)
        result[field + '_median'] = round(median(values), 3) if values else None
        result[field + '_unknown_tasks'] = len(rows) - len(values)
    result['role_attempts'] = dict(Counter(c['role'] for c in calls))
    result['role_total_tokens_known'] = {
        role: sum(c.get('total_tokens') or 0 for c in calls if c['role'] == role)
        for role in result['role_attempts']}
    result['maximum_explicit_memory_bytes_before'] = max((r['explicit_memory_bytes_before'] or 0 for r in rows), default=0)
    result['maximum_selected_episode_bytes'] = max((r['selected_episode_bytes'] for r in rows), default=0)
    result['compaction_events'] = sum(r['compaction_events'] for r in rows)
    return result


def compare(baseline, target):
    assert [(r['index'], r['instance_id']) for r in baseline] == [(r['index'], r['instance_id']) for r in target]
    matrix = Counter(('correct' if b['correct'] else 'wrong', 'correct' if t['correct'] else 'wrong')
                     for b, t in zip(baseline, target))
    groups = {}
    for name, pairs in [
        ('all_tasks', list(zip(baseline, target))),
        ('both_correct', [(b, t) for b, t in zip(baseline, target) if b['correct'] and t['correct']]),
    ]:
        b, t = [list(x) for x in zip(*pairs)] if pairs else ([], [])
        bs, ts = aggregate(b), aggregate(t)
        metrics = ['actions', 'total_tokens_known', 'input_tokens_known', 'output_tokens_known', 'price_equivalent_known_usd']
        groups[name] = {'tasks': len(pairs), 'indices': [x['index'] for x in b], 'baseline': bs, 'target': ts,
                        'delta_target_minus_baseline': {k: round(ts[k] - bs[k], 6) for k in metrics},
                        'relative_delta': {k: ts[k] / bs[k] - 1 if bs[k] else None for k in metrics}}
        complete_usage = [(x, y) for x, y in pairs if all(c['total_tokens'] is not None for r in [x, y] for c in r['calls'])]
        groups[name]['complete_usage_pairs'] = {'tasks': len(complete_usage),
            'indices': [x['index'] for x, _ in complete_usage],
            'token_delta': sum(sum(c['total_tokens'] for c in y['calls']) - sum(c['total_tokens'] for c in x['calls']) for x, y in complete_usage)}
        known_time = [(x, y) for x, y in pairs if x['seconds'] is not None and y['seconds'] is not None]
        groups[name]['complete_time_pairs'] = {'tasks': len(known_time),
            'delta_seconds': round(sum(y['seconds'] - x['seconds'] for x, y in known_time), 3),
            'interpretation': 'Concurrent observed task durations, not causal speedup or total campaign wall time.'}
    return {'correctness_pairs_baseline_target': {f'{a}/{b}': matrix[(a, b)] for a in ['correct', 'wrong'] for b in ['correct', 'wrong']},
            'groups': groups}


def main():
    ledger = {x['attempt_id']: x for x in read(ROOT / 'records/attempt-ledger.json')}
    summary = read(ROOT / 'records/progress-summary.json')
    streams, details, rows_by_run = [], [], {}
    for stream in summary['streams']:
        directory = ROOT / 'private-runs' / stream['run_id']
        raw = read(directory / 'results.json')
        # Restrict to the summary snapshot if a live controller has since appended a row.
        raw = raw[:stream['completed']]
        rows = []
        for result in raw:
            out = directory / f"task-{result['index']:03d}"
            calls = [ledger[c['attempt_id']] for c in result['attempts']]
            cfg, memory = read(out / 'input.json'), read(out / 'memory-before.json')
            selected = cfg.get('sources', [])
            explicit = len(memory.get('notepad', '').encode('utf-8')) if stream['method'].startswith('pi_') else None
            if stream['method'] == 'pi_jaccard':
                explicit = len(json.dumps(memory['history'], ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            row = {k: result[k] for k in ['index', 'instance_id', 'session_id', 'project_key', 'correct', 'actions', 'reward']}
            row.update({'run_id': stream['run_id'], 'method': stream['method'], 'environment': stream['environment'],
                        'seconds': result.get('seconds') if not result.get('seconds_basis') else None,
                        'maintenance_seconds': result.get('maintenance_seconds'), 'calls': calls,
                        'explicit_memory_bytes_before': explicit,
                        'selected_episode_bytes': sum(len(json.dumps(s['episode'], ensure_ascii=False, separators=(',', ':')).encode('utf-8')) for s in selected),
                        'selected_past_indices': [s['episode']['index'] for s in selected],
                        'compaction_events': 0, 'barrier_sha256': sha(out / 'barrier.json')})
            events = out / 'events.jsonl'
            if events.exists():
                row['compaction_events'] = sum('"type":"auto_compaction_start"' in line.replace(' ', '') for line in events.read_text(encoding='utf-8').splitlines())
            rows.append(row)
            public = {k: v for k, v in row.items() if k != 'calls'}
            public['attempt_ids'] = [c['attempt_id'] for c in calls]
            public['usage'] = aggregate([row])
            details.append(public)
        rows_by_run[stream['run_id']] = rows
        phases = defaultdict(list)
        for row in rows:
            phase = ('before_migration' if row['index'] < 20 else 'after_migration') if stream['environment'] == 'database_exploration' else row['project_key']
            phases[phase].append(row)
        streams.append({'run_id': stream['run_id'], 'method': stream['method'], 'environment': stream['environment'],
                        'status': stream['status'], 'target': stream['target'], 'stats': aggregate(rows),
                        'phases': {k: aggregate(v) for k, v in phases.items()}})
    paired = []
    for target in streams:
        if target['status'] != 'completed' or target['method'] == 'pi_none': continue
        baseline = next(s for s in streams if s['method'] == 'pi_none' and s['environment'] == target['environment'])
        paired.append({'baseline': baseline['run_id'], 'target': target['run_id'], 'method': target['method'],
                       'environment': target['environment'], **compare(rows_by_run[baseline['run_id']], rows_by_run[target['run_id']])})
    output = {'as_of': summary['as_of'], 'generated_at': datetime.now(timezone.utc).isoformat(), 'model_calls': 0,
              'scope': 'Committed tasks only; incomplete native prefixes are not compared against full streams.',
              'streams': streams, 'paired': paired,
              'limitations': ['Both-correct subsets condition on observed outcomes; no causal efficiency claim.',
                 'R=1 complete-system comparison, no per-framework stateless controls or significance claim.',
                 'Known token differences with an unknown-usage attempt are differences of partial sums, not exact savings.',
                 'Local cold memory does not imply cold provider prompt cache.',
                 'Jaccard selected bytes measure full episode payloads before wrapping; they are not tokens or unique facts.',
                 'Explicit memory bytes exclude native homes, raw session stores and audit files; no cross-framework size ranking.',
                 'Native role labels combine solving and maintenance; per-role causality is not observed.',
                 'Pi has no separate asynchronous maintenance_seconds field; unknown is not zero.']}
    save(ROOT / 'records/efficiency-analysis.json', output)
    save(ROOT / 'records/task-index.json', details)
    print(json.dumps({'committed_tasks': len(details), 'completed_streams': sum(s['status'] == 'completed' for s in streams),
                      'paired_comparisons': len(paired)}))


if __name__ == '__main__': main()
