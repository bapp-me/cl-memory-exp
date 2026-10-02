"""No paid models: observation, restore and real sandbox isolation fixtures."""
import copy
import json
from pathlib import Path
import subprocess
import unittest.mock
import uuid
from urllib.request import Request, urlopen
from types import SimpleNamespace
from runtime import ROOT, ORIGINAL, LEGACY, read, save, digest, event, retrieval_record, memory_context, record_memory_change, normalized_usage, load_babyai, BabyTask, sandbox, run_task


def main():
    out = ROOT / '.runtime/fixtures/python'
    out.mkdir(parents=True, exist_ok=True)
    checks = []

    def passed(name, **data):
        checks.append({'name': name, 'passed': True, **data})

    assert retrieval_record([], 'episodic_retrieval', 'q')[0] == []
    passed('empty history')
    history = [{'sequence': i, 'text': text} for i, text in enumerate(['match old', 'other', 'match new', 'match newest'])]
    selected, record = retrieval_record(history, 'episodic_retrieval', 'match')
    assert record['observable_candidates'][0]['history_index'] == 3
    assert digest(selected) == digest(memory_context(history, 'episodic_retrieval', 'match'))
    passed('Jaccard rank/tie and chronological packing')
    huge = [{'sequence': 0, 'text': 'x' * 49000}, {'sequence': 1, 'text': 'small'}]
    selected, record = retrieval_record(huge, 'bounded_icl', 'q')
    assert selected == huge[1:] and record['dropped'][0]['history_index'] == 0
    passed('oldest whole episode byte eviction')
    legacy = LEGACY / 'runs/full-codeeval-glm-episodic_retrieval/095'
    before = read(legacy / 'memory-before.json')
    result = read(legacy / 'pi-result.json')
    prompt = next(m['content'] for m in result['messages'] if m['role'] == 'user')
    if not isinstance(prompt, str):
        prompt = ''.join(c.get('text', '') for c in prompt)
    assert digest(retrieval_record(before, 'episodic_retrieval', prompt)[0]) == digest(read(legacy / 'injected.json'))
    passed('frozen long history injection equivalence')
    a = [{'id': 'a', 'text': 'original'}]
    for operation, after in [('modify', [{'id': 'a', 'text': 'changed'}]), ('merge', [{'id': 'a+b', 'text': 'merged'}]), ('delete', [])]:
        record_memory_change(out, a, after, operation, ['fixture.legal-source'])
    record_memory_change(out, a, a, 'reject', ['fixture.legal-source'], 'Rejected fixture candidate')
    passed('modify/merge/delete/rejection records')
    try:
        record_memory_change(out, a, [], 'delete', ['fixture.probe'], readonly=True)
        raise AssertionError('Readonly write accepted')
    except PermissionError:
        pass
    assert a == [{'id': 'a', 'text': 'original'}]
    passed('readonly prohibition and unchanged state hash')
    assert normalized_usage(None) is None
    assert normalized_usage({'prompt_tokens': 0}) is None
    assert normalized_usage({'prompt_tokens': 100, 'completion_tokens': 7, 'prompt_tokens_details': {'cached_tokens': 20}}) == dict(input=80, output=7, cacheRead=20, cacheWrite=0, totalTokens=107)
    passed('unknown usage distinct from valid zero and cache accounting')
    submitted = 'def f():\n    return 1\n'
    (out / 'submission.py').write_bytes(submitted.encode('utf-8'))
    import hashlib
    assert hashlib.sha256((out / 'submission.py').read_bytes()).hexdigest() == hashlib.sha256(submitted.encode()).hexdigest()
    passed('exact submitted text/file bytes across Windows newline handling')
    fixture_config = read(ROOT / 'records/confirmed-config-v1.json')
    submit_row = {'id': 'fixture-submit', 'category': 'raw', 'problem': 'Fixture legal submission request',
                  'test_code': 'assert f()==1', 'solution': 'HIDDEN_SENTINEL'}
    submit_prefix = 'fixture-submit-' + uuid.uuid4().hex

    def mock_node(command, **kwargs):
        cfg = read(command[-1])
        request = Request(cfg['tool_url'], data=json.dumps({'name': 'SUBMIT', 'args': {'code': submitted},
            'tool_call_id': 'fixture-submit-call'}).encode(), headers={'Content-Type': 'application/json', 'X-Run-Token': cfg['tool_token']})
        with urlopen(request, timeout=5) as response:
            assert json.load(response)['submitted']
        folder = Path(cfg['out'])
        save(folder / 'pi-result.json', {'messages': [{'role': 'assistant', 'content': [{'type': 'toolCall',
             'name': 'SUBMIT', 'id': 'fixture-submit-call', 'arguments': {'code': submitted}}]}],
             'turns': 1, 'toolCalls': 1, 'error': None, 'stop_reason': 'toolUse', 'responseTimedOut': False, 'contextExceeded': False})
        save(folder / 'call-ledger.json', [])
        return SimpleNamespace(returncode=0)

    with unittest.mock.patch('runtime.subprocess.run', side_effect=mock_node):
        after, submit_result = run_task(fixture_config, 'no_memory', 'codeeval', 0, submit_row, [], 'fixture-key', run_prefix=submit_prefix)
    submitted_file = ROOT / '.runtime/runs' / (submit_prefix + '-codeeval-no_memory') / '000/submission.py'
    assert submitted_file.read_bytes() == submitted.encode('utf-8') and submit_result['correct'] is True
    passed('actual controller SUBMIT acknowledgement/exact artifact bytes/scorer input')
    probe = ROOT / '.runtime/sandbox-canary/isolation'
    probe.mkdir(parents=True, exist_ok=True)
    code = """import os, socket, json
paths=['/mnt/d/campus_re','/home/fucak','/proc','/work/../evaluators','/work/../workspaces']
assert not any(os.path.exists(path) for path in paths), paths
assert not os.path.exists('/work/../../mnt/d/campus_re')
s=socket.socket();s.settimeout(0.2)
try:
    s.connect(('1.1.1.1',443))
    raise AssertionError('External network reachable')
except OSError:
    pass
import sys
assert sys.version_info[:2] == (3,10),sys.version
print(json.dumps({'isolated':True,'python':sys.version.split()[0]}))
"""
    (probe / 'probe.py').write_text(code, encoding='utf-8')
    response = sandbox(probe, ['/usr/bin/python3', '/work/probe.py'])
    assert response['returncode'] == 0, response
    passed('real WSL sandbox host/other-run/network isolation', result=response)
    wrapper = load_babyai()
    rows = [json.loads(line) for line in (ROOT / '.cache/agentcl-babyai.jsonl').read_text(encoding='utf-8').splitlines()]
    config = read(ROOT / 'records/confirmed-config-v1.json')
    for row in rows:
        if row['id'] not in config['data']['babyai_ordered_task_ids']:
            continue
        task = BabyTask(row, wrapper)
        initial = task.env._get_obs()
        observation = task.tool('ACTION', {'action': 'check available actions'})
        assert observation['observation'] and not any(k in observation for k in {'reward', 'progress', 'subgoals', 'correct'})
        task.env.env.close()
    passed('all 8 BabyAI seeds/initial states and feedback permission')
    # Exercise the actual controller's exception-finally and durable resume branch.
    row = {'id': 'fixture', 'category': 'raw', 'problem': 'Fixture legal instruction',
           'test_code': 'assert True', 'solution': 'HIDDEN_SENTINEL_NEVER_AGENT_VISIBLE'}
    fixture_prefix = 'fixture-process-exception-' + uuid.uuid4().hex
    with unittest.mock.patch('runtime.subprocess.run', side_effect=subprocess.TimeoutExpired('fixture-node', 1)):
        after, record = run_task(config, 'no_memory', 'codeeval', 0, row, [], 'fixture-key', run_prefix=fixture_prefix)
    assert record['terminal_state'] == 'infrastructure_failure' and after == []
    public = ROOT / '.runtime/runs' / (fixture_prefix + '-codeeval-no_memory') / '000/input-public.json'
    assert 'HIDDEN_SENTINEL' not in public.read_text(encoding='utf-8')
    with unittest.mock.patch('runtime.subprocess.run', side_effect=AssertionError('Duplicate execution')):
        restored, restored_record = run_task(config, 'no_memory', 'codeeval', 0, row, [], 'fixture-key', run_prefix=fixture_prefix)
    assert restored_record == record and restored == []
    passed('process exception finally/unique terminal record')
    passed('duplicate committed task restores without generation or write')
    passed('hidden source/test labels excluded from public task input')
    completed = subprocess.run(['node', str(ROOT / 'recorder_fixture.mjs')], capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    mock_report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert mock_report['passed'] and mock_report['model_calls'] == 0
    passed('real pinned SDK mock HTTP retry and payload neutrality', report=mock_report)
    save(ROOT / 'records/fixture-acceptance.json', {'schema_version': 'section7-observability-v1',
         'passed': True, 'model_calls': 0, 'checks': checks,
         'limits': ['Generic change-event fixtures do not certify unimplemented Mem0/AWM/ACE semantics.',
                    'Isolation probes cover declared channels, not every possible kernel vulnerability.']})
    print(json.dumps({'model_calls': 0, 'passed': True, 'checks': len(checks)}))


if __name__ == '__main__':
    main()
