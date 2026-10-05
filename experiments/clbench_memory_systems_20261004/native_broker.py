"""Credential-free container lifecycle for the three native frameworks.

Only the fixed experiment runtime is mounted. Agent containers have no host
workspace, evaluator, administrative broker token, or provider key access.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import json
import re
import hashlib
import argparse
import io
import tarfile
from pathlib import Path
import secrets
import subprocess
import threading
from prepare import ROOT, save

IMAGE = 'sha256:9fff76673f01c927d531e7c8e0891240c1c9509cf845865e3965edba5ae4ee0d'
RUNTIME = '/mnt/d/campus_re/cl-memory-exp/experiments/clbench_memory_systems_20261004/native-runtime'


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--kind',choices=['default','codex'],default='default')
    args=parser.parse_args(); suffix='' if args.kind=='default' else '-codex'
    binary_mount=[]
    if args.kind=='codex':
        from prepare import read
        expected=read(ROOT/'records/codex-build.json')['binary_sha256']
        if hashlib.sha256((ROOT/'.local/native-bin/codex').read_bytes()).hexdigest()!=expected:
            raise ValueError('Codex binary hash mismatch')
        binary_mount=['--mount','type=bind,src='+RUNTIME.rsplit('/',1)[0]+'/.local/native-bin,dst=/native,readonly']
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
                    runtime = RUNTIME
                    if fingerprint := v.get('runtime_hash'):
                        if not re.fullmatch(r'[a-f0-9]{64}',fingerprint): raise ValueError('Invalid runtime hash')
                        directory=ROOT/'.local/native-runtime-builds'/fingerprint
                        inventory={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob('*.py'))}
                        if hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()!=fingerprint:
                            raise ValueError('Native runtime snapshot mismatch')
                        runtime=RUNTIME.rsplit('/',1)[0]+'/.local/native-runtime-builds/'+fingerprint
                    name = 'clmem-native-' + secrets.token_hex(8)
                    volume = name + '-state'
                    checked(['volume', 'create', '--label', 'clbench-memory-study=20261004', volume])
                    container = checked(['run', '-d', '--name', name,
                        '--label', 'clbench-memory-study=20261004', '--network', 'clmem-internal',
                        '--read-only', '--tmpfs', '/tmp:rw,size=1g,mode=1777',
                        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=2g', '--pids-limit=512',
                        '--mount', f'type=volume,src={volume},dst=/state',
                        '--mount', f'type=bind,src={runtime},dst=/runtime,readonly',
                        *binary_mount, IMAGE, 'sleep', '86400']).decode().strip()
                    # Empty volume only; subsequent model processes run as uid 1000.
                    checked(['exec', '--user', '0', container, 'sh', '-c',
                             'mkdir -p /state/home /state/work /state/tasks && chmod 777 /state /state/home /state/work /state/tasks'])
                    with lock: owned[container] = {'name': name, 'volume': volume}
                    result = {'container_id': container, 'volume': volume}
                else:
                    c = v['container_id']
                    if c not in owned: raise ValueError('Not experiment-owned')
                    if op == 'restore':
                        blob=base64.b64decode(v['data'],validate=True)
                        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
                            for member in tar.getmembers():
                                parts=Path(member.name).parts
                                if member.name.startswith('/') or '..' in parts or not (member.isfile() or member.isdir()):
                                    raise ValueError('Unsafe state archive member')
                        checked(['exec','-i','--user','1000:1000',c,'tar','-C','/state','-xzf','-'],data=blob)
                        result={'restored':True,'archive_sha256':hashlib.sha256(blob).hexdigest()}
                    elif op == 'quiesce':
                        # Stop only unprivileged agents inside this owned container;
                        # leave its root sleep alive so a settled snapshot is possible.
                        code='''import os,signal,time
from pathlib import Path
def targets():
 found=[]
 for p in Path('/proc').iterdir():
  try:
   if p.name.isdigit() and int(p.name)!=os.getpid() and p.stat().st_uid==os.getuid():found.append(int(p.name))
  except FileNotFoundError:pass
 return found
for sig in [signal.SIGTERM,signal.SIGKILL]:
 for pid in targets():
  try:os.kill(pid,sig)
  except ProcessLookupError:pass
 time.sleep(1)
'''
                        # CAP_KILL is intentionally absent; signal peers as uid 1000.
                        checked(['exec','--user','1000:1000',c,'python','-c',code])
                        result={'quiesced':True}
                    elif op == 'put':
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
                    with lock: save(ROOT / f'.local/native-owned{suffix}.json', owned)
                data = json.dumps(result).encode(); self.send_response(200)
            except Exception as exc:
                data = json.dumps({'error': type(exc).__name__, 'message': str(exc)}).encode(); self.send_response(400)
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    save(ROOT / f'.local/native-broker{suffix}.json', {'url': f'http://127.0.0.1:{server.server_port}', 'token': token})
    print('Native container broker ready; real provider credentials are not loaded.', flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
