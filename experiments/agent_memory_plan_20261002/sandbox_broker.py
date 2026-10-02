"""Elevated sandbox access only; no credential loading or model network calls.

Default controller owns DPAPI identity. The broker only runs three fixed Python
entrypoints inside declared experiment-private namespace sandboxes.
"""
import json
import secrets
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from core import ROOT,sandbox,save

TOKEN=secrets.token_urlsafe(32)
ALLOWED=[['/usr/bin/python3','/work/probe.py'],
         ['/bin/sh','-c','cd /work && python3 scratch.py'],
         ['/bin/sh','-c','cd /work && python3 evaluate.py']]

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        if self.headers.get('X-Broker-Token')!=TOKEN:
            self.send_error(403);return
        value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        work=Path(value['work']).resolve()
        permitted=[ROOT/'.runtime/workspaces',ROOT/'.runtime/evaluators',ROOT/'.runtime/sandbox-canary']
        if not any(work==p.resolve() or work.is_relative_to(p.resolve()) for p in permitted) or value['command'] not in ALLOWED:
            self.send_error(403);return
        result=sandbox(work,value['command'],timeout=min(int(value.get('timeout',120)),120),direct=True)
        body=json.dumps(result).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    save(ROOT/'.runtime/sandbox-broker.json',{'url':f'http://127.0.0.1:{server.server_port}','token':TOKEN})
    print('Sandbox broker listening on loopback; credentials are not loaded.',flush=True)
    server.serve_forever()
