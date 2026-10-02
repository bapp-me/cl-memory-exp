"""Recompute quality and separate cost metrics without new model calls."""
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from environment import grade
from plan_jobs import GROUPS, aid, wid

ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def analyze():
    rows = []
    for path in sorted((ROOT / 'results/runs').glob('*/summary.json')):
        s = load(path)
        # Recompute ledger usage so missing-usage failures remain explicit.
        from run_task import usage
        s['usage'] = usage(path.parent)
        if not s.get('writer_from') and not s.get('repair_from'):
            s['original_quality'] = s['quality']
            s['quality'] = grade(s.get('final_response', ''), load(ROOT / 'checks' / s['group'] / f'{s["stage"]}.json'), load(path.parent / 'state-after.json'))
        s['grader_version'] = 2
        u = s['usage']
        if s['provider'] == 'deepseek':
            peak = (u.get('input_tokens', 0) * .3 + u.get('cache_read_input_tokens', 0) * .006 + u.get('cache_creation_input_tokens', 0) * .3 + u.get('output_tokens', 0) * 1.2) / 1e6
            s['usd_estimate_range'] = [peak / 2, peak]
        else:
            s['usd_estimate_range'] = None
        tools = [json.loads(x) for x in (path.parent / 'tools.jsonl').read_text(encoding='utf-8').splitlines()] if (path.parent / 'tools.jsonl').exists() else []
        s['task_tool_errors'] = sum(x['error'] for x in tools if x['tool'] != 'experience')
        s['memory_tool_errors'] = sum(x['error'] for x in tools if x['tool'] == 'experience')
        before = load(path.parent / 'memory_before/entries.json')
        read_calls = [x for x in tools if x['tool'] == 'experience' and x['args']['op'] in ('get', 'search')]
        s['read_evidence'] = {'auto_loaded': s['memory'] == 'file' and bool(before),
                              'ensured_injection': s.get('ensure_read', False) and bool(before),
                              'search_or_get_calls': len(read_calls),
                              'returned_nonempty': any(x['result'].get('matches') or x['result'].get('content') for x in read_calls),
                              'first_read_step': min((x['step'] for x in read_calls), default=None),
                              'last_task_step': max((x['step'] for x in tools if x['tool'] != 'experience'), default=None),
                              'read_only_after_task_actions': bool(read_calls) and min(x['step'] for x in read_calls) > max((x['step'] for x in tools if x['tool'] != 'experience'), default=0),
                              'action_dependency': 'requires trace review; visibility alone is insufficient'}
        rows.append(s)
    byid = {s['run_id']: s for s in rows}
    comparisons = []
    for group in GROUPS:
        row = {'group': group, 'stages': {}}
        for stage in 'bc':
            none = byid.get(f'main-pi-{group[:2]}-{stage}-none')
            if not none:
                continue
            conditions = {}
            for condition in ('file', 'guided', 'caution', 'search'):
                mem = byid.get(f'main-pi-{group[:2]}-{stage}-{condition}')
                if not mem:
                    continue
                conditions[condition] = {'none_run': none['run_id'], 'memory_run': mem['run_id'],
                    'quality_comparable': none['quality']['success'] and mem['quality']['success'] and not none['error'] and not mem['error'],
                    'none_success': none['quality']['success'], 'memory_success': mem['quality']['success'],
                    'delta_task_tools': mem['task_tools'] - none['task_tools'],
                    'delta_all_tools': sum(mem['tools'].values()) - sum(none['tools'].values()),
                    'delta_tool_errors': mem['tool_errors'] - none['tool_errors'],
                    'delta_task_errors': mem['task_tool_errors'] - none['task_tool_errors'],
                    'delta_memory_errors': mem['memory_tool_errors'] - none['memory_tool_errors'],
                    'delta_input_tokens': mem['usage'].get('all_input_tokens', 0) - none['usage'].get('all_input_tokens', 0),
                    'delta_output_tokens': mem['usage'].get('output_tokens', 0) - none['usage'].get('output_tokens', 0),
                    'delta_seconds': round(mem['seconds'] - none['seconds'], 3)}
            row['stages'][stage] = conditions
        if row['stages']:
            comparisons.append(row)
    totals = defaultdict(Counter)
    for s in rows:
        totals[s['provider']].update(s['usage'])
        totals[s['provider']]['runs'] += 1
        totals[s['provider']]['errors'] += bool(s['error'])
    compact = {}
    for stage in 'bc':
        compact[stage] = {}
        for condition in ('file', 'guided', 'caution', 'search'):
            pairs = [r['stages'][stage][condition] for r in comparisons if stage in r['stages'] and condition in r['stages'][stage]]
            matched = [r for r in pairs if r['quality_comparable']]
            vals = [r['delta_task_tools'] for r in matched]
            if pairs:
                compact[stage][condition] = {'pairs': len(pairs), 'quality_comparable': len(matched),
                    'fewer_equal_more': [sum(x < 0 for x in vals), sum(x == 0 for x in vals), sum(x > 0 for x in vals)],
                    'mean_task_delta': mean(vals) if vals else None, 'median_task_delta': median(vals) if vals else None}
    result = {'rows': rows, 'comparisons': comparisons, 'totals': {k: dict(v) for k, v in totals.items()}, 'compact': compact,
              'price_basis': {'source': 'https://api-docs.deepseek.com/quick_start/pricing', 'retrieved': '2026-10-02', 'deepseek_peak_per_million': {'uncached': .3, 'cached': .006, 'output': 1.2}, 'off_peak_multiplier': .5, 'billing_not_verified': True, 'glm_price': None},
              'quality_corrections': [{'run_id': r['run_id'], 'original': r['original_quality'], 'corrected': r['quality']} for r in rows if 'original_quality' in r and r['original_quality'] != r['quality']]}
    (ROOT / 'results/scoreboard.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'runs': len(rows), 'compact': compact, 'totals': result['totals'], 'quality_corrections': result['quality_corrections']}, ensure_ascii=False))
    return result


if __name__ == '__main__':
    analyze()
