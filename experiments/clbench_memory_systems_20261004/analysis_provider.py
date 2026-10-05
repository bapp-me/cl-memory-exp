"""User-authorized Aixoras Responses client; no key in logs or git."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from prepare import ROOT, read, save

ENDPOINT = 'https://api.aixoras.com/v1/responses'
MODEL = 'glm-5.3-flash'
PRIVATE = ROOT/'private-analysis/full_observability_20261005'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Provider redirect refused; credential destination is fixed')


def secret():
    path = ROOT/'.local/aixoras-key.dpapi'
    env = dict(os.environ, CLBENCH_AIXORAS_CREDENTIAL=str(path))
    command = "$s=ConvertTo-SecureString -String ((Get-Content -Raw -LiteralPath $env:CLBENCH_AIXORAS_CREDENTIAL).Trim()); $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }"
    value = subprocess.run(['pwsh.exe','-NoProfile','-NonInteractive','-Command',command], env=env, capture_output=True, text=True, check=True).stdout
    if not value.startswith('sk-'):
        raise RuntimeError('Encrypted credential could not be loaded under this execution identity')
    return value.strip()


def call(payload, *, role, unit_id, key=None):
    assert payload['model'] == MODEL and urlsplit(ENDPOINT).hostname == 'api.aixoras.com'
    key = key or secret()
    out = PRIVATE/'requests'; out.mkdir(parents=True, exist_ok=True)
    ident = uuid.uuid4().hex
    save(out/f'{ident}.request.json', payload)
    event = {'attempt_id':ident,'unit_id':unit_id,'role':role,'provider':'aixoras','endpoint':ENDPOINT,
             'requested_model':MODEL,'timestamp':datetime.now(timezone.utc).isoformat(),'phase':'started'}
    save(out/f'{ident}.attempt.json',event)
    raw = b''; started=time.monotonic(); status=None; error=None
    try:
        request=Request(ENDPOINT,data=json.dumps(payload,ensure_ascii=False).encode(),
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
        with build_opener(NoRedirect).open(request, timeout=600) as response:
            status=response.status; raw=response.read()
    except HTTPError as exc:
        status=exc.code; raw=exc.read(); error=type(exc).__name__
    except Exception as exc:
        error=type(exc).__name__
    text=raw.decode('utf8',errors='replace').replace(key,'[REDACTED]')
    (out/f'{ident}.response.txt').write_text(text,encoding='utf8')
    try: data=json.loads(text)
    except json.JSONDecodeError: data={}
    event.update(http_status=status,seconds=round(time.monotonic()-started,3),
                 phase='failed' if error or data.get('error') else 'finished',error=error or data.get('error'),
                 returned_model=data.get('model'),response_status=data.get('status'),usage=data.get('usage'))
    save(out/f'{ident}.attempt.json',event)
    return data,event


def output_text(data):
    return ''.join(c.get('text','') for item in data.get('output',[]) if item.get('type')=='message'
                   for c in item.get('content',[]) if c.get('type')=='output_text')


if __name__ == '__main__':
    payload={'model':MODEL,'instructions':'This is a connectivity and JSON-format check. Return only a JSON object.',
             'input':'Return {"ok":true}.','max_output_tokens':2048,'reasoning':{'effort':'high'},
             'text':{'format':{'type':'json_object'}},'stream':False,'store':False}
    data,event=call(payload,role='protocol_canary',unit_id='aixoras-identity')
    event['valid_json_output']=False
    try: event['valid_json_output']=json.loads(output_text(data))=={'ok':True}
    except Exception: pass
    event['identity_passed']=event['http_status']==200 and event['returned_model']==MODEL and event['valid_json_output']
    save(ROOT/'records/aixoras-protocol-acceptance.json',event)
    print(json.dumps(event,ensure_ascii=False))
