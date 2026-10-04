"""Separately authorized 48 GLM reviews. This module cannot run or reopen a solver."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from common_report import *
from review_glm import render, validate


def review(case,key,retry=False):
    folder=ROOT/'api/round3'/case['case_id']
    original_folder=folder
    if retry:
        assert read(folder/'terminal.json').get('http_status')==429
        folder=folder/'transport-retry-1'
    if (folder/'terminal.json').exists():return read(folder/'terminal.json')
    if folder.exists() and any(folder.iterdir()):raise RuntimeError('Ambiguous in-flight attempt; no reissue')
    packet=read(ROOT/case['packet']);assert sha(ROOT/case['packet'])==case['packet_sha256']
    body=dict(model='glm-5.3-flash',messages=[dict(role='system',content=(ROOT/'review_prompt.txt').read_text(encoding='utf-8')),dict(role='user',content=render(packet))],
        temperature=1,max_tokens=24000,thinking=dict(type='enabled'),reasoning_effort='high',response_format=dict(type='json_object'),stream=False)
    if retry:assert body==read(original_folder/'request.json')
    raw=json.dumps(body,ensure_ascii=False).encode();assert len(raw)<=400000
    save(folder/'request.json',body)
    state=dict(case_id=case['case_id'],role='offline_reviewer',model=body['model'],phase='round3',usage=None,money=None,status='started',
        request_bytes=len(raw),raw_request_sha256=hashlib.sha256(raw).hexdigest(),packet_sha256=case['packet_sha256'],started_at_utc=datetime.now(timezone.utc).isoformat(),http_attempts=1,transport_retry=retry)
    save(folder/'started.json',state);started=time.perf_counter()
    try:
        req=Request('https://api.z.ai/api/paas/v4/chat/completions',data=raw,headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
        with urlopen(req,timeout=660) as response:
            data=response.read();state['http_status']=response.status
        result=json.loads(data);save(folder/'response.json',result)
        state.update(usage=result.get('usage'),returned_model=result.get('model'),response_id=result.get('id'),received_response_sha256=hashlib.sha256(data).hexdigest())
        answer=result['choices'][0]['message'].get('content') or '';state['finish_reason']=result['choices'][0].get('finish_reason')
        (folder/'visible-output.txt').write_text(answer,encoding='utf-8')
        cleaned=answer.strip()
        if cleaned.startswith('```'):cleaned=cleaned.split('\n',1)[1].rsplit('```',1)[0].strip()
        obj=json.loads(cleaned);save(ROOT/'reviews/round3'/f"{case['case_id']}.json",obj)
        state['validation_errors']=validate(obj,packet);state['status']='valid' if not state['validation_errors'] else 'needs_audit'
    except HTTPError as error:
        state.update(status='http_error',http_status=error.code,error=error.read().decode(errors='replace')[:1500])
    except Exception as error:state.update(status='error',error=type(error).__name__+': '+str(error)[:800])
    state.update(seconds=time.perf_counter()-started,finished_at_utc=datetime.now(timezone.utc).isoformat())
    save(folder/'terminal.json',state);return state


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['first','remaining','retry429']);args=parser.parse_args()
    auth=read(ROOT/'records/review-authorization.json');manifest=read(ROOT/'records/review-manifest-round3.json')
    assert auth['approved'] and not auth.get('closed') and len(manifest['cases'])==48
    assert sha(ROOT/'records/review-manifest-round3.json')==auth['manifest_sha256']
    assert sha(ROOT/'review_prompt.txt')==auth['prompt_sha256']
    for path,expected in auth['implementation_hashes'].items():assert sha(REPO/path)==expected
    for path,expected in manifest['source_files'].items():assert sha(REPO/path)==expected
    cases=manifest['cases'][:1] if args.stage=='first' else manifest['cases'][1:]
    if args.stage!='first':
        first=read(ROOT/'api/round3'/manifest['cases'][0]['case_id']/'terminal.json')
        assert first.get('http_status')==200 and first.get('usage') is not None
    if args.stage=='retry429':
        assert auth['transport_reissues']==1
        cases=[c for c in manifest['cases'] if (ROOT/'api/round3'/c['case_id']/'terminal.json').exists()
            and read(ROOT/'api/round3'/c['case_id']/'terminal.json').get('http_status')==429]
    assert len(list((ROOT/'api/round3').rglob('started.json')))<=auth['max_http_attempts']
    import run_native
    eng,_=run_native.engine();key=eng.secret()
    def terminal(case):
        base=ROOT/'api/round3'/case['case_id']
        return (base/'transport-retry-1' if args.stage=='retry429' else base)/'terminal.json'
    jobs=iter(c for c in cases if not terminal(c).exists())
    active={};completed=[];errors=[]
    with ThreadPoolExecutor(max_workers=auth['workers']) as pool:
        def dispatch():
            try:case=next(jobs)
            except StopIteration:return False
            active[pool.submit(review,case,key,args.stage=='retry429')]=case['case_id'];return True
        for _ in range(auth['workers']):
            if not dispatch():break
        while active:
            finished,_=wait(active,return_when=FIRST_COMPLETED)
            for future in finished:
                cid=active.pop(future);result=future.result();completed.append(result)
                print(json.dumps({k:result.get(k) for k in ('case_id','status','seconds','usage')}),flush=True)
                if result.get('http_status')!=200 or result.get('usage') is None:errors.append(cid)
            if not errors:
                while len(active)<auth['workers'] and dispatch():pass
            save(ROOT/f'records/review-progress-{args.stage}.json',dict(completed=completed,errors=errors))
    if errors:raise SystemExit(2)


if __name__=='__main__':main()
