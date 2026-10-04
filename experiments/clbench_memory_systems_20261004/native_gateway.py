"""Run-scoped native protocol relay. Real credentials stay in the ordinary host.

Agent containers can reach this endpoint only through an internal Docker relay.
No protocol conversion, framework prompts, answers or memory synthesis here.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import secrets
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import uuid
from prepare import ROOT, read, save
from protocol_canary import secret

DESTINATIONS = {'chat': 'https://api.z.ai/api/paas/v4/chat/completions',
                'responses': 'https://api.z.ai/api/v1/responses',
                'anthropic': 'https://api.z.ai/api/anthropic/v1/messages'}


def gate(operation, payload):
    settings = read(ROOT / '.local/request-gate.json')
    req = Request(settings['url'] + '/' + operation, data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'X-Gate-Token': settings['token']})
    with urlopen(req, timeout=600) as response: return json.load(response)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--bind', required=True); parser.add_argument('--port', type=int, default=43191)
    args = parser.parse_args()
    key = secret()
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'
        def log_message(self, *_): pass
        def do_GET(self):
            self.record_unhandled(); self.send_error(404)
        def record_unhandled(self):
            with lock:
                with (ROOT / '.local/native-gateway-unhandled.jsonl').open('a', encoding='utf-8') as log:
                    log.write(json.dumps({'method': self.command, 'path': self.path,
                        'at': datetime.now(timezone.utc).isoformat()}) + '\n')
        def do_POST(self):
            parsed = urlsplit(self.path)
            match = re.fullmatch(r'/r/([a-f0-9]{32})/(chat/completions|responses|v1/messages|tool)', parsed.path)
            if not match: self.record_unhandled(); self.send_error(404); return
            route_id, operation = match.groups()
            route_file = ROOT / '.local/native-routes' / f'{route_id}.json'
            if not route_file.is_file(): self.send_error(404); return
            route = read(route_file)
            if route.get('disabled'): self.send_error(410, 'Run route stopped'); return
            supplied = self.headers.get('Authorization', '').removeprefix('Bearer ') or self.headers.get('x-api-key', '')
            if not secrets.compare_digest(supplied, route['token']): self.send_error(403); return
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 32 * 1024 * 1024: self.send_error(413); return
            raw = self.rfile.read(length)
            if operation == 'tool':
                req = Request(route['tool_url'], data=raw,
                    headers={'Content-Type': 'application/json', 'X-Run-Token': route['tool_token']})
                try:
                    with urlopen(req, timeout=600) as response: data, status = response.read(), response.status
                except HTTPError as exc: data, status = exc.read(), exc.code
                self.send_response(status); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
                return
            protocol = {'chat/completions': 'chat', 'responses': 'responses', 'v1/messages': 'anthropic'}[operation]
            payload = json.loads(raw)
            if payload.get('model') != 'glm-5.3-flash': self.send_error(422, 'Undeclared model route'); return
            attempt = uuid.uuid4().hex
            out = ROOT / route['audit_relative_path'] / 'requests'
            if not out.resolve().is_relative_to((ROOT / 'private-runs').resolve()): self.send_error(403); return
            out.mkdir(parents=True, exist_ok=True)
            output_key = 'max_output_tokens' if protocol == 'responses' else 'max_tokens'
            # An explicit integration setting, captured before and after mapping.
            # Preserve a tighter native auxiliary budget rather than inflating it.
            configured_limit = int(route.get('output_limit', 16384))
            payload[output_key] = min(int(payload.get(output_key) or configured_limit), configured_limit)
            meta = {'attempt_id': attempt, 'call_id': attempt, 'run_id': route['run_id'],
                'method_id': route['method_id'], 'instance_id': route.get('instance_id'),
                'project_key': route.get('project_key'), 'session_id': route.get('session_id'),
                'agent_id': None, 'parent_agent_id': None, 'role': route.get('phase', 'unknown_native_role'),
                'config_hash': route.get('config_hash'), 'protocol': protocol,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'request_correlation_headers': {h: self.headers[h] for h in ['session_id', 'x-session-id', 'x-client-request-id'] if self.headers.get(h)}}
            permit = gate('acquire', meta)
            save(out / f'{attempt}.native-request.json', json.loads(raw))
            save(out / f'{attempt}.request.json', payload)
            save(out / f'{attempt}.attempt.json', {**meta, 'phase': 'started', 'gate_wait_seconds': permit['wait_seconds']})
            headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}
            if protocol == 'anthropic':
                headers.update({'x-api-key': key, 'anthropic-version': self.headers.get('anthropic-version', '2023-06-01')})
                if self.headers.get('anthropic-beta'): headers['anthropic-beta'] = self.headers['anthropic-beta']
            started = time.monotonic(); status = None; error = None
            try:
                req = Request(DESTINATIONS[protocol], data=json.dumps(payload).encode(), headers=headers)
                try: response = urlopen(req, timeout=300)
                except HTTPError as exc: response = exc
                with response, (out / f'{attempt}.response.bin').open('wb') as audit:
                    status = response.code
                    self.send_response(status)
                    self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                    self.end_headers()
                    while data := response.read1(16384):
                        # Authentication headers never enter the audit. Defensive
                        # exact-secret removal covers an unexpected server error echo.
                        data = data.replace(key.encode(), b'[REDACTED]')
                        audit.write(data); audit.flush()
                        self.wfile.write(data); self.wfile.flush()
            except Exception as exc:
                error = type(exc).__name__
            finally:
                save(out / f'{attempt}.attempt.json', {**meta, 'phase': 'finished' if error is None else 'failed',
                    'http_status': status, 'error': error, 'seconds': time.monotonic() - started,
                    'gate_wait_seconds': permit['wait_seconds']})
                gate('release', {'lease': permit['lease']})
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    save(ROOT / '.local/native-gateway.json', {'bind': args.bind, 'port': server.server_port,
                                             'account': 'existing_zai', 'credential_value_logged': False})
    print('Native protocol gateway ready on the WSL host interface; credentials remain host-only.', flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
