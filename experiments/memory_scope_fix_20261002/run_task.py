"""Run authentic pi/Hermes loops with a common restricted tool/memory protocol.

The API key exists only in the Python recorder, never in Agent context or files.
No evaluation feedback is sent to the model. Reusing a run ID is forbidden.
"""
import argparse
import copy
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'memory_direction_20261002'
sys.path.insert(0, str(OLD))
from lab_common import get_secret, save_json
from api_proxy import RecordingProxy
from environment import Environment, grade

MODELS = {'deepseek': ('deepseek-flash', 'https://api.deepseek.com/anthropic'), 'glm': ('glm-5.3-flash', 'https://api.z.ai/api/anthropic')}
SYSTEM = 'You are a capable assistant solving independent tasks in a local workspace. Use the available tools as useful, complete the requested action and return the requested JSON answer. Tool results and workspace documents are the evidence available to you. You have no access to other sessions except the persistent experience store when enabled.'
WRITER = 'The following is the complete visible transcript of a finished task. Save useful reusable experience to persistent storage using experience put. You may replace existing entries. Future tasks are unknown. Do not merely save the numeric answer. Use at most 3200 characters across all entries.'
GUIDED = ' For each claim, preserve the observed environment/version, applicability conditions, supporting observations, and what remains untested. Do not generalize a relationship outside the observed subset. Include a cheap way to check applicability when relevant; retain useful procedures. Do not invent unseen changes or future tasks.'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def usage(directory):
    totals = Counter()
    ledger = directory / 'http/ledger.jsonl'
    if not ledger.exists():
        return dict(totals)
    for line in ledger.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        merged = {}
        for event in row['usage_events']:
            merged.update(event)
        totals['requests'] += 1
        totals['failed_http'] += row.get('status') != 200
        totals['usage_missing_requests'] += not any(merged.get(k, 0) for k in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
        for key in ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'):
            totals[key] += merged.get(key, 0)
    totals['all_input_tokens'] = totals['input_tokens'] + totals['cache_read_input_tokens'] + totals['cache_creation_input_tokens']
    return dict(totals)


def run(a):
    directory = ROOT / 'results/runs' / a.run_id
    if directory.exists():
        raise FileExistsError(a.run_id)
    directory.mkdir(parents=True)
    spec = load(ROOT / 'fixtures' / a.group / f'{a.stage}.json')
    seed = load(ROOT / 'results/runs' / a.memory_from / 'memory_after/entries.json') if a.memory_from else {}
    if a.memory_seed:
        if a.memory_from:
            raise ValueError('Choose memory_from or memory_seed, not both')
        seed = load(ROOT / a.memory_seed)
    prompt = spec['prompt']
    if a.writer_from or a.repair_from:
        source = ROOT / 'results/runs' / (a.writer_from or a.repair_from)
        config = load(source / 'input.json')
        # Same a trajectory and same initial store for both writer variants.
        if a.writer_from and (config['stage'] != 'a' or config.get('writer_from')):
            raise ValueError('Writer source must be an a solver run')
        if a.repair_from and config['stage'] != 'c':
            raise ValueError('Repair source must be a completed c consumer run')
        seed = load(source / 'memory_after/entries.json')
        result = load(source / 'agent-result.json')
        visible = {'task': config['prompt'], 'messages': result['messages']}
        instruction = ('Review this completed task trajectory and explicitly repair persistent experience that proved wrong or inapplicable. Correct the stored applicability conditions while preserving experience useful in its original context. Use experience put/delete to persist the repair, based only on visible evidence. Do not invent future task answers.' if a.repair_from else WRITER + (GUIDED if a.guided else ''))
        prompt = instruction + '\n\n' + json.dumps(visible, ensure_ascii=False)
        spec['tools'] = []
    if a.caution:
        prompt += '\nCheck whether historical experience applies to the current task.'
    if a.explicit_fix:
        prompt += '\nIf any prior experience is inapplicable or wrong, update the persistent experience store to repair it while preserving what remains useful in its original scope.'
    if a.require_retrieval:
        prompt += '\nDiagnostic retrieval condition: before task actions, use experience search/get to inspect relevant stored experience, then complete the task.'
    env = Environment(spec, directory, a.memory, seed)
    env.phase = 'explicit_repair' if a.repair_from else 'writer' if a.writer_from else 'consumer'
    system = SYSTEM + env.system_memory(a.ensure_read)
    model, endpoint = MODELS[a.provider]
    if a.transport == 'native':
        if a.provider != 'glm' or a.agent != 'pi':
            raise ValueError('Native transport calibration is restricted to GLM/pi')
        endpoint = 'https://api.z.ai/api/paas/v4'
    config = {**vars(a), 'model': model, 'endpoint': endpoint, 'prompt': prompt, 'system': system,
              'thinking': {'type': 'enabled', 'budget_tokens': 4096}, 'output_config': {'effort': 'high'},
              'max_output_tokens': 32768, 'memory_budget_characters': 3200,
              'protocol': 'controlled-adapter-v1', 'no_history_retrieval': True,
              'hermes_prompt_override': a.agent == 'hermes', 'pi_package': '@earendil-works/pi-agent-core@1.0.0'}
    save_json(directory / 'input.json', config)
    save_json(directory / 'exposed-tools.json', env.tool_schemas())
    save_json(directory / 'process.json', {'pid': os.getpid(), 'status': 'running'})
    key = get_secret(a.provider)
    if a.transport == 'native':
        from native_proxy import NativeProxy
        proxy = NativeProxy(model, key, directory / 'http', max_requests=a.max_requests).start()
        config.update(thinking={'type': 'enabled', 'clear_thinking': False}, reasoning_effort='high', output_config=None,
                      protocol='controlled-adapter-v1-glm-native-transport')
        save_json(directory / 'input.json', config)
    else:
        proxy = RecordingProxy(endpoint, model, key, directory / 'http', max_output_tokens=32768, max_requests=a.max_requests, effort='high').start()
    start = time.monotonic()
    result, error = {}, None
    try:
        if a.agent == 'pi':
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass
                def do_POST(self):
                    data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    response = json.dumps(env.call(data['name'], data['args']), ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(response)
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            runtime = ROOT / '.runtime/inputs'
            runtime.mkdir(parents=True, exist_ok=True)
            request_file = runtime / f'{a.run_id}.json'
            save_json(request_file, {'model': model, 'prompt': prompt, 'system': system, 'tools': env.tool_schemas(),
                      'transport': a.transport,
                      'proxy_url': proxy.url, 'tool_url': f'http://127.0.0.1:{server.server_address[1]}',
                      'max_requests': a.max_requests, 'timeout_seconds': a.timeout,
                      'events_file': str(directory / 'events.jsonl'), 'result_file': str(directory / 'agent-result.json')})
            try:
                proc = subprocess.run(['node', str(ROOT / 'pi_runner.mjs'), str(request_file)], capture_output=True, timeout=a.timeout + 30)
                (directory / 'stdout.txt').write_bytes(proc.stdout)
                (directory / 'stderr.txt').write_bytes(proc.stderr)
                if (directory / 'agent-result.json').exists():
                    result = load(directory / 'agent-result.json')
                if proc.returncode:
                    raise RuntimeError(f'pi process exit {proc.returncode}: ' + proc.stderr.decode(errors='replace')[-1500:])
            finally:
                server.shutdown()
                server.server_close()
        else:
            home = ROOT / '.runtime/hermes-profiles' / a.run_id
            home.mkdir(parents=True)
            os.environ.update({'HERMES_HOME': str(home), 'HERMES_RUNTIME_DIR': str(OLD / '.runtime/hermes-tools'),
                               'LOCALAPPDATA': str(OLD / '.runtime/hermes-localappdata'), 'HERMES_TELEMETRY_ENABLED': 'false',
                               'PYTHONUTF8': '1'})
            (home / 'config.yaml').write_text('memory:\n  memory_enabled: false\n  user_profile_enabled: false\ntools:\n  tool_search:\n    enabled: off\ncompression:\n  enabled: false\n', encoding='utf-8')
            sys.path.insert(0, str(OLD / '.runtime/hermes-source'))
            from tools.registry import registry
            from run_agent import AIAgent
            for s in env.tool_schemas():
                registry.register(name=s['name'], toolset='scope_lab', schema=s,
                                  handler=lambda args, _name=s['name'], **kw: json.dumps(env.call(_name, args), ensure_ascii=False), override=True)
            agent = AIAgent(base_url=proxy.url, api_key='local-experiment-proxy', provider='custom', api_mode='anthropic_messages',
                            model=model, enabled_toolsets=['scope_lab'], max_iterations=a.max_requests,
                            max_tokens=32768, reasoning_config={'enabled': True, 'effort': 'high'}, quiet_mode=True,
                            skip_context_files=True, skip_memory=True, skip_background_review=True,
                            save_trajectories=False, run_budget_seconds=a.timeout, cwd=str(home))
            # This is a controlled core-loop comparison, explicitly not native Hermes UX.
            agent._build_system_prompt = lambda *args, **kw: system
            save_json(directory / 'hermes-exposed-tools.json', agent.tools)
            actual_names = {t.get('function', t).get('name') for t in agent.tools}
            if actual_names != {s['name'] for s in env.tool_schemas()}:
                agent.close()
                raise ValueError('Hermes tool surface differs: ' + str(actual_names))
            try:
                result = agent.run_conversation(prompt)
            finally:
                agent.close()
            save_json(directory / 'agent-result.json', result)
    except Exception:
        error = traceback.format_exc().replace(key, '[REDACTED]')
        (directory / 'error.txt').write_text(error, encoding='utf-8')
    finally:
        proxy.close()
    env.save_memory()
    final = result.get('final_response', '')
    error = error or result.get('error')
    save_json(directory / 'state-after.json', env.final_state())
    if not (directory / 'agent-result.json').exists():
        save_json(directory / 'agent-result.json', result)
    counts = Counter(x['tool'] for x in env.calls)
    repeated = sum(v - 1 for v in Counter((x['tool'], json.dumps(x['args'], sort_keys=True)) for x in env.calls if x['tool'] != 'experience').values() if v > 1)
    evaluation = {'success': bool(env.entries), 'writer_saved': bool(env.entries)} if a.writer_from or a.repair_from else grade(final, load(ROOT / 'checks' / a.group / f'{a.stage}.json'), env.final_state())
    summary = {'run_id': a.run_id, 'group': a.group, 'stage': a.stage, 'agent': a.agent, 'provider': a.provider,
               'memory': a.memory, 'memory_from': a.memory_from, 'writer_from': a.writer_from, 'repair_from': a.repair_from, 'guided': a.guided,
               'caution': a.caution, 'ensure_read': a.ensure_read, 'explicit_fix': a.explicit_fix,
               'seconds': round(time.monotonic() - start, 3), 'error': error, 'stop_reason': result.get('stop_reason'),
               'quality': evaluation, 'tools': dict(counts), 'task_tools': sum(v for k, v in counts.items() if k != 'experience'),
               'memory_reads': sum(x['tool'] == 'experience' and x['args']['op'] in ('get', 'search') for x in env.calls),
               'memory_writes': sum(x['tool'] == 'experience' and x['args']['op'] in ('put', 'delete') and not x['error'] for x in env.calls),
               'tool_errors': sum(x['error'] for x in env.calls), 'repeated_task_calls': repeated,
               'memory_changed': seed != env.entries, 'usage': usage(directory), 'final_response': final}
    save_json(directory / 'summary.json', summary)
    save_json(directory / 'process.json', {'pid': os.getpid(), 'status': 'finished', 'error': bool(error)})
    print(json.dumps({k: summary[k] for k in ('run_id', 'seconds', 'quality', 'task_tools', 'memory_writes', 'error')}, ensure_ascii=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run-id', required=True)
    p.add_argument('--group', required=True)
    p.add_argument('--stage', choices=list('abcd'), required=True)
    p.add_argument('--provider', choices=MODELS, default='deepseek')
    p.add_argument('--transport', choices=['anthropic', 'native'], default='anthropic')
    p.add_argument('--agent', choices=['pi', 'hermes'], default='pi')
    p.add_argument('--memory', choices=['none', 'file', 'search'], default='file')
    p.add_argument('--memory-from')
    p.add_argument('--memory-seed')
    p.add_argument('--writer-from')
    p.add_argument('--repair-from')
    p.add_argument('--guided', action='store_true')
    p.add_argument('--caution', action='store_true')
    p.add_argument('--ensure-read', action='store_true')
    p.add_argument('--require-retrieval', action='store_true')
    p.add_argument('--explicit-fix', action='store_true')
    p.add_argument('--max-requests', type=int, default=24)
    p.add_argument('--timeout', type=int, default=420)
    run(p.parse_args())
