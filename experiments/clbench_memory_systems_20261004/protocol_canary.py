"""One small request per verified Z.AI protocol using the existing credential.

Never transmits this credential to another hostname. Raw bodies are private;
headers and secrets are never persisted. No automatic retry or model fallback.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import uuid
from prepare import ROOT, save, read

MODEL = 'glm-5.3-flash'


def secret():
    # Reuse the verified loader without importing the legacy experiment runtime.
    code = ROOT.parent / 'section7_observability_20261002/engine.py'
    tree = ast.parse(code.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'secret')
    namespace = {'os': os, 'Path': Path, 'subprocess': subprocess}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(code), 'exec'), namespace)
    return namespace['secret']()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol', choices=['chat', 'responses', 'anthropic'], required=True)
    parser.add_argument('--window', action='store_true', help='Isolated near-256k provider input probe, no benchmark content')
    args = parser.parse_args()
    authorization = read(ROOT / 'records/execution-authorization.json')
    if authorization.get('monetary_policy') != 'user_authorized_no_additional_cap':
        raise RuntimeError('Current batch authorization missing')
    prompt = 'This is an isolated protocol connectivity test. Reply with exactly OK.'
    if args.window:
        prompt = 'Ignore the repeated filler below.\n' + (' cat' * 245000) + '\nReply with exactly OK.'
    definitions = {
        'chat': ('https://api.z.ai/api/paas/v4/chat/completions',
                 {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}],
                  'max_tokens': 2048, 'reasoning_effort': 'high', 'thinking': {'type': 'enabled'}}),
        'responses': ('https://api.z.ai/api/v1/responses',
                      {'model': MODEL, 'input': [{'role': 'user', 'content': prompt}],
                       'max_output_tokens': 2048, 'reasoning': {'effort': 'high'}, 'store': False}),
        'anthropic': ('https://api.z.ai/api/anthropic/v1/messages',
                      {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}],
                       'max_tokens': 2048}),
    }
    endpoint, body = definitions[args.protocol]
    if urlparse(endpoint).hostname != 'api.z.ai':
        raise ValueError('Unexpected credential destination')
    key = secret()
    out = ROOT / 'private-runs' / ('protocol-canary-' + args.protocol + '-' + uuid.uuid4().hex)
    out.mkdir(parents=True)
    attempt_id = uuid.uuid4().hex
    started = time.monotonic()
    event = {'attempt_id': attempt_id, 'call_id': attempt_id, 'role': 'protocol_canary',
             'protocol': args.protocol, 'endpoint': endpoint, 'requested_model': MODEL,
             'created_at': datetime.now(timezone.utc).isoformat(), 'retry': False,
             'account': 'existing_zai', 'prompt_bytes': len(prompt.encode()), 'http_status': None}
    save(out / 'request.json', body)
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}
    if args.protocol == 'anthropic':
        headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
    try:
        req = Request(endpoint, data=json.dumps(body).encode(), headers=headers)
        with urlopen(req, timeout=90) as response:
            event['http_status'] = response.status
            raw = response.read().decode('utf-8')
    except HTTPError as exc:
        event['http_status'] = exc.code
        raw = exc.read().decode('utf-8', errors='replace')
    except Exception as exc:
        raw = json.dumps({'transport_error': type(exc).__name__, 'message': str(exc)})
    raw = raw.replace(key, '[REDACTED]')
    (out / 'response.txt').write_text(raw, encoding='utf-8')
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    event.update({'seconds': round(time.monotonic() - started, 3),
                  'returned_model': data.get('model'), 'usage': data.get('usage'),
                  'error': data.get('error', data.get('transport_error')),
                  'response_status': data.get('status'),
                  'raw_evidence': out.relative_to(ROOT).as_posix()})
    event['identity_passed'] = event['http_status'] == 200 and str(data.get('model', '')).lower() == MODEL
    usage = data.get('usage') or {}
    input_tokens = usage.get('prompt_tokens', usage.get('input_tokens'))
    event['probe'] = 'near_256k_input' if args.window else 'identity'
    event['context_window_verified'] = bool(args.window and event['identity_passed']
        and isinstance(input_tokens, int) and 240000 <= input_tokens <= 262144 - 2048)
    event['framework_acceptance'] = False
    save(out / 'attempt.json', event)
    save(ROOT / 'records' / ('protocol-' + args.protocol + ('-window' if args.window else '') + '.json'), event)
    print(json.dumps(event, ensure_ascii=True))


if __name__ == '__main__':
    main()
