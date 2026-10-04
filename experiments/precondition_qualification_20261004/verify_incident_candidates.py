"""Offline checks for local Q1 drafts. No credentials, OS launch, or model calls.

Candidates are executed through a closed simulator/operation table. The verifier
examines their actual output; it never replaces candidate output with a reference.
These finite controlled fixtures are not evidence of natural failure frequency.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def credential_candidate(state, action):
    """Closed fake-account fixture, not a DPAPI implementation or security test."""
    account = action['account']
    if action['role'] == 'broker':
        return {'status': 'broker_started', 'account': account, 'credential_reads': 0}
    source = state['credential_source']
    if source == 'mock_dpapi':
        reads = 1
        if account != state['sealed_for']:
            return {'status': 'account_mismatch', 'account': account, 'credential_reads': reads}
        value = 'FAKE_VALUE_ONLY'
    elif source == 'mock_environment':
        reads = 0
        value = state['process_environment_value']
    else:
        raise ValueError('Unknown mock source')
    return {'status': 'model_ready', 'account': account, 'credential_reads': reads,
            'loaded_value': value}


def verify_credential(state, result):
    if not isinstance(result, dict):
        return False
    if result.get('account') not in state['permitted_accounts']:
        return False
    if state['task_role'] == 'broker':
        return result.get('status') == 'broker_started' and result.get('credential_reads') == 0
    if state['credential_source'] == 'mock_dpapi' and result.get('account') != state['sealed_for']:
        return False
    required_reads = 1 if state['credential_source'] == 'mock_dpapi' else 0
    return (result.get('status') == 'model_ready'
            and result.get('loaded_value') == 'FAKE_VALUE_ONLY'
            and result.get('credential_reads') == required_reads)


def payload_candidate(state, action):
    content, prompt = state['content'], state['prompt']
    if action['operation'] == 'raw_equal':
        matched = content == prompt
    elif action['operation'] == 'join_text_only':
        matched = ''.join(b['text'] for b in content if b['type'] == 'text') == prompt
    else:
        raise ValueError('Unknown candidate operation')
    return {'matched': matched}


def payload_truth(state):
    mode, content = state['contract'], state['content']
    if mode == 'wire_exact':
        return type(content) is type(state['prompt']) and content == state['prompt']
    if mode == 'multimodal_exact':
        return content == state['expected_content']
    if mode != 'text_equivalence':
        raise ValueError('Unknown contract')
    if isinstance(content, str):
        canonical = content
    else:
        pieces = []
        for block in content:
            if set(block) != {'type', 'text'} or block['type'] != 'text':
                raise ValueError('Text fixture contains unsupported blocks')
            pieces.extend(block['text'])
        canonical = ''.join(pieces)
    return canonical == state['prompt']


def verify_payload(state, result):
    return (isinstance(result, dict) and type(result.get('matched')) is bool
            and result['matched'] == payload_truth(state))


def check_existing_normalizer():
    # Load only this pure function through AST; do not import the paid runner.
    source = ROOT.parent / 'section7_frozen_jaccard_20261004/audit.py'
    node = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
                if isinstance(n, ast.FunctionDef) and n.name == 'text_content')
    space = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), space)
    normalize = space['text_content']
    checks = []
    for content in ['alpha beta', [{'type': 'text', 'text': 'alpha '}, {'type': 'text', 'text': 'beta'}]]:
        checks.append(normalize(content) == 'alpha beta')
    try:
        normalize([{'type': 'text', 'text': 'alpha beta'}, {'type': 'image', 'url': 'mock:a'}])
        checks.append(False)
    except AssertionError:
        checks.append(True)
    assert all(checks)
    # Recheck the exact archived requests from the actual incident, read-only.
    repo = ROOT.parent.parent
    index = json.loads((source.parent / 'records/raw-archive.json').read_text(encoding='utf-8'))
    archive = source.parent / index['path']
    assert sha(archive) == index['sha256']
    expected_hashes = {r['path']: r['sha256'] for r in index['members']}
    prefix = next(p.rsplit('/', 1)[0] for p in expected_hashes if p.endswith('/048/input-public.json'))
    with tarfile.open(archive, 'r:gz') as bundle:
        def load_member(name, jsonl=False):
            member = bundle.getmember(name)
            assert member.isfile()
            raw = bundle.extractfile(member).read()
            assert hashlib.sha256(raw).hexdigest() == expected_hashes[name]
            return [json.loads(line) for line in raw.splitlines()] if jsonl else json.loads(raw)
        initial = load_member(prefix + '/input-public.json')
        requests = load_member(prefix + '/requests.jsonl', jsonl=True)
        replay = []
        for request in requests:
            payload = load_member(prefix + '/' + request['artifact'])
            user = payload['messages'][1]
            assert user['role'] == 'user'
            old_equal = user['content'] == initial['prompt']
            fixed_equal = normalize(user['content']) == initial['prompt']
            assert old_equal is False and fixed_equal is True
            replay.append({'raw_equal': old_equal, 'normalized_equal': fixed_equal})
    return {'source': str(source.relative_to(repo)).replace('\\', '/'),
            'sha256': sha(source), 'checks_passed': len(checks),
            'archived_incident_requests_replayed': len(replay),
            'archived_request_checks': replay, 'archive_sha256_verified': index['sha256'],
            'limit': 'Text-content comparison only; not all runtime assertions, business score, or multimodal support.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / '.local/cases')
    args = parser.parse_args()
    cases = [json.loads(line) for line in (args.data / 'public_cases.jsonl').read_text(encoding='utf-8').splitlines()]
    private = {r['case']['case_id']: r for r in
               map(json.loads, (args.data / 'evaluator_cases.jsonl').read_text(encoding='utf-8').splitlines())}
    rows = []
    for case in cases:
        state, action = case['current_state'], case['proposed_action']
        if state['fixture'] == 'fake_launch':
            candidate, verifier = credential_candidate, verify_credential
            good_action = deepcopy(action)
            good_action['account'] = (state.get('sealed_for') if state['credential_source'] == 'mock_dpapi'
                                      and state['task_role'] == 'model' else state['permitted_accounts'][0])
            positive = candidate(state, good_action)
            corrupt = deepcopy(positive)
            corrupt['status'] = 'invalid'
            wrong_field = deepcopy(positive)
            if state['task_role'] == 'model':
                wrong_field['loaded_value'] = 'WRONG_FAKE_VALUE'
            else:
                wrong_field['credential_reads'] = 1
            wrong_account = deepcopy(positive)
            wrong_account['account'] = 'unpermitted_account'
        else:
            candidate, verifier = payload_candidate, verify_payload
            positive = {'matched': payload_truth(state)}
            corrupt = {'matched': not positive['matched']}
            wrong_field = {'matched': str(positive['matched'])}
        actual = candidate(state, action)
        decision = 'allow' if verifier(state, actual) else 'block'
        expected = private[case['case_id']]['expected_by_arm']
        tests = {'positive_accepted': verifier(state, positive),
                 'empty_rejected': not verifier(state, {}),
                 'wrong_status_or_decision_rejected': not verifier(state, corrupt),
                 'wrong_value_or_type_rejected': not verifier(state, wrong_field),
                 'candidate_matches_registered_truth': all(v == decision for v in expected.values())}
        if state['fixture'] == 'fake_launch':
            tests['unpermitted_account_rejected'] = not verifier(state, wrong_account)
        assert all(tests.values()), (case['case_id'], tests)
        rows.append({'case_id': case['case_id'], 'candidate_output': actual,
                     'verified_decision': decision, 'tests': tests})
    normalizer = check_existing_normalizer()
    summary = {'status': 'OFFLINE_CONTROLLED_FIXTURES_PASS_NOT_RESEARCH_GO',
               'cases': len(rows), 'assertions_passed': sum(len(r['tests']) for r in rows),
               'actual_candidate_outputs_evaluated': len(rows),
               'original_error_rejected': all(r['verified_decision'] == 'block' for r in rows
                                               if private[r['case_id']]['variant'] == 'recurrence'),
               'legitimate_neighbors_allowed': all(r['verified_decision'] == 'allow' for r in rows
                                                    if private[r['case_id']]['variant'] == 'legitimate_neighbor'),
               'existing_text_normalizer': normalizer,
               'verifier_sha256': sha(Path(__file__)),
               'real_credentials_read': False, 'external_model_calls': 0,
               'limits': ['Fake credential fixture encodes observed account behavior; no current DPAPI retest.',
                          'Eight authored controlled variants, not eight naturally observed failures.',
                          'Source authenticity and human approval are separate from these tests.']}
    write(args.data.parent / 'verifier_results.json', {'summary': summary, 'rows': rows})
    write(ROOT / 'records/incident-verifier-summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
