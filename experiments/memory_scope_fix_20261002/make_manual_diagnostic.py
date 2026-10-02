"""Human scoped-memory diagnostic, explicitly separate from real writer output.

Uses only observed a metadata and tool interfaces; no c/d values or answers.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENTS = {
    '04_pagination': 'Observed service ledger version 1 only. For that version GET /items uses page (1-based), limit<=3 and next_page; follow next_page until null and aggregate active items. At a later task first read api.json and GET /info. Apply the page procedure only when the current documented pagination contract matches; otherwise use the currently documented contract. The source observed 8 items, which is not a constant for future ledgers.',
    '05_update': 'Observed profiles API version 1 only. Its PATCH /profile changes supplied fields and retains omitted fields; PUT unsupported in that observed version. For this version GET, PATCH changed fields, then GET to verify. Re-read api.json on each task and select the currently documented method and preservation semantics. Do not generalize omission-preserves-fields to other update methods or versions. Preserve the current resource values when the task requires it.',
    '08_csv': 'Observed one ledger export: encoding utf-8, delimiter comma, preamble_lines 0; columns category and amount. Those parser settings describe that export only. For each new file read export.json and pass its encoding, delimiter and preamble_lines (as skip_lines) explicitly to parse_csv; verify column names in returned rows, then sum numeric amount where category is sales. Never reuse a prior numeric answer.',
}
jobs = []
for group, content in CONTENTS.items():
    path = ROOT / 'fixtures/diagnostic' / f'{group}.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'human-scoped-diagnostic': {'title': 'Manually scoped a experience (diagnostic only)', 'content': content, 'version': 1}}, indent=2) + '\n', encoding='utf-8')
    for stage in 'bc':
        jobs.append({'run_id': f'manual-pi-{group[:2]}-{stage}', 'group': group, 'stage': stage, 'memory_seed': str(path.relative_to(ROOT))})
(ROOT / 'jobs/manual.json').write_text(json.dumps(jobs, indent=2) + '\n', encoding='utf-8')
print('Created 3 human memory diagnostic seeds and 6 jobs; not natural writer evidence.')
