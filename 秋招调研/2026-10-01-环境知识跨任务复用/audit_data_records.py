"""Recompute small public-data checks without importing benchmark code or models.

Run after audit_public_sources.py and audit_selected_files.py. Reads one bounded
JSONL record from the 1.2 GB trajectory object, not the full corpus or screenshots.
"""
import hashlib
import json
from collections import Counter
from urllib.request import Request, urlopen
from audit_public_sources import ROOT, CACHE


def main():
    inventory = json.loads((ROOT / '公开来源核查.json').read_text(encoding='utf-8'))
    datasets = {x['repo']: x for x in inventory['datasets']}
    questions = [json.loads(x) for x in (CACHE / 'hf/xiaowu0162/longmemeval-v2/questions.jsonl').read_text(encoding='utf-8').splitlines()]
    haystacks = json.loads((CACHE / 'hf/xiaowu0162/longmemeval-v2/haystacks/lme_v2_small.json').read_text(encoding='utf-8'))
    tasks = json.loads((CACHE / 'web-arena-x/webarena/config_files/test.raw.json').read_text(encoding='utf-8'))
    repo = 'xiaowu0162/longmemeval-v2'
    url = f"https://huggingface.co/datasets/{repo}/resolve/{datasets[repo]['revision']}/trajectories.jsonl"
    with urlopen(Request(url, headers={'User-Agent': 'environment-memory-research/1.0'}), timeout=40) as response:
        remote_bytes = response.headers.get('Content-Length')
        first = response.readline(8 * 1024 * 1024)
    if not first.endswith(b'\n'):
        raise ValueError('First record exceeds 8 MiB cap')
    trace = json.loads(first)
    (CACHE / 'lme_first_trajectory.json').write_bytes(first)
    result = {
        'model_calls': 0, 'environment_runs': 0,
        'lme_questions': {
            'count': len(questions),
            'domains': dict(Counter(x['domain'] for x in questions)),
            'types': dict(Counter(x['question_type'] for x in questions)),
            'small_haystack_size_distribution': dict(Counter(len(x) for x in haystacks.values())),
            'selected_question_ids': ['01307e07', '0d07143c', '18b91103', '05cce9b3', '0738c1ac'],
            'answers_independently_regraded': False,
        },
        'lme_first_trace': {
            'url': url, 'remote_content_length': int(remote_bytes) if remote_bytes else None,
            'bytes_read': len(first), 'sha256': hashlib.sha256(first).hexdigest(),
            'sampling_rule': 'First JSONL record, convenience inspection only; not a failure-rate estimate',
            'id': trace['id'], 'record_keys': list(trace), 'domain': trace['domain'],
            'environment': trace['environment'], 'outcome_label': trace['outcome'],
            'state_count': len(trace['states']),
            'non_null_action_count': sum(s.get('action') is not None for s in trace['states']),
            'tab_focus_action_count': sum(str(s.get('action', '')).startswith('tab_focus(') for s in trace['states']),
            'model_identifiable_from_record': False,
            'causal_memory_off_on_comparison': False,
        },
        'webarena': {
            'tasks': len(tasks), 'unique_template_ids': len({x['intent_template_id'] for x in tasks}),
            'site_combinations': dict(Counter('+'.join(x['sites']) for x in tasks)),
            'evaluator_type_counts_nonexclusive': dict(Counter(k for x in tasks for k in x['eval']['eval_types'])),
            'reference_answer_match_modes_nonexclusive': dict(Counter(k for x in tasks for k in (x['eval'].get('reference_answers') or {}))),
            'shopping_admin_match_modes_nonexclusive': dict(Counter(k for x in tasks if x['sites'] == ['shopping_admin'] for k in (x['eval'].get('reference_answers') or {}))),
            'selected_tasks': [{k: x[k] for k in ('task_id', 'intent_template_id', 'sites', 'intent')} for x in tasks if x['task_id'] in (0, 1, 11, 41)],
            'environment_installed': False,
        },
        'muse_released_memory_bytes': {name: (CACHE / 'KnowledgeXLab/MUSE/memory' / name).stat().st_size for name in ('procedural_memory.json', 'strategic_memory.json', 'tool_memory.json')},
        'limitations': [
            'Counts and source reading only, no downstream task-performance replication.',
            'LME public data card says 1870 trajectories; paper v1 says 1540. Full corpus not counted.',
            'LME screenshots not downloaded or visually inspected.',
            'MUSE empty files are this pinned repository snapshot, not evidence no other artifacts exist.',
        ],
    }
    (ROOT / '数据记录复算.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('lme_questions', 'lme_first_trace', 'muse_released_memory_bytes')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
