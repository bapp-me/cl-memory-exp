"""Two-session native capability canary, excluded from benchmark scores."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse
import json
import time
import uuid
from prepare import ROOT, read, save, sha
from native_client import broker, put, snapshot, freeze_runtime


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--framework', choices=['claude', 'hermes', 'codex'], required=True)
    args = parser.parse_args(); run_id = f'native-{args.framework}-capability-' + uuid.uuid4().hex[:8]
    if args.framework=='codex':
        import native_client
        native_client.BROKER_KIND='codex'
    directory = ROOT / 'private-runs' / run_id; directory.mkdir()
    created = broker({'op': 'create','runtime_hash':freeze_runtime()}); c = created['container_id']
    save(directory / 'container.json', created)
    try:
        for index in range(2):
            out = directory / f'task-{index:03d}'; out.mkdir()
            actions = []; token = uuid.uuid4().hex
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_): pass
                def do_POST(self):
                    if self.headers.get('X-Run-Token') != token: self.send_error(403); return
                    value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    if value.get('control')=='session_start':
                        save(out/'native-session.json',{'session_id':value['session_id']})
                        route['session_id']=value['session_id']; save(ROOT/'.local/native-routes'/f'{route_id}.json',route)
                        data=b'{"registered":true}'; self.send_response(200)
                        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
                        return
                    actions.append(value); save(out / 'business-actions.json', actions)
                    result = {'observation': 'Capability probe complete. No hidden answer is available.', 'instance_complete': True, 'done': True}
                    data = json.dumps(result).encode(); self.send_response(200)
                    self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
            server = HTTPServer(('127.0.0.1', 0), Handler); server.timeout = .5
            route_id = uuid.uuid4().hex; route_token = uuid.uuid4().hex; session = str(uuid.uuid4())
            route = {'token': route_token, 'run_id': run_id, 'method_id': args.framework + '_memory_ready',
                'instance_id': f'capability-{index}', 'project_key': 'database', 'session_id': session,
                'phase': 'native_capability', 'config_hash': sha(ROOT / 'native-runtime/native_entry.py'),
                'audit_relative_path': out.relative_to(ROOT).as_posix(),
                'tool_url': f'http://127.0.0.1:{server.server_port}/tool', 'tool_token': token, 'output_limit': 16384}
            save(ROOT / '.local/native-routes' / f'{route_id}.json', route)
            cfg = {'framework': args.framework, 'session_id': session, 'project_key': 'database',
                'gateway': f'http://172.30.0.1:43191/r/{route_id}', 'gateway_token': route_token,
                'environment': 'database_exploration', 'tool_description': 'Submit the requested probe answer using action ANSWER and content.',
                'framing': 'This is an isolated capability probe. Use your native memory mechanism when asked. Submit the answer via CLBENCH_ACTION, then end your turn.',
                'prompt': ('Remember in your native persistent memory that this project uses the marker COBALT-739. Save it, then submit READY using CLBENCH_ACTION.'
                           if index == 0 else 'What project marker was saved in the previous session? Retrieve it using your native persistent memory and submit it using CLBENCH_ACTION.')}
            save(out / 'input.json', cfg); task = f'task-{index:03d}'
            put(c, f'/state/tasks/{task}/input.json', cfg)
            job = broker({'op': 'launch', 'container_id': c, 'task': task})['job_id']
            started = time.monotonic(); next_poll = 0
            while True:
                server.handle_request()
                if time.monotonic() >= next_poll:
                    state = broker({'op': 'poll', 'container_id': c, 'job_id': job}); next_poll = time.monotonic() + 2
                    if not state['running']: break
                if time.monotonic() - started > 900: raise TimeoutError('Native capability did not complete')
            server.server_close(); save(out / 'process.json', state)
            snapshot(c, out / 'native-state.tar.gz')
            print(json.dumps({'run_id': run_id, 'index': index, 'exit_code': state['exit_code'], 'actions': len(actions)}), flush=True)
            if state['exit_code'] or not actions: raise RuntimeError('Native capability incomplete; inspect evidence')
        save(ROOT / f'records/{args.framework}-live-capability.json', {'raw': directory.relative_to(ROOT).as_posix(),
            'status': 'calls_completed_requires_audit', 'formal_ready': False})
    finally:
        # Active jobs are never silently killed by this cleanup operation.
        try: broker({'op': 'remove', 'container_id': c})
        except Exception: pass


if __name__ == '__main__': main()
