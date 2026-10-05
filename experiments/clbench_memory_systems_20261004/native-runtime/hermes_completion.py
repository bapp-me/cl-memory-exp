"""Validate native supersession only when the same writer covers the final source."""


def scope(job):
    memory=bool(job.get('review_memory',False))
    skills=bool(job.get('review_skills',False)) or not memory
    return memory,skills


def superseded(call):
    result=call.get('result',{})
    return (call.get('status')=='returned' and not call.get('error') and not result.get('failed')
        and result.get('interrupted') is True
        and result.get('turn_exit_reason')=='interrupted_during_api_call(background_review_superseded)')


def validate_calls(jobs,calls,final_hash,*,allow_missing=False):
    proofs=[];missing=[]
    for call in calls:
        result=call.get('result',{})
        if call.get('status')=='returned' and not call.get('error') and not result.get('failed') and result.get('completed'):
            continue
        if not superseded(call):raise RuntimeError('Native child returned incomplete without verified supersession')
        original=next((j for j in jobs if j['id']==call.get('job_id')),None)
        if original is None:raise RuntimeError('Superseded child has no recorded job')
        needed=scope(original)
        replacements=[j for j in jobs if j['id']!=original['id'] and j['source_hash']==final_hash
            and j['status']=='returned' and j.get('native_result') not in {None,'error'}
            and all(not need or have for need,have in zip(needed,scope(j)))
            and any(c.get('job_id')==j['id'] and c.get('status')=='returned' and c.get('result',{}).get('completed')
                    and not c.get('result',{}).get('failed') for c in calls)]
        if not replacements:
            if allow_missing:missing.append(needed);continue
            raise RuntimeError('Superseded writer lacks a completed final-source replacement')
        proofs.append({'superseded_call_id':call['id'],'superseded_job_id':original['id'],
            'replacement_job_id':replacements[-1]['id'],'covered_final_hash':final_hash,
            'original_native_exit_reason':result['turn_exit_reason']})
    return proofs,sorted(set(missing))
