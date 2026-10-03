"""Offline consistency and source-integrity checks for the 7.4.1/7.4.2 decision."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def read(name):
    return json.loads((ROOT / 'records' / name).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = read('source-audit.json')
    decision = read('base-system-decision.json')
    spike = read('interface-spike.json')
    proposal = read('canary-proposal.json')
    assert decision['selected_route'] == 'B'
    assert decision['hermes_revision'] == sources['hermes']['revision']
    assert not any(decision[x] for x in ['s0_accepted', 's0_frozen', 's1_started', 'canary_authorized'])
    assert all(x['model_calls'] == 0 for x in [sources, spike])
    assert decision['model_calls_this_phase'] == proposal['model_calls_executed'] == 0
    assert spike['passed'] and len(spike['checks']) == 6 and all(x['passed'] for x in spike['checks'])
    assert spike['script_sha256'] == digest(ROOT / 'interface_spike.py')
    assert all(x['event'] == 'subprocess.Popen' for x in spike['blocked_attempts'])
    estimate = decision['engineering_estimate']
    for route in ('A', 'B'):
        assert [sum(row[route][i] for row in estimate['work_packages']) for i in (0, 1)] == estimate[route + '_total']
    assert proposal['s0_tasks'] == len(proposal['code_ordered_tasks']) + len(proposal['babyai_ordered_task_ids'])
    assert proposal['task_ceiling'] == proposal['s0_tasks'] + proposal['conditional_N_J_tasks'] == 36
    prior = json.loads((REPO / proposal['source_manifest']).read_text(encoding='utf-8'))
    assert proposal['code_ordered_tasks'] == [x['task_id'] for x in prior['data']['code_ordered_tasks']]
    assert proposal['babyai_ordered_task_ids'] == prior['data']['babyai_ordered_task_ids']
    assert proposal['status'] == 'proposal_only_not_authorized_not_executable'
    for row in sources['existing_assets']:
        assert digest(REPO / row['path']) == row['sha256'], row['path']
    source_root = ROOT / '.cache/hermes-source'
    checked_upstream = 0
    if source_root.exists():
        for row in sources['source_files']:
            assert digest(source_root / row['path']) == row['sha256'], row['path']
            lines = (source_root / row['path']).read_text(encoding='utf-8-sig').splitlines()
            for symbol in row.get('symbols', []):
                assert symbol['name'] in lines[symbol['start'] - 1]
            checked_upstream += 1
    report = ROOT / 'S0接入审查与路线决定.md'
    local_links = []
    for link in re.findall(r'\]\(([^)]+)\)', report.read_text(encoding='utf-8')):
        if '://' not in link and not link.startswith('#'):
            assert (report.parent / link.split('#')[0]).resolve().exists(), link
            local_links.append(link)
    budget = proposal['limited_budget_proposal']
    for n, label in [(12, 'S0_12'), (36, '36')]:
        for dim in ['generations', 'http_attempts']:
            assert budget[f'all_roles_{dim}_{label}_ceiling'] == n * budget[f'all_roles_{dim}_per_task_ceiling']
    # New artifacts only: known credential shapes, not old unrelated research data.
    suspicious = []
    for path in [report, *ROOT.glob('*.py'), *ROOT.glob('records/*.json')]:
        text = path.read_text(encoding='utf-8')
        if re.search(r'(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{24,}|AKIA[A-Z0-9]{16})', text):
            suspicious.append(path.name)
    assert not suspicious, suspicious
    result = {'schema': 's0-decision-verification-v1', 'passed': True,
              'existing_assets_unchanged': len(sources['existing_assets']),
              'upstream_source_hashes_checked': checked_upstream,
              'upstream_check_status': 'checked' if checked_upstream else 'cache_absent_not_rechecked',
              'interface_groups_passed': 6, 'report_local_links_checked': len(local_links),
              'cost_work_package_sums_checked': True, 'canary_scope_and_budget_arithmetic_checked': True,
              'credential_pattern_scan_new_files': 'no_match',
              'credential_scan_limit': 'Pattern scan only; not a guarantee against all possible secrets',
              'model_calls': 0, 'sections_complete': ['7.4.1', '7.4.2'],
              'sections_not_complete': ['7.4.3', '7.4.4', '7.5']}
    (ROOT / 'records/verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
