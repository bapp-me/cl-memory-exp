"""One shared all-role HTTP request semaphore for the study; no model keys."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import argparse
import secrets
import threading
import time
from prepare import ROOT, read, save


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ceiling',type=int)
    args=parser.parse_args()
    historical_ceiling = read(ROOT / 'records/execution-authorization.json')['global_request_ceiling']
    ceiling = args.ceiling or historical_ceiling
    if not 1 <= ceiling <= historical_ceiling:
        raise ValueError('Request ceiling must stay within the existing maximum')
    semaphore = threading.BoundedSemaphore(ceiling)
    token = secrets.token_hex(32)
    leases = {}; lock = threading.Lock(); peak = 0
    output = ROOT / '.local/request-gate-events.jsonl'
    def log(value):
        with output.open('a', encoding='utf-8') as stream: stream.write(json.dumps(value) + '\n')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            nonlocal peak
            if not secrets.compare_digest(self.headers.get('X-Gate-Token', ''), token):
                self.send_error(403); return
            value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path == '/acquire':
                started = time.monotonic(); semaphore.acquire()
                lease = secrets.token_hex(16)
                with lock:
                    leases[lease] = value
                    peak = max(peak, len(leases))
                    result = {'lease': lease, 'active': len(leases), 'ceiling': ceiling,
                              'wait_seconds': time.monotonic() - started}
                    log({'event': 'acquire', 'at': time.time(), **value, **result})
            elif self.path == '/release':
                with lock:
                    lease = value.get('lease')
                    if lease not in leases:
                        self.send_error(409); return
                    del leases[lease]; semaphore.release()
                    result = {'released': True, 'active': len(leases)}
                    log({'event': 'release', 'at': time.time(), 'lease': lease, **result})
            elif self.path == '/status':
                with lock: result = {'active': len(leases), 'peak': peak, 'ceiling': ceiling}
            else:
                self.send_error(404); return
            body = json.dumps(result).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    save(ROOT / '.local/request-gate.json', {'url': f'http://127.0.0.1:{server.server_port}', 'token': token,
                                          'ceiling': ceiling})
    print(f'Shared study request gate ready; ceiling={ceiling}; no model credentials.', flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
