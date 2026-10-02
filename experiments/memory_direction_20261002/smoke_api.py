"""Tiny authenticated probes, with no retry loop or secret-bearing logs."""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from lab_common import ROOT, get_secret, save_json


def request(provider, url, payload=None):
    key = get_secret(provider)
    started = time.monotonic()
    record = {'provider': provider, 'url': url, 'at': datetime.now(timezone.utc).isoformat()}
    raw = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=raw, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=100) as response:
            data = json.load(response)
        record.update(status=200, data=data)
    except HTTPError as error:
        record.update(status=error.code, error=error.read().decode('utf-8', errors='replace')[:1800])
    except (URLError, TimeoutError) as error:
        record.update(status='transport_error', error=str(error))
    record['seconds'] = round(time.monotonic() - started, 3)
    # Remove any echoed credential, including unexpected upstream error bodies.
    record = json.loads(json.dumps(record).replace(key, '[REDACTED]'))
    return record


def main():
    records = []
    balance = request('deepseek', 'https://api.deepseek.com/user/balance')
    records.append(balance)
    save_json(ROOT / '.private/deepseek-balance-before.json', balance)
    ds = request('deepseek', 'https://api.deepseek.com/chat/completions', {
        'model': 'deepseek-flash', 'messages': [{'role': 'user', 'content': 'Reply with exactly OK.'}],
        'thinking': {'type': 'enabled'}, 'reasoning_effort': 'high', 'max_tokens': 512,
    })
    records.append(ds)
    payload = {'model': 'glm-5.3-flash', 'messages': [{'role': 'user', 'content': 'Reply with exactly OK.'}],
               'thinking': {'type': 'enabled'}, 'reasoning_effort': 'high', 'max_tokens': 512}
    glm = request('glm', 'https://api.z.ai/api/paas/v4/chat/completions', payload)
    records.append(glm)
    if glm['status'] in (401, 403):
        records.append(request('glm', 'https://open.bigmodel.cn/api/paas/v4/chat/completions', payload))
    # Account balance is private, while request outcome and token usage are public experiment evidence.
    public = [r for r in records if not r['url'].endswith('/balance')]
    save_json(ROOT / 'results/api-smoke.json', public)
    for r in public:
        d = r.get('data', {})
        print(json.dumps({'provider': r['provider'], 'url':r['url'], 'status': r['status'],
                          'model': d.get('model'), 'usage': d.get('usage'), 'seconds': r['seconds'],
                          'error': r.get('error')}, ensure_ascii=True))


if __name__ == '__main__':
    main()
