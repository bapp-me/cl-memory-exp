"""Manually adjudicated narrow repair-opportunity set, tied to actual c traces.

No lexical heuristic is used as a claim of recognition. Unknown stays unknown.
The groups were chosen for follow-up after first observations; rates are descriptive.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANNOTATIONS = [
    ('main-pi-04-c-file', True, 'Compared cursor contract with prior page experience; added v2 entry.'),
    ('main-pi-05-c-file', True, 'Added a version-aware rule contrasting prior PATCH with observed PUT replacement.'),
    ('main-pi-08-c-file', True, 'Explicitly attributed default assumption to old experience; corrected encoding then delimiter.'),
    ('repeat2-pi-04-c-file', None, 'Current docs used correctly, but no explicit link to problematic memory observed.'),
    ('repeat3-pi-04-c-file', True, 'Explicitly stated docs differ from prior experience; no persistent write.'),
    ('repeat2-pi-08-c-file', None, 'Parsed current export correctly; no explicit recognition of old memory problem.'),
    ('repeat3-pi-08-c-file', True, 'Replaced old default-specific entry with do-not-assume-defaults and exact current-parameter rule.'),
    ('cross-hermes-04-c-file', True, 'Explicitly compared docs with experience and changed to cursor; no write.'),
    ('repeat2-hermes-04-c-file', None, 'Called this a different variant; link to remembered rule is not explicit enough for strict denominator.'),
    ('repeat3-hermes-04-c-file', True, 'Explicitly compared v2 with experience and proposed/persisted v2 update.'),
    ('cross-hermes-08-c-file', None, 'Recognized current decode error and corrected parsing, but did not explicitly connect it to memory scope. Broad opportunity possible; strict denominator excludes.'),
    ('repeat2-hermes-08-c-file', None, 'Current parameters used correctly; no explicit memory mismatch recognition.'),
    ('repeat3-hermes-08-c-file', True, 'Explicitly stated parameters differ from experience; no persistent write.'),
]


def main():
    rows = []
    for rid, recognized, evidence in ANNOTATIONS:
        directory = ROOT / 'results/runs' / rid
        if not (directory / 'summary.json').exists():
            continue
        s = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
        calls = [json.loads(x) for x in (directory / 'tools.jsonl').read_text(encoding='utf-8').splitlines()]
        attempts = [c for c in calls if c['tool'] == 'experience' and c['args']['op'] in ('put', 'delete')]
        errors = [c for c in calls if c['tool'] != 'experience' and c['error']]
        rows.append({'run_id': rid, 'memory_visible': True, 'explicit_memory_scope_recognition': recognized,
                     'current_action_corrected_or_adapted': s['quality']['success'],
                     'proposed_or_attempted_persistent_update': bool(attempts), 'persisted_store_change': s['memory_changed'],
                     'tool_error_steps': [c['step'] for c in errors], 'evidence': evidence,
                     'source': f'results/runs/{rid}/agent-result.json',
                     'repair_semantics_not_implied_by_write': True})
    known = [r for r in rows if r['explicit_memory_scope_recognition'] is True]
    output = {'selection': 'Main 04/05/08 plus two consumer repeats for 04/08 on pi and Hermes. Post-observation diagnostic set, not population sampling.',
              'recognition_rule': 'Explicit comparison of historical memory with current evidence, or an actual targeted rewrite of the obsolete rule. Merely answering correctly, seeing metadata or encountering a tool error is insufficient.',
              'rows': rows, 'observed_recognition': len(known), 'total_audited_c_runs': len(rows),
              'recognition_unknown': sum(r['explicit_memory_scope_recognition'] is None for r in rows),
              'persistent_updates_among_known_opportunities': sum(r['persisted_store_change'] for r in known),
              'denominator': len(known), 'interpretation': 'An observed lower bound on recognition in this selected set; persistence is not complete semantic repair.'}
    (ROOT / 'results/repair-opportunity-audit.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in output.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
