"""One recorded offline API review per packet; no retries and no rollout mutation."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import os
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from common import *

MODELS={'deepseek':('https://api.deepseek.com','deepseek-flash'),
        'glm':('https://api.z.ai/api/paas/v4','glm-5.3-flash')}
TAGS={'EVAL_CONTRACT','INFRA_PROTOCOL','TASK_EXECUTION','OPPORTUNITY_SOURCE','WRITE_ADMISSION',
      'REPRESENTATION','RETRIEVAL','PACKING_VISIBILITY','USE_TRANSFER','UPDATE_RETENTION','SCOPE_INTERFERENCE','COST_UTILITY'}
ENUMS={'source_quality':{'pass_with_limits','failed_or_partial','unknown','not_applicable'},
       'memory_fidelity':{'faithful','partial','contradicted','absent','unknown','not_applicable'},
       'target_applicability':{'applicable','partial','irrelevant','absent','unknown','not_applicable'},
       'visible_use':{'consistent_adaptation','misapplication_candidate','no_visible_use','unknown','not_applicable'}}


def secret(provider):
    value=os.environ.get({'glm':'GLM_API_KEY','deepseek':'DEEPSEEK_API_KEY'}[provider])
    if value: return value.strip()
    path=Path('D:/campus_re/experiments/memory_direction_20261002/.private/credentials.json')
    script=("$d=Get-Content -Raw -LiteralPath '"+str(path)+"'|ConvertFrom-Json;"
            "$s=ConvertTo-SecureString $d."+provider+";"
            "$p=[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s);"
            "try{[Console]::Write([System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($p))}"
            "finally{[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}")
    result=subprocess.run(['pwsh.exe','-NoProfile','-Command',script],capture_output=True)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError('Credential unavailable for '+provider+'; no API attempted')
    return result.stdout.decode().strip()


def validate(obj,packet):
    errors=[]
    if not isinstance(obj,dict):return ['not an object']
    for key in ['case_id','result_status','semantic','labels','primary_hypothesis','competing_explanations','confidence','uncertainties','minimal_intervention','causal_claim']:
        if key not in obj:errors.append('missing '+key)
    if obj.get('case_id')!=packet['case_id']:errors.append('wrong case_id')
    if obj.get('causal_claim') is not False: errors.append('causal_claim must be false')
    text={s['id']:s['text'] for s in packet['evidence']}
    claims=list(obj.get('labels',[]))+list(obj.get('semantic',{}).values())
    for claim in claims:
        if not isinstance(claim,dict):errors.append('claim not object');continue
        if 'tag' in claim and claim['tag'] not in TAGS: errors.append('invalid tag')
        if 'tag' in claim and claim.get('level') not in ['D0','D1']:errors.append('invalid evidence level')
        if not claim.get('evidence') and claim.get('value') not in ['unknown','not_applicable']:
            errors.append('missing evidence '+str(claim.get('tag',claim.get('value'))))
        for e in claim.get('evidence',[]):
            if e.get('section') not in text or not e.get('quote') or e['quote'] not in text.get(e['section'],''):
                errors.append('unmatched quote '+str(e.get('section'))+': '+str(e.get('quote'))[:80])
    for field,choices in ENUMS.items():
        if obj.get('semantic',{}).get(field,{}).get('value') not in choices:errors.append('invalid '+field)
    if obj.get('primary_hypothesis') not in TAGS|{'unknown'}:errors.append('invalid primary')
    if len(obj.get('labels',[]))>4:errors.append('too many labels')
    if not obj.get('competing_explanations'):errors.append('no competing explanation')
    return errors


def call(provider,case,key,phase):
    cid=case['case_id']; folder=ROOT/'api'/phase/provider/cid
    target=ROOT/'reviews'/provider/f'{cid}.json' if phase=='pilot' else ROOT/'reviews'/phase/provider/f'{cid}.json'
    if (folder/'terminal.json').exists():return read(folder/'terminal.json')
    if folder.exists() and any(folder.iterdir()):
        raise RuntimeError('Unfinished prior attempt; audit before any retry: '+str(folder))
    packet=read(ROOT/'packets'/f'{cid}.json')
    if sha(ROOT/'packets'/f'{cid}.json')!=case['packet_sha256']:raise RuntimeError('Packet changed')
    endpoint,model=MODELS[provider]
    payload={'model':model,'messages':[{'role':'system','content':(ROOT/'review_prompt.txt').read_text(encoding='utf-8')},
             {'role':'user','content':json.dumps(packet,ensure_ascii=False)}],
             'temperature':1,'max_tokens':10000 if phase=='pilot' else 24000,'thinking':{'type':'enabled'},'response_format':{'type':'json_object'},'stream':False}
    if phase!='pilot':payload['reasoning_effort']='medium'
    save(folder/'request.json',payload)
    started=time.monotonic()
    terminal={'provider':provider,'case_id':cid,'phase':phase,'model_requested':model,'endpoint':endpoint,
              'started_at_utc':datetime.now(timezone.utc).isoformat(),'request_sha256':sha(folder/'request.json'),
              'prompt_sha256':sha(ROOT/'review_prompt.txt'),'packet_sha256':case['packet_sha256'],
              'http_attempts':1,'retry':False,'money':None,'usage':None}
    save(folder/'started.json',terminal)
    try:
        request=Request(endpoint+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),
                        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        with urlopen(request,timeout=300 if phase=='pilot' else 660) as response:
            raw=json.load(response);terminal['http_status']=response.status
        # No headers or credentials. Preserve full provider response for independent audit.
        save(folder/'response.json',raw)
        terminal.update(model_returned=raw.get('model'),usage=raw.get('usage'),response_id=raw.get('id'))
        text=raw['choices'][0]['message'].get('content') or ''
        terminal['finish_reason']=raw['choices'][0].get('finish_reason')
        (folder/'visible-output.txt').write_text(text,encoding='utf-8')
        cleaned=text.strip()
        if cleaned.startswith('```'):cleaned=cleaned.split('\n',1)[1].rsplit('```',1)[0].strip()
        obj=json.loads(cleaned)
        save(target,obj)
        terminal['validation_errors']=validate(obj,packet)
        terminal['status']='valid' if not terminal['validation_errors'] else 'needs_audit'
    except HTTPError as e:
        terminal.update(status='http_error',http_status=e.code,error=e.read().decode(errors='replace')[:2000])
    except Exception as e:
        terminal.update(status='error',error=type(e).__name__+': '+str(e)[:1000])
    terminal['seconds']=round(time.monotonic()-started,3)
    save(folder/'terminal.json',terminal)
    return terminal


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['pilot','pilot2','formal'],required=True)
    ap.add_argument('--provider',choices=['deepseek','glm','both'],required=True);ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args();assert 1<=args.workers<=12
    manifest=read(ROOT/'records/manifest.json'); cases=manifest['cases']
    if args.phase in ['pilot','pilot2']:cases=[c for c in cases if c['pilot']]
    else:
        selection=read(ROOT/'records/model-selection.json')
        assert args.provider==selection['selected_provider'] and selection['status']=='frozen'
        # Reuse selected pilot reviews; no second reviews of the same packet.
        cases=[c for c in cases if not c['pilot']]
        cases.sort(key=lambda c:(c['case_id'] not in manifest['priority_16_ids'],c['case_id']))
    providers=list(MODELS) if args.provider=='both' else [args.provider]
    keys={p:secret(p) for p in providers}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(call,p,c,keys[p],args.phase) for p in providers for c in cases]
        for future in as_completed(futures):
            r=future.result();print(json.dumps({k:r.get(k) for k in ['provider','case_id','status','seconds','usage','error']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
