"""Scripted localhost fixture for the real SDK. No external model traffic."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
import uuid
from prepare import ROOT, save
from protocol import digest


def run_fixture(method, *, note='', sources=None, force_compact=False, timeout=False, grow_output=False, tool_failure=False):
    out = ROOT / '.local/fixtures' / uuid.uuid4().hex
    out.mkdir(parents=True)
    requests = []
    actions = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path == '/tool':
                actions.append(value)
                if tool_failure:
                    self.send_error(500, 'Fixture controller failure'); return
                data = json.dumps({'instance_complete': True, 'observation': 'Question 1: CORRECT.\nExploratory queries used: 0'}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
                return
            if self.headers.get('Authorization') != 'Bearer FIXTURE-NOT-A-SECRET':
                self.send_error(401); return
            requests.append(value)
            if timeout:
                self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                self.wfile.write(b'data: {"choices":[]}\n\n'); self.wfile.flush()
                save(out / 'task-timeout.json', {'observation': 'Fixture TIMED OUT. No hidden answer.'})
                threading.Event().wait(0.5)
                return
            messages = value.get('messages', [])
            summary = not value.get('tools')
            finished = messages and messages[-1].get('role') == 'tool'
            if summary or finished:
                delta = {'role': 'assistant', 'content': 'Fixture summary COBALT.' if summary else 'Completed.'}
                reason = 'stop'
            else:
                args = {'action': 'ANSWER', 'content': 'OK'}
                if method == 'pi_notepad': args['notepad_update'] = 'COBALT'
                delta = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'call_fixture', 'type': 'function',
                         'function': {'name': 'CLBENCH_ACTION', 'arguments': json.dumps(args)}}]}
                reason = 'tool_calls'
            if grow_output and len(requests) == 1:
                delta = {'role': 'assistant', 'reasoning_content': 'Synthetic output-budget exhaustion.'}
                reason = 'length'
            def chunk(delta, finish=None, usage=None):
                result = {'id': 'fixture-' + uuid.uuid4().hex, 'object': 'chat.completion.chunk',
                          'created': 1, 'model': 'glm-5.3-flash',
                          'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
                if usage is not None: result['usage'] = usage
                return 'data: ' + json.dumps(result) + '\n\n'
            data = (chunk(delta) + chunk({}, reason, {'prompt_tokens': 100, 'completion_tokens': 20,
                    'total_tokens': 120, 'prompt_tokens_details': {'cached_tokens': 0}}) + 'data: [DONE]\n\n').encode()
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    config = {'fixture': True, 'out': str(out), 'workspace': str(out / 'workspace'),
        'run_id': 'fixture', 'method_id': method, 'instance_id': 'fixture0', 'project_key': 'fixture',
        'environment': 'database_exploration', 'config_hash': digest({'fixture': method}),
        'base_url': base, 'tool_url': base + '/tool', 'tool_token': 'fixture-token',
        'tool_description': 'Use ANSWER to complete the fixture.',
        'system_append': 'Use CLBENCH_ACTION to submit. After completion end the turn.',
        'prompt': 'Submit OK.', 'notepad': note, 'sources': sources or [],
        'force_compact_fixture': force_compact}
    Path(config['workspace']).mkdir()
    save(out / 'input.json', config)
    try:
        proc = subprocess.run(['node', str(ROOT / 'pi_session.mjs'), str(out / 'input.json')],
            env={**os.environ, 'EXPERIMENT_API_KEY': 'FIXTURE-NOT-A-SECRET'}, capture_output=True, text=True, timeout=60)
    finally:
        server.shutdown(); server.server_close(); thread.join()
    (out / 'stdout.txt').write_text(proc.stdout, encoding='utf-8')
    (out / 'stderr.txt').write_text(proc.stderr, encoding='utf-8')
    if tool_failure:
        assert proc.returncode != 0 and len(requests) == 1
        return {'method': method, 'session_id': json.loads((out / 'session-start.json').read_text(encoding='utf-8'))['session_id'],
            'requests': 1, 'raw': out.relative_to(ROOT).as_posix(), 'controller_failure_stops_model_calls': True,
            'model_calls': 0}
    if proc.returncode:
        raise RuntimeError(proc.stderr[-5000:])
    end = json.loads((out / 'session-end.json').read_text(encoding='utf-8'))
    start = json.loads((out / 'session-start.json').read_text(encoding='utf-8'))
    assert start['active_tools'] == ['CLBENCH_ACTION']
    assert len(actions) == (0 if timeout else 1)
    if actions: assert 'notepad_update' not in actions[0]['action']
    assert end['terminal'] and end['pending_message_count'] == 0
    assert len(list((out / 'requests').glob('*.request.json'))) == len(requests)
    assert all(x['model'] == 'glm-5.3-flash' for x in requests)
    if method == 'pi_notepad' and not timeout: assert end['notepad'] == 'COBALT'
    if note: assert note in json.dumps(requests[0])
    if force_compact: assert (out / 'compaction-after-fixture.json').exists()
    if timeout:
        assert end['timed_out']
        assert any('Fixture TIMED OUT' in str(m.get('content', '')) for m in end['messages'])
    if grow_output:
        assert end['final_output_limit'] == 32768
        first_max = requests[0].get('max_tokens', requests[0].get('max_completion_tokens'))
        second_max = requests[1].get('max_tokens', requests[1].get('max_completion_tokens'))
        assert (first_max, second_max) == (16384, 32768), (first_max, second_max)
    return {'method': method, 'session_id': end['session_id'], 'requests': len(requests),
            'raw': out.relative_to(ROOT).as_posix(), 'long_compaction': force_compact,
            'timeout': timeout, 'output_growth': grow_output, 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--quick', action='store_true'); args = parser.parse_args()
    checks = [run_fixture('pi_none'), run_fixture('pi_notepad'), run_fixture('pi_notepad', note='PREVIOUS-NOTE')]
    checks.append(run_fixture('pi_jaccard', sources=[{'source_id': 'fixture-past', 'episode': {'text': 'past legal source'}}]))
    checks.append(run_fixture('pi_none', timeout=True))
    checks.append(run_fixture('pi_none', grow_output=True))
    checks.append(run_fixture('pi_none', tool_failure=True))
    if not args.quick:
        checks.append(run_fixture('pi_jaccard', sources=[{'source_id': 'long-fixture',
            'episode': {'text': ('COBALT fact. ' * 60000)}}], force_compact=True))
    assert len({c['session_id'] for c in checks}) == len(checks)
    save(ROOT / 'records/pi-sdk-fixtures.json', {'checks': checks, 'model_calls': 0,
        'scope': 'SDK sessions/tools/accounting/native compaction with synthetic local provider',
        'formal_ready': False})
    print(json.dumps({'passed': len(checks), 'model_calls': 0}))


if __name__ == '__main__': main()
