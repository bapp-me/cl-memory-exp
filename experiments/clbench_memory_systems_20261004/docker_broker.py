"""Credential-free elevated Windows/WSL bridge for experiment-owned containers.

Only the ordinary controller can access its local authentication token. Model
processes receive separate business/model tokens, never this administrative one.
"""
from __future__ import annotations
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import threading
from prepare import ROOT, read, save


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--port', type=int, default=0); args = parser.parse_args()
    token = secrets.token_hex(32)
    owned = set()
    lock = threading.Lock()
    images = read(ROOT / 'records/docker-images.json')['images']
    allowed_images = set(images.values())
    def docker(argv, timeout=120, data=None):
        process = subprocess.run(['wsl.exe', '-d', 'Ubuntu', '-u', 'root', '--exec', 'docker', *argv],
            input=data, capture_output=True, timeout=timeout)
        return {'returncode': process.returncode, 'stdout': process.stdout.decode('utf-8', errors='replace'),
                'stderr': process.stderr.decode('utf-8', errors='replace')}
    def require_owned(container):
        if container not in owned: raise ValueError('Container outside this broker ownership')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            if not secrets.compare_digest(self.headers.get('X-Broker-Token', ''), token):
                self.send_error(403); return
            try:
                length = int(self.headers['Content-Length'])
                if not 0 < length <= 32 * 1024 * 1024: raise ValueError('Invalid request size')
                request = json.loads(self.rfile.read(length))
                op = request['op']; timeout = min(int(request.get('timeout', 120)), 1800)
                if op == 'create':
                    if request['image'] not in allowed_images: raise ValueError('Unpinned image')
                    name = 'clmem-' + secrets.token_hex(8)
                    argv = ['run', '-d', '--name', name, '--label', 'clbench-memory-study=20261004',
                        '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                        '--memory=2g', '--pids-limit=256', '-w', request.get('cwd', '/testbed'),
                        request['image'], 'sleep', '86400']
                    result = docker(argv, timeout)
                    if result['returncode'] == 0:
                        container = result['stdout'].strip()
                        with lock: owned.add(container)
                        result['container_id'] = container
                elif op == 'exec':
                    container = request['container_id']; require_owned(container)
                    argv = ['exec', '-w', request.get('cwd', '/testbed'), container,
                            'bash', '-lc', request['command']]
                    result = docker(argv, timeout)
                elif op == 'put':
                    container = request['container_id']; require_owned(container)
                    target = request['path']
                    if not target.startswith(('/tmp/clmem-', '/tmp/clbench_patch_')) or '..' in target: raise ValueError('Upload must use private patch staging path')
                    result = docker(['exec', '-i', container, 'sh', '-c', 'cat > "$1"', 'sh', target],
                                    timeout, base64.b64decode(request['data'], validate=True))
                elif op == 'remove':
                    container = request['container_id']; require_owned(container)
                    result = docker(['rm', '-f', container], timeout)
                    if result['returncode'] == 0:
                        with lock: owned.remove(container)
                elif op == 'health': result = {'owned_count': len(owned)}
                else: raise ValueError('Unknown broker operation')
                with lock: save(ROOT / '.local/docker-owned.json', {'containers': sorted(owned)})
                data = json.dumps(result).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
            except Exception as exc:
                data = json.dumps({'error': type(exc).__name__, 'message': str(exc)}).encode()
                self.send_response(400); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    save(ROOT / '.local/docker-broker.json', {'url': f'http://127.0.0.1:{server.server_port}', 'token': token})
    print('Experiment-owned Docker broker ready; no model credentials loaded.', flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
