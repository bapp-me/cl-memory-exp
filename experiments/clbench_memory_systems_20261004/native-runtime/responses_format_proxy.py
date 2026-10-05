"""Literal JSON-fence interoperability for a native Responses JSON-schema call.

No prompts, fields, values, reasoning, or usage are synthesized. Invalid JSON is
passed through unchanged. Raw provider bytes remain captured by the host relay.
"""
from collections import defaultdict
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import json
import re
import threading
from urllib.request import Request,urlopen
from urllib.error import HTTPError


def unwrap(text):
    match=re.fullmatch(r'\s*```(?:json)?\s*\n(.*)\n```\s*',text,re.DOTALL)
    if not match:return text
    inner=match.group(1)
    try:value=json.loads(inner)
    except (ValueError,TypeError):return text
    return inner if isinstance(value,dict) else text


def normalize(raw):
    blocks=raw.decode().split('\n\n');events=[];texts=defaultdict(str)
    for block in blocks:
        data=next((x[6:] for x in block.splitlines() if x.startswith('data: ')),None)
        try:value=json.loads(data) if data else None
        except ValueError:value=None
        events.append((block,value))
        if isinstance(value,dict) and value.get('type')=='response.output_text.delta':
            key=(value.get('item_id'),value.get('output_index'),value.get('content_index'))
            texts[key]+=value.get('delta','')
    replacements={text:unwrap(text) for text in texts.values() if unwrap(text)!=text}
    if not replacements:return raw,0
    emitted=set();result=[]
    def visit(value):
        if isinstance(value,dict):
            return {k:(replacements.get(v,v) if k=='text' and isinstance(v,str) else visit(v)) for k,v in value.items()}
        if isinstance(value,list):return [visit(x) for x in value]
        return value
    for block,value in events:
        if not isinstance(value,dict):result.append(block);continue
        if value.get('type')=='response.output_text.delta':
            key=(value.get('item_id'),value.get('output_index'),value.get('content_index'))
            if texts.get(key) in replacements:
                if key in emitted:continue
                emitted.add(key);value['delta']=replacements[texts[key]]
        value=visit(value)
        lines=[('data: '+json.dumps(value,ensure_ascii=False)) if x.startswith('data: ') else x for x in block.splitlines()]
        result.append('\n'.join(lines))
    return '\n\n'.join(result).encode(),len(replacements)


def start(cfg,out):
    lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0'
        def log_message(self,*args):pass
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']));payload=json.loads(body)
            headers={k:v for k,v in self.headers.items() if k.lower() not in {'host','content-length','connection'}}
            request=Request(cfg['gateway']+self.path,data=body,headers=headers)
            try:upstream=urlopen(request,timeout=300)
            except HTTPError as exc:upstream=exc
            with upstream:
                self.send_response(upstream.code)
                self.send_header('Content-Type',upstream.headers.get('Content-Type','application/json'))
                self.end_headers()
                schema=payload.get('text',{}).get('format',{}).get('type')=='json_schema'
                if schema:
                    raw=upstream.read();forwarded,count=normalize(raw)
                    with lock:
                        with (out/'format-envelope-audit.jsonl').open('a') as stream:
                            stream.write(json.dumps({'kind':'literal_json_fence_only','normalized_outputs':count,
                                'raw_sha256':hashlib.sha256(raw).hexdigest(),
                                'forwarded_sha256':hashlib.sha256(forwarded).hexdigest(),
                                'usage_unchanged':True,'no_model_call_added':True})+'\n')
                    self.wfile.write(forwarded);self.wfile.flush()
                else:
                    while chunk:=upstream.read1(16384):self.wfile.write(chunk);self.wfile.flush()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return f'http://127.0.0.1:{server.server_port}'
