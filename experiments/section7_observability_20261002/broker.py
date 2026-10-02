"""Restricted loopback broker for the existing WSL namespace sandbox."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
ALLOWED = [['/usr/bin/python3', '/work/probe.py'], ['/bin/sh', '-c', 'cd /work && python3 scratch.py'],
           ['/bin/sh', '-c', 'cd /work && python3 evaluate.py']]


def linux(path):
    value = Path(path).resolve().as_posix()
    return '/mnt/' + value[0].lower() + value[2:]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        if self.headers.get('X-Broker-Token') != TOKEN:
            self.send_error(403)
            return
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        work = Path(data['work']).resolve()
        permitted = [ROOT / '.runtime/workspaces', ROOT / '.runtime/evaluators', ROOT / '.runtime/sandbox-canary']
        if not any(work.is_relative_to(p.resolve()) for p in permitted) or data['command'] not in ALLOWED:
            self.send_error(403)
            return
        mount = ROOT / '.runtime/sandbox-root'
        mount.mkdir(parents=True, exist_ok=True)
        command = ['/python/bin/python3.10' if c == '/usr/bin/python3' else c for c in data['command']]
        cmd = ['wsl.exe', '-d', 'Ubuntu', '--exec', 'unshare', '-Urnmpf', 'sh', linux(ROOT / '.runtime/sandbox.sh'),
               linux(mount), linux(work), '/home/fucak/.cache/agent-memory-plan-20261002/deps310',
               '/home/fucak/.cache/agent-memory-plan-20261002/python310', *command]
        try:
            process = subprocess.run(cmd, capture_output=True, timeout=min(int(data.get('timeout', 120)), 120))
            result = {'returncode': process.returncode, 'stdout': process.stdout.decode(errors='replace')[-24000:],
                      'stderr': process.stderr.decode(errors='replace')[-24000:]}
        except subprocess.TimeoutExpired:
            result = {'returncode': 124, 'stdout': '', 'stderr': 'sandbox wall timeout'}
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    state = ROOT / '.runtime/sandbox-broker.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'token': TOKEN}), encoding='utf-8')
    print('Section 7 sandbox broker ready on loopback; no model or credential access.', flush=True)
    server.serve_forever()
