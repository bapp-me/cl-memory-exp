"""Internal-only HTTP relay using a host-polled spool, without firewall changes.

WSL never receives provider credentials. Agent containers cannot mount the
spool. Native SSE bytes are streamed unchanged through append-only files.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).resolve().parent / '.local/native-spool'
ROOT.mkdir(exist_ok=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self): self.send_error(404)
    def do_POST(self):
        job = ROOT / uuid.uuid4().hex; job.mkdir()
        n = int(self.headers.get('Content-Length', '0'))
        if not 0 < n <= 32 * 1024 * 1024: self.send_error(413); return
        (job / 'body.bin').write_bytes(self.rfile.read(n))
        temp = job / 'request.tmp'
        temp.write_text(json.dumps({'path': self.path, 'headers': dict(self.headers)}))
        temp.rename(job / 'request.json')
        deadline = time.monotonic() + 660
        while not (job / 'response.json').exists():
            if time.monotonic() > deadline: self.send_error(504); return
            time.sleep(.05)
        meta = json.loads((job / 'response.json').read_text())
        self.send_response(meta['status']); self.send_header('Content-Type', meta['content_type']); self.end_headers()
        with (job / 'response.bin').open('rb') as output:
            while True:
                data = output.read(65536)
                if data: self.wfile.write(data); self.wfile.flush()
                elif (job / 'done').exists(): break
                else: time.sleep(.05)


ThreadingHTTPServer(('172.30.0.1', 43191), Handler).serve_forever()
