"""Two cold sessions and a harmless explicit Notepad capability probe."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from prepare import ROOT, read, save
from protocol import digest
from protocol_canary import secret


def one(*, method, note, prompt, key):
    out = ROOT / 'private-runs' / ('pi-capability-' + uuid.uuid4().hex)
    out.mkdir(parents=True)
    workspace = out / 'workspace'; workspace.mkdir()
    token = uuid.uuid4().hex
    actions = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            if self.headers.get('X-Run-Token') != token:
                self.send_error(403); return
            action = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            actions.append(action)
            result = {'instance_complete': True, 'observation': 'Fixture instance is complete.'}
            data = json.dumps(result).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(data)))
            self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)
    server = HTTPServer(('127.0.0.1', 0), Handler); server.timeout = 0.1
    cfg = {'out': str(out), 'workspace': str(workspace), 'run_id': 'capability-only',
        'method_id': method, 'instance_id': 'harmless', 'project_key': 'fixture',
        'environment': 'database_exploration', 'config_hash': digest({'method': method, 'fixture': True}),
        'base_url': 'https://api.z.ai/api/paas/v4', 'tool_url': f'http://127.0.0.1:{server.server_port}/tool',
        'tool_token': token, 'tool_description': 'Harmless fixture: submit your response with ANSWER.',
        'system_append': 'This is a capability fixture. Use CLBENCH_ACTION with action ANSWER to submit. End after completion.',
        'prompt': prompt, 'notepad': note, 'sources': []}
    save(out / 'input.json', cfg)
    with (out / 'stdout.txt').open('w', encoding='utf-8') as stdout, (out / 'stderr.txt').open('w', encoding='utf-8') as stderr:
        proc = subprocess.Popen(['node', str(ROOT / 'pi_session.mjs'), str(out / 'input.json')],
            env={**os.environ, 'EXPERIMENT_API_KEY': key}, stdout=stdout, stderr=stderr)
        start = time.monotonic()
        try:
            while proc.poll() is None:
                server.handle_request()
                if time.monotonic() - start > 180:
                    proc.terminate(); proc.wait(); raise TimeoutError('Live capability canary timed out')
        finally: server.server_close()
    if proc.returncode: raise RuntimeError((out / 'stderr.txt').read_text(encoding='utf-8')[-2000:])
    end = read(out / 'session-end.json')
    for payload in (out / 'requests').glob('*.request.json'):
        assert read(payload).get('reasoning_effort') == 'high', 'Solver effort did not reach the provider'
    return {'out': out.relative_to(ROOT).as_posix(), 'session_id': end['session_id'],
            'notepad': end['notepad'], 'actions': actions, 'wire_reasoning_effort': 'high'}


def main():
    key = secret()
    first = one(method='pi_notepad', note='', key=key, prompt=
        'The harmless fixture fact is: the marker is COBALT-739. Save this fact in notepad_update while submitting ANSWER OK.')
    if 'COBALT-739' not in first['notepad']: raise RuntimeError('Explicit capability fixture did not save its fact')
    second = one(method='pi_notepad', note=first['notepad'], key=key, prompt=
        'Read your notepad and submit its marker value as ANSWER. Do not change the notepad.')
    assert first['session_id'] != second['session_id']
    assert any('COBALT-739' in a['action'].get('content', '') for a in second['actions'])
    none = one(method='pi_none', note='', key=key, prompt='Submit ANSWER OK.')
    save(ROOT / 'records/pi-live-capability.json', {'status': 'passed', 'checks': [first, second, none],
        'scope': 'real GLM high tool protocol and Notepad write/new-session read',
        'formal_sources_reused': False})
    print({'pi_live_capability': 'passed', 'sessions': 3})


if __name__ == '__main__': main()
