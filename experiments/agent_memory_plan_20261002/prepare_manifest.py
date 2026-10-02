"""Pre-register metadata-only task selection before any observed model result.

The source JSON contains solutions/tests; parse only IDs and relation metadata,
never render or export source solutions into the agent view.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
REVISION = 'a01e2ca6e33fd07d9cf80e4bd69a5b3585d3400f'
URL = f'https://huggingface.co/datasets/osunlp/AgentCL/resolve/{REVISION}/codeeval-pro/bigcodebench_lite_pro.dependent.json'

def spaced(items, count):
    if len(items) < count or count < 2:
        raise ValueError('Selection requires enough items and at least two positions')
    return [items[round(i * (len(items) - 1) / (count - 1))] for i in range(count)]

def main():
    raw = urlopen(URL, timeout=45).read()
    rows = json.loads(raw)
    sources = [r for r in rows if r['category'] == 'raw']
    targets = [r for r in rows if r['category'] == 'new']
    assert len(rows) == 96 and len(sources) == len(targets) == 48
    selected = spaced(targets, 12)
    ids = {r['id'] for r in selected}
    stream = [{'source_index': i, 'category': r['category'], 'id': r['id']}
              for i, r in enumerate(rows) if r['id'] in ids]
    assert len(stream) == 24
    for target in selected:
        pair = [r for r in rows if r['id'] == target['id']]
        assert {r['category'] for r in pair} == {'raw', 'new'}
        assert target['corresponding_raw_id'] == target['id']
        assert next(r for r in pair if r['category'] == 'raw')['corresponding_new_id'] == target['id']
    manifest = {
        'status': 'task_selection_preregistered_runtime_not_ready',
        'registered_at': datetime.now(timezone.utc).isoformat(),
        'source_url': URL, 'revision': REVISION,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'selection_rule': '12 evenly spaced complex tasks in original stream; include paired sources; preserve original relative order',
        'ordered_task_ids': stream,
        'diagnostic_targets': [{'category': 'new', 'id': r['id']} for r in spaced(selected, 8)],
        'methods': ['no_memory', 'bounded_icl', 'episodic_retrieval'],
        'repetitions': 1, 'first_pass_only': True,
        'pilot_task_executions': 72, 'diagnostic_execution_upper_bound': 24,
        'agent_visible_fields': ['problem'],
        'researcher_only_fields': ['id', 'category', 'corresponding_new_id', 'corresponding_raw_id'],
        'evaluator_only_fields': ['solution', 'test_code'],
        'model_config': None, 'budget_config': None, 'sandbox': None,
        'execution_frozen_at': None,
    }
    path = ROOT / 'records/agentcl-selection.json'
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        old = json.loads(path.read_text(encoding='utf-8'))
        for field in ['source_sha256', 'ordered_task_ids', 'diagnostic_targets']:
            if old[field] != manifest[field]:
                raise RuntimeError('Existing registration differs; append an explicit revision instead')
        print('Existing selection matches; not replacing registration timestamp.')
        return
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    access = {
        'record_id': 'agentcl-codeeval-selection-001', 'benchmark': 'AgentCL',
        'revision': REVISION, 'purpose': 'dev_selection', 'accessed_at': manifest['registered_at'],
        'information_viewed': ['schema_field_names', 'ids', 'categories', 'dependency_links', 'original_order'],
        'machine_processed': 'Entire source JSON downloaded into process memory; includes hidden solutions/tests. Their contents were not printed, inspected, or exported.',
        'used_to_change_method': False,
        'subsequent_allowed_use': 'development; not held-out validation or final test',
    }
    (ROOT / 'records/data-access.jsonl').write_text(json.dumps(access, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'selected_tasks': len(stream), 'diagnostic_targets': 8, 'model_calls': 0}))

if __name__ == '__main__':
    main()
