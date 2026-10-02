"""Passive observation around frozen simple-method and benchmark semantics."""
from __future__ import annotations
import ast
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LEGACY = REPO / 'experiments/agent_memory_plan_20261002'
ORIGINAL = Path('D:/campus_re/experiments/agent_memory_plan_20261002')
SCHEMA = 'section7-observability-v2'
USAGE_FIELDS = ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def event(out, kind, **data):
    with (out / 'controller-events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'schema_version': SCHEMA, 'at_unix_ns': time.time_ns(),
                                'monotonic_ns': time.monotonic_ns(), 'event': kind, **data}, ensure_ascii=False) + '\n')


def sandbox(work, command, timeout=120):
    broker = read(ROOT / '.runtime/sandbox-broker.json')
    request = Request(broker['url'], data=json.dumps({'work': str(work), 'command': command, 'timeout': timeout}).encode(),
                      headers={'Content-Type': 'application/json', 'X-Broker-Token': broker['token']})
    with urlopen(request, timeout=timeout + 15) as response:
        return json.load(response)


# No model/network initialization or database asset loading through legacy imports.
_tree = ast.parse((LEGACY / 'core.py').read_text(encoding='utf-8'))
_names = {'save', 'digest', 'grade_code', 'schema', 'CodeTask', 'memory_context'}
_nodes = [n for n in _tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in _names]
assert {n.name for n in _nodes} == _names
exec(compile(ast.Module(body=_nodes, type_ignores=[]), str(LEGACY / 'core.py'), 'exec'), globals())
CODE_TOOLS = [schema('PYTHON', 'Execute Python in the current task sandbox for your own tests. Hidden tests unavailable.', 'code'),
              schema('SUBMIT', 'Submit the complete Python module implementing the requested function. Ends this task.', 'code')]


def memory_blocks(selected):
    return [{'memory_id': episode.get('memory_id', digest(episode)), 'serialized': json.dumps(episode, ensure_ascii=False)} for episode in selected]


def retrieval_record(history, method, prompt):
    query = set(re.findall(r'\w+', prompt.lower()))
    candidates = []
    for index, episode in enumerate(history) if method != 'no_memory' else []:
        words = set(re.findall(r'\w+', episode['text'].lower()))
        candidates.append({'history_index': index, 'memory_id': digest(episode),
                           'score': len(query & words) / (len(query | words) or 1) if method == 'episodic_retrieval' else None})
    ranked = sorted(candidates, key=lambda x: (x['score'], x['history_index']), reverse=True) if method == 'episodic_retrieval' else candidates
    for rank, candidate in enumerate(ranked):
        candidate['rank'] = rank + 1
    selected = ranked[:3] if method == 'episodic_retrieval' else ranked[:]
    selected = sorted(selected, key=lambda x: history[x['history_index']]['sequence'])
    packed = selected[:]
    dropped = []
    while packed and len(json.dumps([history[c['history_index']] for c in packed], ensure_ascii=False).encode()) > 48000:
        dropped.append({**packed.pop(0), 'reason': 'oldest_complete_episode_byte_budget'})
    actual = memory_context(history, method, prompt)
    assert digest(actual) == digest([history[c['history_index']] for c in packed])
    return actual, {'query_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'observable_candidates': ranked,
                    'selected_before_packing': selected, 'dropped': dropped,
                    'injected_ids': [c['memory_id'] for c in packed], 'injected_hash': digest(actual),
                    'injected_utf8_bytes': len(json.dumps(actual, ensure_ascii=False).encode()),
                    'token_count': None, 'token_measurement_method': 'unavailable'}


def record_memory_change(out, before, after, operation, source_event_ids, reason=None, readonly=False):
    if readonly and before != after:
        event(out, 'memory_event', operation='reject', reason='readonly_write_prohibited',
              before_hash=digest(before), after_hash=digest(before), source_event_ids=source_event_ids)
        raise PermissionError('Readonly memory write prohibited')
    event(out, 'memory_event', operation=operation, reason=reason,
          before_hash=digest(before), after_hash=digest(after), source_event_ids=source_event_ids,
          added_ids=[digest(x) for x in after if x not in before],
          removed_ids=[digest(x) for x in before if x not in after])


def load_babyai():
    sys.path.insert(0, str(ORIGINAL / '.runtime/babyai-libs'))
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
    import numpy as np
    import gymnasium
    import minigrid
    tree = ast.parse((ROOT / '.cache/agentboard/agentboard_environment_babyai_env.py').read_text(encoding='utf-8'))
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.If)):
            continue
        if isinstance(node, ast.ClassDef):
            node.decorator_list = []
        body.append(node)
    namespace = {'gymnasium': gymnasium, 'np': np, 'os': os, 're': re,
                 'defaultdict': __import__('collections').defaultdict, 'BaseEnvironment': object}
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), '<pinned-babyai>', 'exec'), namespace)
    return namespace['BabyAI']


