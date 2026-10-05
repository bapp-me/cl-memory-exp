"""Recover first mechanically valid exact-input response, without model calls.

All response bodies and superseded records remain private and immutable. This
does not manufacture semantic judgments or edit their scores/rationales.
"""
from collections import defaultdict
from datetime import datetime,timezone
import json
from prepare import ROOT,read,save,sha
from analysis_provider import PRIVATE,MODEL,output_text
from judge_full_analysis import normalize_citations,validate,wire_packet


def response_data(path):
    text=path.read_text(encoding='utf8')
    try:return json.loads(text)
    except json.JSONDecodeError:pass
    result={}
    for line in text.splitlines():
        if not line.startswith('data: ') or line[6:]=='[DONE]':continue
        try:e=json.loads(line[6:])
        except json.JSONDecodeError:continue
        if isinstance(e.get('response'),dict):result=e['response']
    return result


def main():
    grouped=defaultdict(list);live=set()
    for p in (PRIVATE/'requests').glob('*.attempt.json'):
        meta=read(p)
        if meta['phase']=='started':live.add(meta['unit_id'])
        if meta['role']=='llm_judge':grouped[meta['unit_id']].append(meta)
    recovered=[];checked=0
    for e in read(ROOT/'records/full-judge-packet-index.json'):
        ident=e['packet_id']
        if ident in live:continue
        packet=read(PRIVATE/'packets'/(ident+'.json'));wire=wire_packet(packet);out=PRIVATE/'judge'/(ident+'.json')
        old=read(out) if out.exists() else None
        if old and old['status']=='valid' and old['packet_sha256']==sha(PRIVATE/'packets'/(ident+'.json')):continue
        for meta in sorted(grouped[ident],key=lambda m:m['timestamp']):
            if meta['http_status']!=200 or meta.get('returned_model')!=MODEL or meta.get('response_status')!='completed':continue
            attempt=meta['attempt_id'];request=read(PRIVATE/'requests'/(attempt+'.request.json'))
            try:matching=json.loads(request['input'])==wire
            except (ValueError,TypeError):matching=False
            if not matching:continue
            checked+=1;data=response_data(PRIVATE/'requests'/(attempt+'.response.txt'))
            try:
                judgement,changes=normalize_citations(json.loads(output_text(data)),packet);validate(judgement,packet)
            except (ValueError,TypeError,KeyError):continue
            if old:save(PRIVATE/'judge-history'/(ident+'-before-offline-reconcile-'+old['attempt_ids'][-1]+'.json'),old)
            record={'packet_id':ident,'packet_sha256':sha(PRIVATE/'packets'/(ident+'.json')),'kind':packet['kind'],'status':'valid',
                    'attempt_ids':[m['attempt_id'] for m in sorted(grouped[ident],key=lambda m:m['timestamp'])],
                    'selected_attempt_id':attempt,'validation_error':None,'judgement':judgement,
                    'citation_span_normalizations':changes,'completed_at':datetime.now(timezone.utc).isoformat(),
                    'repeat':False,'offline_reconciled':True,'selection':'First valid response whose actual submitted input exactly matches the current evidence packet'}
            save(out,record);recovered.append({'packet_id':ident,'selected_attempt_id':attempt,'span_normalizations':len(changes)});break
    path=ROOT/'records/judge-offline-reconciliation.json';prior=read(path) if path.exists() else {'recovered':[]}
    prior.update(as_of=datetime.now(timezone.utc).isoformat(),new_model_calls=0,checked_existing_responses=checked)
    prior['recovered'].extend(recovered);save(path,prior)
    print(json.dumps({'new_model_calls':0,'recovered':len(recovered),'responses_checked':checked}))


if __name__=='__main__':main()
