"""Fixed Z.ai native chat-completions recorder with documented reasoning parameters."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class NativeProxy:
    def __init__(self, model, key, directory, max_requests=24):
        self.directory, self.model, self.key = directory, model, key
        self.count, self.max_requests = 0, max_requests
        self.lock = threading.Lock()
        directory.mkdir(parents=True, exist_ok=True)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                if self.path != '/chat/completions':
                    self.send_error(404)
                    return
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                with owner.lock:
                    owner.count += 1
                    n = owner.count
                if n > owner.max_requests or payload.get('model') != model:
                    self.send_error(400, 'Model or request guard')
                    return
                native = {k: payload.get(k) for k in ('model', 'thinking', 'reasoning_effort', 'max_tokens', 'stream')}
                payload['thinking'] = {'type': 'enabled', 'clear_thinking': False}
                payload['reasoning_effort'] = 'high'
                payload['max_tokens'] = 32768
                payload['stream_options'] = {'include_usage': True}
                (directory / f'{n:03d}-request.json').write_text(json.dumps({'path': self.path, 'native_parameters': native, 'effective_payload': payload}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                request = Request('https://api.z.ai/api/paas/v4/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
                started = time.monotonic()
                status, error, chunks = None, None, []
                try:
                    with urlopen(request, timeout=180) as response:
                        status = response.status
                        self.send_response(status)
                        self.send_header('Content-Type', response.headers.get('Content-Type', 'text/event-stream'))
                        self.end_headers()
                        while chunk := response.read1(16384):
                            chunks.append(chunk)
                            self.wfile.write(chunk)
                            self.wfile.flush()
                except HTTPError as exc:
                    status = exc.code
                    data = exc.read()
                    chunks.append(data)
                    self.send_response(status)
                    self.end_headers()
                    self.wfile.write(data)
                except Exception as exc:
                    error = str(exc).replace(key, '[REDACTED]')
                    if status is None:
                        self.send_error(502, 'Upstream transport failed')
                text = b''.join(chunks).decode('utf-8', errors='replace').replace(key, '[REDACTED]')
                (directory / f'{n:03d}-response.txt').write_text(text, encoding='utf-8')
                usage, raw = [], []
                for line in text.splitlines():
                    if not line.startswith('data: '):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except ValueError:
                        continue
                    u = event.get('usage')
                    if u:
                        raw.append(u)
                        cached = u.get('prompt_tokens_details', {}).get('cached_tokens', 0)
                        usage.append({'input_tokens': u.get('prompt_tokens', 0) - cached, 'cache_read_input_tokens': cached, 'output_tokens': u.get('completion_tokens', 0), 'cache_creation_input_tokens': 0})
                row = {'request': n, 'path': self.path, 'model': model, 'status': status, 'seconds': round(time.monotonic() - started, 3), 'usage_events': usage, 'native_usage_events': raw, 'error': error}
                with owner.lock:
                    with (directory / 'ledger.jsonl').open('a', encoding='utf-8') as file:
                        file.write(json.dumps(row) + '\n')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
