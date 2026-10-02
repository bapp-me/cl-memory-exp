"""Loopback-only Anthropic transport recorder and per-run request guard.

Credentials are inserted only for the fixed official upstream. Request/response
bodies are recorded, headers are not. The reasoning configuration is explicit
because a third-party model name may not activate Claude's native model profile.
"""
from __future__ import annotations
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from lab_common import save_json


class RecordingProxy:
    def __init__(self, endpoint, model, key, directory, max_requests=24, capture_only=False, max_output_tokens=8192, effort='high'):
        self.endpoint=endpoint;self.model=model;self.key=key;self.directory=directory
        self.max_requests=max_requests;self.count=0;self.lock=threading.Lock()
        self.capture_only=capture_only
        self.max_output_tokens=max_output_tokens
        self.effort=effort
        directory.mkdir(parents=True,exist_ok=True)
        owner=self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass

            def do_POST(self):
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                try:payload=json.loads(body)
                except ValueError:
                    self.send_error(400);return
                with owner.lock:
                    owner.count+=1;n=owner.count
                if n>owner.max_requests:
                    # 429 invites paid-client retry loops; this is a terminal local guard.
                    self.send_error(400,'Experiment request cap reached');return
                if not self.path.split('?')[0].endswith(('/messages','/messages/count_tokens')):
                    self.send_error(404);return
                if payload.get('model')!=owner.model:
                    self.send_error(400,'Unexpected model; fallback is disabled');return
                original={k:payload.get(k) for k in ('model','thinking','output_config','max_tokens','stream')}
                if self.path.split('?')[0].endswith('/messages'):
                    payload['max_tokens']=min(int(payload.get('max_tokens',owner.max_output_tokens)),owner.max_output_tokens)
                    payload['thinking']={'type':'enabled','budget_tokens':4096}
                    payload['output_config']={**payload.get('output_config',{}),'effort':owner.effort}
                save_json(owner.directory/f'{n:03d}-request.json',{'path':self.path,'native_parameters':original,'effective_payload':payload})
                if owner.capture_only:
                    self.send_error(400,'Intentional configuration capture; no upstream request')
                    return
                request=Request(owner.endpoint+self.path,data=json.dumps(payload).encode(),headers={
                    'Content-Type':'application/json','x-api-key':owner.key,
                    'Authorization':'Bearer '+owner.key,
                    'anthropic-version':self.headers.get('anthropic-version','2023-06-01')})
                started=time.monotonic();chunks=[];status=None;error=None
                try:
                    with urlopen(request,timeout=180) as upstream:
                        status=upstream.status;self.send_response(status)
                        self.send_header('Content-Type',upstream.headers.get('Content-Type','application/json'))
                        self.end_headers()
                        while chunk:=upstream.read1(16384):
                            chunks.append(chunk);self.wfile.write(chunk);self.wfile.flush()
                except HTTPError as exc:
                    status=exc.code;data=exc.read();chunks.append(data)
                    self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers()
                    try:self.wfile.write(data)
                    except (BrokenPipeError,ConnectionResetError):pass
                except Exception as exc:
                    error=type(exc).__name__+': '+str(exc)
                    if status is None:
                        try:self.send_error(502,'Upstream transport failed')
                        except (BrokenPipeError,ConnectionResetError):pass
                text=b''.join(chunks).decode('utf-8',errors='replace').replace(owner.key,'[REDACTED]')
                (owner.directory/f'{n:03d}-response.txt').write_text(text,encoding='utf-8')
                usage=[]
                for line in text.splitlines():
                    if line.startswith('data: '):
                        try:
                            event=json.loads(line[6:])
                            if event.get('usage'):usage.append(event['usage'])
                            if event.get('message',{}).get('usage'):usage.append(event['message']['usage'])
                        except ValueError:pass
                row={'request':n,'path':self.path,'model':payload.get('model'),'status':status,
                     'seconds':round(time.monotonic()-started,3),'usage_events':usage,'error':error}
                with owner.lock:
                    with (owner.directory/'ledger.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')

        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.url=f'http://127.0.0.1:{self.server.server_address[1]}'

    def start(self):
        self.thread.start();return self

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
