"""Offline mechanical summary; never reads hidden labels or writes agent memory."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from prepare import ROOT, read, save


def response_usage(path):
    raw=path.read_text(encoding='utf-8') if path.exists() else ''
    chunks=[]
    for line in raw.splitlines():
        if line.startswith('data: ') and line[6:]!='[DONE]':
            try: chunks.append(json.loads(line[6:]))
            except json.JSONDecodeError: pass
    if not chunks:
        try: chunks=[json.loads(raw)]
        except json.JSONDecodeError: pass
    usage={}; model=None; finish=None; thinking_characters=0
    for chunk in chunks:
        if chunk.get('type')=='content_block_delta':
            thinking_characters+=len(chunk.get('delta',{}).get('thinking',''))
        if chunk.get('type')=='message_start': chunk=chunk['message']
        if 'response' in chunk: chunk=chunk['response']
        usage.update(chunk.get('usage') or {}); model=chunk.get('model') or model
        delta=chunk.get('delta')
        finish=chunk.get('stop_reason') or (delta.get('stop_reason') if isinstance(delta,dict) else None) or finish
        if (chunk.get('incomplete_details') or {}).get('reason')=='max_output_tokens': finish='max_tokens'
        for choice in chunk.get('choices',[]):
            finish=choice.get('finish_reason') or finish
            thinking_characters+=len(choice.get('delta',{}).get('reasoning_content') or '')
    return usage or None,model,finish,thinking_characters


def normalize(usage,protocol):
    if not usage: return {'input_tokens':None,'output_tokens':None,'cached_input_tokens':None,'reasoning_tokens':None,'total_tokens':None}
    if protocol=='chat':
        inp=usage.get('prompt_tokens'); output=usage.get('completion_tokens')
        cache=(usage.get('prompt_tokens_details') or {}).get('cached_tokens')
        reasoning=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
    elif protocol=='responses':
        inp=usage.get('input_tokens'); output=usage.get('output_tokens')
        cache=(usage.get('input_tokens_details') or {}).get('cached_tokens')
        reasoning=(usage.get('output_tokens_details') or {}).get('reasoning_tokens')
    else:
        inp=(usage.get('input_tokens') or 0)+(usage.get('cache_read_input_tokens') or 0)+(usage.get('cache_creation_input_tokens') or 0)
        output=usage.get('output_tokens'); cache=usage.get('cache_read_input_tokens')
        reasoning=(usage.get('output_tokens_details') or {}).get('thinking_tokens')
    return {'input_tokens':inp,'output_tokens':output,'cached_input_tokens':cache,'reasoning_tokens':reasoning,
            'total_tokens':inp+output if inp is not None and output is not None else None}


def main():
    ledger={}; streams=[]; root=ROOT/'private-runs'
    for directory in sorted(root.iterdir()):
        if not directory.is_dir(): continue
        manifest=read(directory/'manifest.json') if (directory/'manifest.json').exists() else {}
        formal=manifest.get('mode')=='formal'
        for request in directory.rglob('*.request.json'):
            if request.parent.name!='requests': continue
            ident=request.name.removesuffix('.request.json'); out=request.parent.parent
            native_meta=request.with_name(ident+'.attempt.json')
            if native_meta.exists():
                meta=read(native_meta); protocol=meta['protocol']; response=request.with_name(ident+'.response.bin')
            else:
                records=[json.loads(x) for x in (out/'attempts.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()] if (out/'attempts.jsonl').exists() else []
                candidates=[x for x in records if x['attempt_id']==ident]; meta=candidates[-1] if candidates else {}
                protocol='chat'; response=request.with_name(ident+'.response.txt')
            usage,model,finish,thinking_chars=response_usage(response)
            row={'attempt_id':ident,'run_id':directory.name,'category':'formal' if formal else 'acceptance_or_debug',
                 'task':out.name,'method_id':meta.get('method_id'),'role':meta.get('role','unknown_native_role'),
                 'protocol':protocol,'phase':meta.get('phase'),'status':meta.get('http_status',meta.get('status')),
                 'returned_model':model,'finish_reason':finish,'thinking_characters_observed':thinking_chars,
                 'usage':usage,**normalize(usage,protocol)}
            if ident in ledger: raise RuntimeError('Duplicate physical attempt id')
            ledger[ident]=row
        if formal:
            rows=read(directory/'results.json') if (directory/'results.json').exists() else []
            ns=manifest['namespace']; method,_,environment=ns.split('/')
            target=40 if environment=='database_exploration' else 19
            boundary=read(directory/'boundary.json')
            final=read(directory/'stream-status.json') if (directory/'stream-status.json').exists() else None
            state='completed' if len(rows)==target else 'paused_error' if final and final.get('status')=='paused_error' else 'in_progress'
            phases=defaultdict(list)
            for row in rows:
                if environment=='database_exploration': phases['before_migration' if row['index']<20 else 'after_migration'].append(row)
                else: phases[row['project_key']].append(row)
            def stats(values):
                return {'completed':len(values),'correct':sum(x['correct'] for x in values),
                    'business_actions':sum(x['actions'] for x in values),'reward_sum':sum(x['reward'] for x in values),
                    'task_seconds_sum':round(sum(x['seconds'] for x in values),3)}
            streams.append({'run_id':directory.name,'method':method,'environment':environment,'status':state,'target':target,
                **stats(rows),'phases':{k:stats(v) for k,v in phases.items()},
                'distinct_sessions':len({x['session_id'] for x in rows}),
                'boundary_next_index':boundary['next_index'],'pending_index':boundary['pending']['index'] if boundary['pending'] else None,
                'accepted_prefix_instances':manifest.get('accepted_prefix_instances',0)})
    for path in (ROOT/'records').glob('protocol-*.json'):
        record=read(path)
        if 'attempt_id' not in record or record['attempt_id'] in ledger: continue
        ledger[record['attempt_id']]={'attempt_id':record['attempt_id'],'run_id':record['raw_evidence'].split('/')[-1],
            'category':'acceptance_or_debug','task':None,'method_id':None,'role':'protocol_canary','protocol':record['protocol'],
            'phase':'finished' if not record.get('error') else 'failed','status':record.get('http_status'),
            'returned_model':record.get('returned_model'),'usage':record.get('usage'),**normalize(record.get('usage'),record['protocol'])}
    totals={}
    for category in ['formal','acceptance_or_debug']:
        selected=[x for x in ledger.values() if x['category']==category]
        totals[category]={'attempts':len(selected),'unknown_usage_attempts':sum(x['usage'] is None for x in selected),
            **{key+'_known_sum':sum(x.get(key) or 0 for x in selected) for key in ['input_tokens','output_tokens','cached_input_tokens','reasoning_tokens','total_tokens']}}
    for stream in streams:
        calls=[x for x in ledger.values() if x['run_id']==stream['run_id']]
        stream['known_total_tokens']=sum(x.get('total_tokens') or 0 for x in calls)
        stream['attempts']=len(calls); stream['unknown_usage_attempts']=sum(x['usage'] is None for x in calls)
    summary={'as_of':datetime.now(timezone.utc).isoformat(),'streams':streams,'totals':totals,
        'notes':['Counts include unfinished task attempts; completed-task cost comparison must use committed rows only.',
            'Unknown usage is not zero; known sums are lower bounds when attempts are missing usage.',
            'reasoning tokens are a subset of output where reported; never added again.',
            'Anthropic input combines uncached input, cache reads and cache creation; chat/Responses inputs already include cache.',
            'Framework dollar totals and Pi catalog zero placeholders are not GLM bills; monetary cost is unverified.',
            'Parallel task latency is not a serial historical speedup estimate.']}
    save(ROOT/'records/progress-summary.json',summary)
    save(ROOT/'records/attempt-ledger.json',list(ledger.values()))
    print(json.dumps({'streams':[{'method':x['method'],'environment':x['environment'],'completed':x['completed'],'target':x['target'],'status':x['status']} for x in streams],
        'totals':totals},ensure_ascii=False))


if __name__=='__main__': main()