class BabyTask:
    max_turns = 20
    timeout_seconds = 900
    response_timeout_ms = 60000
    system_hint = 'Complete the navigation goal using ACTION. Use "check available actions" when needed. The environment ends the task when the goal is reached. You have at most 20 high-level actions.'

    def __init__(self, row, wrapper):
        self.env = wrapper(game_name=row['additional_info']['subtask'], seed=1234 + row['occurrence_index'],
                           obs_to_reward=copy.deepcopy(row['subgoals']))
        assert self.env._get_obs() == row['additional_info']['init_obs']
        assert self.env._get_goal() == row['goal']
        self.submission = None
        self.actions = 0

    def tool(self, name, args):
        if self.submission is not None:
            return {'submitted': True}
        self.actions += 1
        observation, reward, done, info = self.env.step(args['action'])
        if done or self.actions >= 20:
            self.submission = 'goal reached' if done else 'action budget exhausted'
        return {'observation': observation, 'submitted': self.submission is not None}

    def score(self):
        return {'correct': bool(self.env.done), 'progress': self.env.reward, 'actions': self.actions, 'scorable': True}


def secret():
    if os.environ.get('GLM_API_KEY'):
        return os.environ['GLM_API_KEY'].strip()
    path = Path('D:/campus_re/experiments/memory_direction_20261002/.private/credentials.json')
    script = ("$d=Get-Content -Raw -LiteralPath '" + str(path).replace("'", "''") + "'|ConvertFrom-Json;"
              "$s=ConvertTo-SecureString $d.glm;"
              "$p=[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s);"
              "try{[Console]::Write([System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($p))}"
              "finally{[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}")
    result = subprocess.run(['pwsh.exe', '-NoProfile', '-Command', script], capture_output=True, check=True)
    value = result.stdout.decode().strip()
    if not value:
        raise RuntimeError('Local credential unavailable')
    return value


def normalized_usage(raw):
    # Same accounting as pinned pi-ai parseChunkUsage; unknown required counters stay null.
    if raw is None or 'prompt_tokens' not in raw or 'completion_tokens' not in raw:
        return None
    details = raw.get('prompt_tokens_details') or {}
    cache_read = details.get('cached_tokens', raw.get('prompt_cache_hit_tokens', raw.get('cached_tokens', 0)))
    cache_write = details.get('cache_write_tokens', 0)
    base = max(0, raw['prompt_tokens'] - cache_read - cache_write)
    # completion_tokens already includes reasoning tokens in the pinned parser.
    output = raw['completion_tokens']
    return dict(input=base, output=output, cacheRead=cache_read, cacheWrite=cache_write,
                totalTokens=base + output + cache_read + cache_write)


