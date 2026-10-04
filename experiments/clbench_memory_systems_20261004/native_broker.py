"""Credential-free container lifecycle for the three native frameworks.

Only the fixed experiment runtime is mounted. Agent containers have no host
workspace, evaluator, administrative broker token, or provider key access.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import json
from pathlib import Path
import secrets
import subprocess
import threading
from prepare import ROOT, save

IMAGE = 'sha256:9fff76673f01c927d531e7c8e0891240c1c9509cf845865e3965edba5ae4ee0d'
RUNTIME = '/mnt/d/campus_re/cl-memory-exp/experiments/clbench_memory_systems_20261004/native-runtime'


def main():
    token = secrets.token_hex(32); owned = {}; jobs = {}; lock = threading.Lock()
    def docker(args, *, data=None, timeout=120):
        return subprocess.run(['wsl', '-d', 'Ubuntu', '-u', 'root', '--exec', 'docker', *args],
                              input=data, capture_output=True, timeout=timeout)
    def checked(args, **kwargs):
        p = docker(args, **kwargs)
        if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace')[:2000])
        return p.stdout
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            if not secrets.compare_digest(self.headers.get('X-Broker-Token', ''), token):
                self.send_error(403); return
            try:
                n = int(self.headers['Content-Length'])
                if not 0 < n <= 32 * 1024 * 1024: raise ValueError('Request size')
                v = json.loads(self.rfile.read(n)); op = v['op']
                if op == 'create':
                    name = 'clmem-native-' + secrets.token_hex(8)
                    volume = name + '-state'
                    checked(['volume', 'create', '--label', 'clbench-memory-study=20261004', volume])
                    container = checked(['run', '-d', '--name', name,
                        '--label', 'clbench-memory-study=20261004', '--network', 'clmem-internal',
                        '--read-only', '--tmpfs', '/tmp:rw,size=1g,mode=1777',
                        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=2g', '--pids-limit=512',
                        '--mount', f'type=volume,src={volume},dst=/state',
                        '--mount', f'type=bind,src={RUNTIME},dst=/runtime,readonly',
                        IMAGE, 'sleep', '86400']).decode().strip()
                    # Empty volume only; subsequent model processes run as uid 1000.
                    checked(['exec', '--user', '0', container, 'sh', '-c',
                             'mkdir -p /state/home /state/work /state/tasks && chmod 777 /state /state/home /state/work /state/tasks'])
                    with lock: owned[container] = {'name': name, 'volume': volume}
                    result = {'container_id': container, 'volume': volume}
                else:
                    c = v['container_id']
                    if c not in owned: raise ValueError('Not experiment-owned')
                    if op == 'put':
                        path = v['path']
                        if not path.startswith('/state/') or '..' in path or '\x00' in path: raise ValueError('Invalid path')
                        checked(['exec', '-i', '--user', '1000:1000', c, 'python', '-c',
                            'import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(sys.stdin.buffer.read())', path],
                            data=base64.b64decode(v['data'], validate=True))
                        result = {'written': True}
                    elif op == 'launch':
                        task = v['task']
                        if not task.replace('-', '').isalnum(): raise ValueError('Invalid task')
                        job = secrets.token_hex(16)
                        proc = subprocess.Popen(['wsl', '-d', 'Ubuntu', '-u', 'root', '--exec', 'docker',
                            'exec', '--user', '1000:1000', '-w', '/state/work', c,
                            'python', '/runtime/native_entry.py', f'/state/tasks/{task}/input.json'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        jobs[job] = {'container': c, 'process': proc, 'output': None}
                        # Drain pipes immediately, including long native stream JSON.
                        def drain(): jobs[job]['output'] = proc.communicate()
                        threading.Thread(target=drain, daemon=True).start()
                        result = {'job_id': job}
                    elif op == 'poll':
                        entry = jobs[v['job_id']]
                        if entry['container'] != c: raise ValueError('Wrong job owner')
                        result = {'running': entry['output'] is None, 'exit_code': entry['process'].poll()}
                        if entry['output'] is not None:
                            result.update(stdout=entry['output'][0].decode(errors='replace'),
                                          stderr=entry['output'][1].decode(errors='replace'))
                    elif op == 'snapshot':
                        blob = checked(['exec', '--user', '1000:1000', c, 'tar', '-C', '/state', '-czf', '-', '.'], timeout=120)
                        result = {'data': base64.b64encode(blob).decode()}
                    elif op == 'stop':
                        checked(['stop', '--timeout', '5', c]); result = {'stopped': True, 'volume_preserved': True}
                    elif op == 'remove':
                        if any(j['container'] == c and j['output'] is None for j in jobs.values()):
                            raise ValueError('Active native jobs')
                        checked(['rm', '-f', c]); del owned[c]
                        # Retain named state volume for recovery; never recursive host delete.
                        result = {'removed': True, 'volume_preserved': True}
                    else: raise ValueError('Unknown operation')
                if op in {'create', 'remove'}:
                    with lock: save(ROOT / '.local/native-owned.json', owned)
                data = json.dumps(result).encode(); self.send_response(200)
            except Exception as exc:
                data = json.dumps({'error': type(exc).__name__, 'message': str(exc)}).encode(); self.send_response(400)
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    save(ROOT / '.local/native-broker.json', {'url': f'http://127.0.0.1:{server.server_port}', 'token': token})
    print('Native container broker ready; real provider credentials are not loaded.', flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
