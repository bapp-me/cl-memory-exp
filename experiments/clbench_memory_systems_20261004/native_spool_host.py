"""Ordinary-identity host pump for the isolated native relay; no key forwarding."""
import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from prepare import ROOT, read

spool = ROOT / '.local/native-spool'; spool.mkdir(exist_ok=True)
seen = set()


def serve(job):
    request = read(job / 'request.json')
    headers = {k: v for k,v in request['headers'].items() if k.lower() not in {'host','connection','content-length'}}
    req = Request('http://172.21.16.1:43191' + request['path'], data=(job / 'body.bin').read_bytes(), headers=headers)
    def meta(status, content_type):
        p = job / 'response.tmp'; p.write_text(json.dumps({'status': status, 'content_type': content_type}))
        p.replace(job / 'response.json')
    try:
        try: response = urlopen(req, timeout=630)
        except HTTPError as exc: response = exc
        with response, (job / 'response.bin').open('wb') as output:
            meta(response.code, response.headers.get('Content-Type', 'application/json'))
            while data := response.read1(16384): output.write(data); output.flush()
    except Exception as exc:
        if not (job / 'response.json').exists():
            (job / 'response.bin').write_text(json.dumps({'error': type(exc).__name__}))
            meta(502, 'application/json')
    finally: (job / 'done').write_text('done')


print('Native spool pump ready; no inbound Windows firewall rule required.', flush=True)
while True:
    for item in spool.glob('*/request.json'):
        if item.parent.name not in seen:
            seen.add(item.parent.name)
            if not (item.parent / 'done').exists(): threading.Thread(target=serve, args=(item.parent,), daemon=True).start()
    time.sleep(.05)