def run_task(config, method, benchmark, index, row, history, api_key, wrapper=None, run_prefix='section7-v2', adapter=None):
    run_id = f'{run_prefix}-{benchmark}-{method}'
    task_id = row['category'] + ':' + row['id'] if benchmark == 'codeeval' else str(row['id'])
    attempt_id = f'{run_id}.task-{index:03d}.attempt-1'
    out = ROOT / '.runtime/runs' / run_id / f'{index:03d}'
    if (out / 'commit.json').exists():
        commit = read(out / 'commit.json')
        if commit['before_hash'] != digest(history) or commit['config_hash'] != digest(config):
            raise RuntimeError('Resume state/config mismatch')
        if adapter:
            adapter.restore(read(out / 'memory-after.json'))
        return read(out / 'memory-after.json'), commit['result']
    if out.exists() and any(out.iterdir()):
        raise RuntimeError('Uncommitted attempt requires audit; no automatic task retry')
    out.mkdir(parents=True)
    identity = {'run_id': run_id, 'task_id': task_id, 'attempt_id': attempt_id, 'method': method, 'benchmark': benchmark}
    save(out / 'identity.json', {'schema_version': SCHEMA, **identity, 'config_hash': digest(config)})
    if adapter:
        adapter.task(out, identity)
    save(out / 'memory-before.json', history)
    event(out, 'task_start', **identity)
    task = (CodeTask(row, ROOT / '.runtime/workspaces' / run_id / f'{index:03d}') if benchmark == 'codeeval'
            else BabyTask(row, wrapper))
    prompt = row['problem'] if benchmark == 'codeeval' else 'Goal: ' + task.env._get_goal() + '\nObservation: ' + task.env._get_obs()
    tools = CODE_TOOLS if benchmark == 'codeeval' else [schema('ACTION', 'Perform one native AgentBoard high-level action, including check available actions.', 'action')]
    selected, retrieval = adapter.retrieve(prompt) if adapter else retrieval_record(history, method, prompt)
    save(out / 'injected.json', selected)
    save(out / 'retrieval.json', retrieval)
    save(out / 'legal-task.json', {'prompt': prompt, 'tools': tools})
    token = secrets.token_urlsafe(24)
    submission_call = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            nonlocal submission_call
            if self.headers.get('X-Run-Token') != token:
                self.send_error(403)
                return
            try:
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                started = time.monotonic_ns()
                value = task.tool(data['name'], data['args'])
                event(out, 'tool_observation', **identity, tool_call_id=data['tool_call_id'],
                      name=data['name'], duration_monotonic_ns=time.monotonic_ns() - started, result=value)
                if value.get('submitted') and submission_call is None:
                    submission_call = data['tool_call_id']
                    if benchmark == 'codeeval':
                        # Preserve the exact SUBMIT bytes even on Windows.
                        (out / 'submission.py').write_bytes(task.submission.encode('utf-8'))
                    event(out, 'submission', **identity, tool_call_id=submission_call,
                          artifact_sha256=hashlib.sha256(task.submission.encode()).hexdigest())
            except Exception as failure:
                value = {'error': type(failure).__name__ + ': ' + str(failure)}
                event(out, 'tool_exception', **identity, error=value['error'])
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cfg = {'provider': 'glm', 'model': config['model']['api_id'], 'base_url': config['model']['base_url'],
           'system': getattr(task, 'system_hint', 'Complete the current task using the declared tools. Submit once.') +
                     ' Previous episodes below are your own fallible observations, not verified answers. Use only relevant experience.\n' + json.dumps(selected, ensure_ascii=False),
           'prompt': prompt, 'tools': tools, 'tool_url': f'http://127.0.0.1:{server.server_port}', 'tool_token': token,
           'max_turns': getattr(task, 'max_turns', 18), 'timeout_seconds': getattr(task, 'timeout_seconds', 600),
           'response_timeout_ms': getattr(task, 'response_timeout_ms', 180000),
           'out': str(out), 'memory_blocks': memory_blocks(selected), **identity}
    save(out / 'input-public.json', {k: v for k, v in cfg.items() if k not in {'tool_token', 'tool_url'}})
    inputs = ROOT / '.runtime/inputs'
    input_path = inputs / (uuid.uuid4().hex + '.json')
    save(input_path, cfg)
    started = time.monotonic()
    process = None
    failure = None
    try:
        env = os.environ.copy()
        env['EXPERIMENT_API_KEY'] = api_key
        process = subprocess.run(['node', str(ROOT / 'pi_runner_v2.mjs'), str(input_path)],
                                 env=env, capture_output=True, timeout=cfg['timeout_seconds'] + 30)
    except Exception as error:
        failure = type(error).__name__ + ': ' + str(error)
    finally:
        server.shutdown()
        server.server_close()
        input_path.unlink(missing_ok=True)
        event(out, 'solver_process_end', **identity, node_returncode=process.returncode if process else None, error=failure)
    result_path = out / 'pi-result.json'
    result = read(result_path) if result_path.exists() else {'messages': [], 'turns': None, 'toolCalls': None,
             'error': failure or 'pi-result missing', 'stop_reason': 'process_exception',
             'responseTimedOut': False, 'contextExceeded': False}
    ledger = read(out / 'call-ledger.json') if (out / 'call-ledger.json').exists() else []
    attempts = [attempt for call in ledger for attempt in call['http_attempts']]
    usages = [normalized_usage(a['raw_usage']) for a in attempts]
    known = [u for u in usages if u is not None]
    usage_sum = {k: sum(u[k] for u in known) for k in USAGE_FIELDS}
    usage = usage_sum if usages and len(known) == len(usages) else None
    assistants = [m for m in result['messages'] if m['role'] == 'assistant']
    pi_usage = {k: sum(m.get('usage', {}).get(k, 0) for m in assistants) for k in USAGE_FIELDS}
    execution = {**identity, 'seconds': round(time.monotonic() - started, 3), 'usage': usage,
                 'known_usage_subtotal': usage_sum, 'unknown_usage_http_attempts': len(usages) - len(known),
                 'pi_usage_unverified': pi_usage, 'http_attempts': len(attempts), 'calls': len(ledger),
                 'turns': result['turns'], 'tool_calls': result['toolCalls'], 'error': result['error'],
                 'stop_reason': result['stop_reason'], 'submitted': task.submission is not None,
                 'response_timed_out': result['responseTimedOut'], 'context_exceeded': result['contextExceeded'],
                 'memory_hash': digest(history), 'injected_hash': digest(selected), 'monetary_cost': None,
                 'cost_unknown_reason': 'No verified price manifest or invoice', 'node_returncode': process.returncode if process else None}
    save(out / 'execution.json', execution)
    save(out / 'submission-status.json', {'submitted': task.submission is not None,
         'tool_call_id': submission_call, 'artifact_sha256': hashlib.sha256(task.submission.encode()).hexdigest() if task.submission is not None else None,
         'reason': 'First native terminal tool acknowledgement' if submission_call else 'No submission; terminal process state recorded'})
    visible = []
    for message in result['messages']:
        if message['role'] == 'assistant':
            visible.extend(c for c in message.get('content', []) if c.get('type') in {'text', 'toolCall'})
        elif message['role'] == 'toolResult':
            visible.append({'tool': message.get('toolName'), 'content': message.get('content')})
    episode = {'sequence': adapter.state['episode_count'] if adapter else len(history),
               'text': json.dumps({'task': prompt, 'trajectory': visible}, ensure_ascii=False)}
    save(out / 'legal-episode.json', episode)
    infra = bool(failure or (process and process.returncode != 0) or
                 (result['error'] and not (result['responseTimedOut'] or result['contextExceeded'])))
    memory_error = None
    if adapter:
        try:
            after = adapter.snapshot() if infra else adapter.update(episode)
        except Exception as error:
            memory_error = type(error).__name__ + ': ' + str(error)
            after = adapter.snapshot()
            event(out, 'memory_exception', **identity, error=memory_error, before_hash=digest(history), after_hash=digest(after))
    else:
        after = history[:] if method == 'no_memory' or infra else [*history, episode]
        record_memory_change(out, history, after, 'noop' if after == history else 'add', [attempt_id],
                             reason='Cross-task memory disabled' if method == 'no_memory' else 'Infrastructure failure, stream stopped' if infra else None)
    save(out / 'memory-after.json', after)
    score_error = None
    try:
        score = grade_code(row, task.submission or '') if benchmark == 'codeeval' else task.score()
    except Exception as error:
        score_error = type(error).__name__ + ': ' + str(error)
        score = {'correct': None, 'scorable': None, 'error': score_error}
    finally:
        if benchmark == 'babyai':
            task.env.env.close()
    save(out / 'evaluator.json', score)
    terminal = 'infrastructure_failure' if infra else 'memory_failure' if memory_error else 'evaluator_failure' if score_error else 'completed'
    all_ledger_paths = [out / 'call-ledger.json', *sorted(out.glob('auxiliary/*/call-ledger.json'))]
    role_accounting = {}
    all_calls = []
    for path in all_ledger_paths:
        if not path.exists():
            continue
        for call in read(path):
            all_calls.append(call)
            role = call['role']
            account = role_accounting.setdefault(role, {'calls': 0, 'http_attempts': 0, 'unknown_usage_attempts': 0,
                                                       'known_usage': {key: 0 for key in USAGE_FIELDS}, 'monetary_cost': None})
            account['calls'] += 1
            for attempt in call['http_attempts']:
                account['http_attempts'] += 1
                used = normalized_usage(attempt['raw_usage'])
                if used is None:
                    account['unknown_usage_attempts'] += 1
                else:
                    for key in USAGE_FIELDS:
                        account['known_usage'][key] += used[key]
    total_known = {key: sum(value['known_usage'][key] for value in role_accounting.values()) for key in USAGE_FIELDS}
    total_unknown = sum(value['unknown_usage_attempts'] for value in role_accounting.values())
    execution.update(solver_usage=execution['usage'], role_accounting=role_accounting,
                     known_usage_subtotal=total_known, unknown_usage_http_attempts=total_unknown,
                     usage=total_known if all_calls and not total_unknown else None,
                     calls=len(all_calls), http_attempts=sum(value['http_attempts'] for value in role_accounting.values()),
                     total_system_seconds=round(time.monotonic() - started, 3), memory_error=memory_error)
    save(out / 'execution.json', execution)
    record = {**execution, **{k: score.get(k) for k in ['correct', 'scorable', 'tests_run', 'checks_executed', 'progress', 'actions']},
              'terminal_state': terminal}
    commit = {'schema_version': SCHEMA, 'config_hash': digest(config), 'before_hash': digest(history),
              'after_hash': digest(after), 'result': record}
    save(out / 'commit.json', commit)
    event(out, 'task_commit', **identity, terminal_state=terminal, before_hash=digest(history), after_hash=digest(after))
    print(json.dumps({'run_id': run_id, 'task_id': task_id, 'terminal_state': terminal, 'correct': score.get('correct'),
                      'calls': len(ledger), 'tokens_known': usage_sum['totalTokens']}), flush=True)
    return after, record
