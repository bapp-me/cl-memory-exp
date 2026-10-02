"""Descriptive native-memory health; no semantic or causal judgment."""
import ast
from collections import Counter
import json
from pathlib import Path
import re
from engine import ROOT, read, save, digest


def main():
    utility = ROOT / '.runtime/complex-libs/mem0/memory/utils.py'
    tree = ast.parse(utility.read_text(encoding='utf-8'))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'remove_code_blocks')
    namespace = {'re': re}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(utility), 'exec'), namespace)
    strip_blocks = namespace['remove_code_blocks']
    records = []
    for run in sorted((ROOT / '.runtime/runs').glob('section7-full-v3-codeeval-*')):
        method = run.name.rsplit('codeeval-', 1)[1]
        for folder in sorted(run.glob('[0-9][0-9][0-9]')):
            if not (folder / 'commit.json').exists():
                continue
            before, after = read(folder / 'memory-before.json'), read(folder / 'memory-after.json')
            result = read(folder / 'commit.json')['result']
            events = [json.loads(line) for line in (folder / 'controller-events.jsonl').read_text(encoding='utf-8').splitlines()]
            retrieval = read(folder / 'retrieval.json')
            row = {'method': method, 'task_id': result['task_id'], 'state_hash_changed': digest(before) != digest(after),
                   'terminal_state': result['terminal_state'],
                   'injected_utf8_bytes': retrieval['injected_utf8_bytes'],
                   'observable_candidate_count': len(retrieval['observable_candidates']),
                   'injected_entry_count': len(retrieval['injected_ids']),
                   'packing_dropped_entries': len(retrieval['dropped']),
                   'auxiliary_budget_exhausted': [event for event in events if event['event'] == 'auxiliary_budget_exhausted'],
                   'role_accounting': result.get('role_accounting'), 'semantic_memory_quality': None,
                   'semantic_unknown_reason': 'No semantic review or counterfactual performed'}
            if method == 'mem0':
                row.update(before_entries=len(before['points']), after_entries=len(after['points']))
                extraction = next(iter(sorted(folder.glob('auxiliary/*-writer/aux-result.json'))), None)
                if extraction:
                    text = read(extraction)['text']
                    try:
                        facts = json.loads(strip_blocks(text))['facts']
                        row.update(extraction_json_valid=True, extracted_facts=len(facts), extraction_rejected_reason=None)
                    except Exception as error:
                        row.update(extraction_json_valid=False, extracted_facts=None,
                                   extraction_rejected_reason=type(error).__name__ + ': ' + str(error))
                journal = read(folder / 'native-operations.json')
                row['native_operations'] = dict(Counter(op['type'] for op in journal['operations']))
                row['no_learned_point_mutation'] = before['points'] == after['points']
            elif method == 'awm':
                row.update(before_library_utf8_bytes=len(before['workflow_text'].encode()),
                           after_library_utf8_bytes=len(after['workflow_text'].encode()),
                           workflow_library_changed=before['workflow_text'] != after['workflow_text'])
                row['raw_episode_history_count'] = len(after['episodes'])
                row['native_operations'] = dict(Counter(op['type'] for op in read(folder / 'native-operations.json')['operations']))
            elif method == 'ace':
                row.update(before_bullets=sum(line.startswith('[') for line in before['playbook'].splitlines()),
                           after_bullets=sum(line.startswith('[') for line in after['playbook'].splitlines()))
                journal = folder / 'native-operations.json'
                row['native_operations'] = dict(Counter(op['type'] for op in read(journal)['operations'])) if journal.exists() else None
                row['native_operation_observation'] = 'observed' if journal.exists() else 'not produced before memory exception'
                row['curator_rejection_records'] = [event.get('reason') for event in events if event['event'] == 'native_curator_reject']
            else:
                row.update(before_entries=len(before), after_entries=len(after))
            records.append(row)
    summary = []
    for method in sorted({row['method'] for row in records}):
        selected = [row for row in records if row['method'] == method]
        summary.append({'method': method, 'tasks_observed': len(selected),
                        'terminal_states': dict(Counter(row['terminal_state'] for row in selected)),
                        'auxiliary_budget_exhausted_tasks': sum(bool(row['auxiliary_budget_exhausted']) for row in selected),
                        'budget_exhaustion_roles': dict(Counter(event['role'] for row in selected for event in row['auxiliary_budget_exhausted'])),
                        'injection_packing_dropped_tasks': sum(row['packing_dropped_entries'] > 0 for row in selected),
                        'mem0_extraction_json_rejected': sum(row.get('extraction_json_valid') is False for row in selected),
                        'native_empty_fact_extractions': sum(row.get('extraction_json_valid') is True and row.get('extracted_facts') == 0 for row in selected),
                        'ace_curator_rejections': sum(len(row.get('curator_rejection_records', [])) for row in selected)})
    report = {'phase': '7.1', 'status': 'descriptive_completed_prefix' if len(records) < 384 else 'complete',
              'model_calls': 0, 'summary': summary, 'records': records,
              'limits': ['State/bookkeeping change is distinct from learned content change.',
                         'Native JSON rejection and NOOP are reported rather than replaced by an extra model retry.',
                         'No diagnosis of abstraction fidelity, usefulness or causal transfer is claimed.']}
    save(ROOT / 'records/memory-health.json', report)
    print(json.dumps({key: value for key, value in report.items() if key != 'records'}))


if __name__ == '__main__':
    main()
