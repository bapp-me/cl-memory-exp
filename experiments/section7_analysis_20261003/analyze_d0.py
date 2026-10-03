"""Recompute D0 metrics, exact legacy retrieval, context bytes and efficiency pairs.

Only parses saved files. Does not import experiment runners, execute submissions,
call providers, modify score masks or mutate memories.
"""
import ast
from collections import Counter, defaultdict
import re
import statistics
from common import *


def optional(p):
    return read(p) if p.exists() else None


def legacy_retrieval(history,method,prompt):
    candidates=[]
    query=set(re.findall(r'\w+',prompt.lower()))
    for i,e in enumerate(history) if method!='no_memory' else []:
        words=set(re.findall(r'\w+',e['text'].lower()))
        score=len(query&words)/(len(query|words) or 1) if method=='episodic_retrieval' else None
        candidates.append({'history_index':i,'memory_id':digest(e),'score':score})
    ranked=sorted(candidates,key=lambda c:(c['score'],c['history_index']),reverse=True) if method=='episodic_retrieval' else candidates
    for rank,item in enumerate(ranked): item['rank']=rank+1
    selected=ranked[:3] if method=='episodic_retrieval' else ranked[:]
    selected.sort(key=lambda c:history[c['history_index']]['sequence'])
    packed=selected[:];dropped=[]
    while packed and len(json.dumps([history[c['history_index']] for c in packed],ensure_ascii=False).encode())>48000:
        dropped.append({**packed.pop(0),'reason':'oldest_complete_episode_byte_budget'})
    injected=[history[c['history_index']] for c in packed]
    return {'observable_candidates':ranked,'selected_before_packing':selected,'dropped':dropped,
            'injected_ids':[c['memory_id'] for c in packed],'injected_hash':digest(injected),'reconstructed_offline':True}


def median(values):
    values=[v for v in values if isinstance(v,(int,float))]
    return statistics.median(values) if values else None


def stat(values):
    values=[v for v in values if isinstance(v,(int,float))]
    return {'observed':len(values),'sum':sum(values),'median':median(values),'min':min(values) if values else None,'max':max(values) if values else None}


def tool_metrics(pi):
    calls=[];observations=[]
    for m in pi['messages']:
        if m['role']=='assistant':
            calls.extend(c for c in m.get('content',[]) if c.get('type')=='toolCall')
        elif m['role']=='toolResult':
            texts=[c.get('text','') for c in m.get('content',[]) if isinstance(c,dict)]
            parsed=[]
            for t in texts:
                try: parsed.append(json.loads(t))
                except (ValueError,TypeError):pass
            errors=[]
            if m.get('isError'):errors.append('tool_isError')
            for obj in parsed:
                if not isinstance(obj,dict):continue
                if obj.get('error'):errors.append('error_field')
                if obj.get('returncode') not in [None,0]:errors.append('nonzero_returncode')
                # Descriptive BabyAI textual observation proxy, never a failure rate.
                if re.search(r'invalid action|not a valid action|not recognized|cannot|can.t|blocked',str(obj.get('observation','')),re.I):errors.append('action_text_proxy')
            if any('fetch failed' in t or 'ECONNREFUSED' in t for t in texts):errors.append('tool_transport_failure')
            observations.append({'tool_call_id':m.get('toolCallId'),'tool':m.get('toolName'),'signals':errors})
    working=[c for c in calls if c['name']!='SUBMIT']
    keys=[digest([c['name'],c.get('arguments')]) for c in working]
    duplicates=sum(v-1 for v in Counter(keys).values() if v>1)
    badids={o['tool_call_id'] for o in observations if o['signals']}
    recovered=[]
    for i,c in enumerate(calls):
        if c.get('id') in badids:
            after=calls[i+1:];first=next((j for j,x in enumerate(after) if x.get('id') not in badids and x['name']==c['name']),None)
            recovered.append(first+1 if first is not None else None)
    return {'by_name':dict(Counter(c['name'] for c in calls)),'same_working_arguments_excess':duplicates,
            'observations_with_error_signals':sum(bool(o['signals']) for o in observations),
            'error_signal_types':dict(Counter(s for o in observations for s in o['signals'])),
            'calls_to_next_same_tool_without_error_signal':recovered,
            'warning':'Identical arguments/error text/recovery proxy are descriptive; no waste or semantic recovery claim.'}


def ast_overlap(source,target):
    def nodes(text):
        try: tree=ast.parse(text)
        except (SyntaxError,TypeError):return None
        return {ast.dump(n,include_attributes=False) for n in ast.walk(tree)
                if isinstance(n,ast.stmt) and not isinstance(n,(ast.Import,ast.ImportFrom)) and sum(1 for _ in ast.walk(n))>=5}
    a,b=nodes(source),nodes(target)
    return {'source_subtrees':len(a) if a is not None else None,'target_subtrees':len(b) if b is not None else None,
            'identical_nontrivial_statement_subtrees':len(a&b) if a is not None and b is not None else None,
            'status':'proxy_only_no_causal_attribution'}


def main():
    final=read(OBS/'records/section7.1-final.json'); assets=read(OBS/'.cache/agentcl-codeeval.json')
    output=[];contexts=[];reconstructed=[];issues=[];inputs={};pair_metrics=[];content_states=[]
    pairs={(p['method'],p['target_index']):p for p in final['paired_source_target_rows']}
    def track(p):
        if p.exists():inputs[p.relative_to(REPO).as_posix()]=sha(p)
    for row in final['results']:
        folder=REPO/row['source_path'];pi=read(folder/'pi-result.json');before=read(folder/'memory-before.json');after=read(folder/'memory-after.json');inj=read(folder/'injected.json')
        for n in ['pi-result.json','memory-before.json','memory-after.json','injected.json','execution.json','commit.json','evaluator.json','requests.jsonl','call-ledger.json','controller-events.jsonl','tools.jsonl']:
            track(folder/n)
        result={**row,'case_id':case_id(row),'stop_reason':pi.get('stop_reason'),'tool_metrics':tool_metrics(pi),
                'memory_state_changed':digest(before)!=digest(after),'before_canonical_bytes':len(json.dumps(before,ensure_ascii=False,sort_keys=True).encode()),
                'after_canonical_bytes':len(json.dumps(after,ensure_ascii=False,sort_keys=True).encode()),
                'history_episode_count':len(before) if isinstance(before,list) else before.get('episode_count'),
                'injection_count':len(inj),'injection_serialized_bytes':len(json.dumps(inj,ensure_ascii=False).encode()),
                'injected_text_bytes':sum(len(x['text'].encode()) for x in inj),'unique_injected_text_bytes':sum(len(s.encode()) for s in {x['text'] for x in inj}),
                'result_status':'asset_unscorable' if not row['scorable'] else 'success' if row['correct'] else 'scorable_failure'}
        # Score remains authoritative; separately record infrastructure evidence without erasing failure.
        result['execution_anomalies']={k:row.get(k) for k in ['terminal_state','response_timed_out','context_exceeded','solver_error','memory_error']}
        result['diagnostic_outcome_status']='infrastructure_interruption' if result['tool_metrics']['error_signal_types'].get('tool_transport_failure') else result['result_status']
        if row['benchmark']=='codeeval' and row['method'] in ['mem0','awm','ace']:
            key={'awm':'workflow_text','ace':'playbook','mem0':'points'}[row['method']]
            content_states.append({'method':row['method'],'task_id':row['task_id'],'index':row['index'],'content_key':key,
                 'before_content_hash':digest(before.get(key)),'after_content_hash':digest(after.get(key)),
                 'content_changed':before.get(key)!=after.get(key),'memory_state_hash_changed':digest(before)!=digest(after)})
        prompt=assets[row['index']]['problem'] if row['benchmark']=='codeeval' else next(m['content'] for m in pi['messages'] if m['role']=='user')
        if isinstance(prompt,list):prompt='\n'.join(x.get('text','') for x in prompt if isinstance(x,dict))
        retrieval=optional(folder/'retrieval.json')
        if retrieval is None:
            retrieval=legacy_retrieval(before,row['method'],prompt)
            if retrieval['injected_hash']!=digest(inj):issues.append({'case_id':result['case_id'],'issue':'legacy injection reconstruction mismatch'})
            reconstructed.append({'case_id':result['case_id'],'injection_hash_verified':retrieval['injected_hash']==digest(inj),**retrieval})
        result['candidate_count']=len(retrieval['observable_candidates']);result['packing_dropped_count']=len(retrieval['dropped'])
        result['selected_before_packing_count']=len(retrieval['selected_before_packing'])
        if isinstance(before,list):
            expected=before if row['method']=='no_memory' else None
            if row['method']!='no_memory':
                # Historical append contents have a frozen visible trajectory format; check prefix,
                # increment and next-start continuity independently, without reconstructing observations.
                result['append_only_verified']=after[:-1]==before and len(after)==len(before)+1
            else:result['append_only_verified']=after==before==[]
        nxt=folder.parent/f'{row["index"]+1:03d}'/'memory-before.json'
        result['next_start_matches_after']=digest(read(nxt))==digest(after) if nxt.exists() else None
        if result['next_start_matches_after'] is False:issues.append({'case_id':result['case_id'],'issue':'memory chain mismatch'})
        events=lines(folder/'controller-events.jsonl')
        def boundary(a,b):
            x=next((x for x in events if x['event']==a),None);y=next((x for x in reversed(events) if x['event']==b),None)
            return (y['monotonic_ns']-x['monotonic_ns'])/1e9 if x and y else None
        result['task_start_to_commit_seconds']=boundary('task_start','task_commit')
        result['submission_to_commit_seconds']=boundary('submission','task_commit')
        result['recorded_tool_duration_seconds']=sum(e.get('duration_monotonic_ns',0) for e in events if e['event']=='tool_observation')/1e9 if events else None
        ledger=optional(folder/'call-ledger.json')
        result['solver_generation_durations_seconds']=[c['duration_monotonic_ms']/1000 for c in ledger if c.get('duration_monotonic_ms') is not None] if ledger else None
        reqs=lines(folder/'requests.jsonl');result['solver_request_count']=len(reqs)
        if row['source_kind']=='legacy_descriptive_reuse':
            # First system memory persists in each frozen runner generation. An explicitly
            # reconstructed logical count, not an actual historical body/hash measurement.
            result['cumulative_solver_memory_serialized_bytes']=result['injection_serialized_bytes']*len(reqs) if inj else 0
            result['context_measurement']='legacy reconstruction, request count * frozen system memory; no original payload hash'
        else:
            result['cumulative_solver_memory_serialized_bytes']=sum(match['utf8_bytes'] for q in reqs for b in q.get('blocks',[]) for match in b.get('matches',[]))
            result['context_measurement']='actual request block spans, excludes JSON array separators'
            result['all_injected_blocks_mapped']=all(q.get('all_injected_blocks_mapped') for q in reqs)
        # Offline auxiliary role maps: exact substring matches only, with overlaps visible.
        for q in folder.glob('auxiliary/*/payloads/*.json'):
            track(q);payload=read(q);txt=[m.get('content','') for m in payload.get('messages',[]) if isinstance(m.get('content'),str)]
            sources={'target_prompt':prompt,'prior_playbook':before.get('playbook','') if isinstance(before,dict) else '',
                     'prior_workflows':before.get('workflow_text','') if isinstance(before,dict) else ''}
            for fname,label in [('legal-episode.json','current_legal_episode'),('reflection.json','reflection')]:
                z=optional(folder/fname)
                if z is not None:
                    track(folder/fname)
                    sources[label]=z if isinstance(z,str) else z.get('text',z.get('raw_response',json.dumps(z,ensure_ascii=False)))
            mapped=[]
            for label,s in sources.items():
                if not isinstance(s,str) or not s:continue
                for i,t in enumerate(txt):
                    start=t.find(s)
                    if start>=0:mapped.append({'block':label,'message_index':i,'char_start':start,'char_end':start+len(s),'utf8_bytes':len(s.encode())})
            contexts.append({'case_id':result['case_id'],'role_folder':q.parent.parent.name,'payload':q.relative_to(REPO).as_posix(),
                             'sha256':sha(q),'message_text_bytes':sum(len(t.encode()) for t in txt),'exact_matches':mapped,
                             'coverage':'partial semantic map; unmatched text retained in full payload, overlap not summed','token_count':None})
        if row['benchmark']=='codeeval' and row['task_id'].startswith('new:'):
            pair=pairs[(row['method'],row['index'])]; srcfolder=folder.parent/f'{pair["source_index"]:03d}'
            def submission(d):return (d/'submission.py').read_text(encoding='utf-8') if (d/'submission.py').exists() else ''
            p={**pair,'case_id':result['case_id'],'ast_overlap':ast_overlap(submission(srcfolder),submission(folder))}
            if row['method'] in ['no_memory','episodic_retrieval','bounded_icl']:
                source_ids={digest(e) for e in before if json.loads(e['text'])['task']==assets[pair['source_index']]['problem']}
                p['source_in_candidates_recomputed']=bool(source_ids&{c['memory_id'] for c in retrieval['observable_candidates']})
                selected_ids={c['memory_id'] if isinstance(c,dict) else c for c in retrieval['selected_before_packing']}
                p['source_selected_before_packing']=bool(source_ids&selected_ids)
                p['source_packing_dropped']=bool(source_ids&{c['memory_id'] for c in retrieval['dropped']})
            else:
                source_ids={k for k,v in before.get('provenance',{}).items() if any(f'.task-{pair["source_index"]:03d}.' in x for x in v)}
                p['source_in_candidates_recomputed']=bool(source_ids&{c['memory_id'] for c in retrieval['observable_candidates']})
                p['source_selected_before_packing']=bool(source_ids&{c['memory_id'] if isinstance(c,dict) else c for c in retrieval['selected_before_packing']})
                p['source_packing_dropped']=bool(source_ids&{c['memory_id'] for c in retrieval['dropped']})
            p['coverage_interpretation']='provenance only; abstraction content/semantic utility reviewed separately'
            pair_metrics.append(p)
        output.append(result)
    summaries=[];efficiency=[];cross=[]
    no={(r['benchmark'],r['task_id']):r for r in output if r['method']=='no_memory'}
    for method in METHODS:
        for benchmark in ['codeeval','babyai']:
            cohort=[r for r in output if r['method']==method and r['benchmark']==benchmark]
            for scope in ['all_executed','effective','all_complex_executed','effective_complex'] if benchmark=='codeeval' else ['all_executed']:
                xs=[r for r in cohort if ('effective' not in scope or r['scorable']) and ('complex' not in scope or r['task_id'].startswith('new:'))]
                summary={'method':method,'benchmark':benchmark,'scope':scope,'tasks':len(xs),
                         'scorable':sum(r['scorable'] for r in xs),'correct':sum(r['correct'] is True for r in xs),
                         'usage_missing_tasks':sum(r['usage'] is None for r in xs),
                         'unknown_http_usage':None if method in ['no_memory','episodic_retrieval'] else sum(r['unknown_usage_http_attempts'] or 0 for r in xs),
                         'known_usage_subtotal':{k:sum((r['known_usage_subtotal'] or {}).get(k,0) for r in xs) for k in ['input','output','cacheRead','cacheWrite','totalTokens']},
                         'working_calls':sum(r['working_tool_calls'] for r in xs),'submit_calls':sum(r['submit_calls'] for r in xs),
                         'same_working_arguments_excess':sum(r['tool_metrics']['same_working_arguments_excess'] for r in xs),
                         'tool_observation_error_signals':sum(r['tool_metrics']['observations_with_error_signals'] for r in xs),
                         'packing_dropped_tasks':sum(r['packing_dropped_count']>0 for r in xs),
                         'turns':stat(r['turns'] for r in xs),'task_start_to_commit_seconds':stat(r['task_start_to_commit_seconds'] for r in xs),
                         'submission_to_commit_seconds':stat(r['submission_to_commit_seconds'] for r in xs),
                         'injected_text_bytes':stat(r['injected_text_bytes'] for r in xs),
                         'cumulative_solver_memory_serialized_bytes':sum(r['cumulative_solver_memory_serialized_bytes'] for r in xs),
                         'result_statuses':dict(Counter(r['result_status'] for r in xs))}
                summaries.append(summary)
            eligible=[r for r in cohort if r['scorable'] and (benchmark=='babyai' or r['task_id'].startswith('new:'))]
            paired=[]
            for r in eligible:
                ref=no[(benchmark,r['task_id'])]
                paired.append({'case_id':r['case_id'],'task_id':r['task_id'],'correct':r['correct'],'no_memory_correct':ref['correct'],
                               'known_token_delta':r['known_usage_subtotal']['totalTokens']-ref['known_usage_subtotal']['totalTokens'],
                               'complete_usage':r['usage'] is not None and ref['usage'] is not None,
                               'working_calls_delta':r['working_tool_calls']-ref['working_tool_calls'],
                               'submit_calls_delta':r['submit_calls']-ref['submit_calls'],
                               'repeat_args_delta':r['tool_metrics']['same_working_arguments_excess']-ref['tool_metrics']['same_working_arguments_excess']})
            efficiency.append({'method':method,'benchmark':benchmark,'denominator':len(paired),
                               'both_correct':sum(p['correct'] and p['no_memory_correct'] for p in paired),
                               'improvement_candidates':sum(p['correct'] and not p['no_memory_correct'] for p in paired),
                               'harm_candidates':sum(not p['correct'] and p['no_memory_correct'] for p in paired),
                               'both_fail':sum(not p['correct'] and not p['no_memory_correct'] for p in paired),
                               'known_token_delta':stat(p['known_token_delta'] for p in paired),
                               'working_calls_delta':stat(p['working_calls_delta'] for p in paired),'pairs':paired,
                               'causal':False,'limits':'R=1, independent method histories, historical baseline aliases/usage/concurrency; descriptive paired differences only'})
        ps=[p for p in pair_metrics if p['method']==method and p['target_scorable']]
        counts=Counter((str(p['source_correct']),p['source_provenance_injected'],p['target_correct']) for p in ps)
        cross.append({'method':method,'denominator':len(ps),'source_quality_x_injected_x_result':[{'source_correct':a,'injected':b,'target_correct':c,'count':n} for (a,b,c),n in counts.items()],
                      'source_in_candidates':sum(p['source_in_candidates_recomputed'] for p in ps),'source_selected_before_packing':sum(p['source_selected_before_packing'] for p in ps),
                      'source_packing_dropped':sum(p['source_packing_dropped'] for p in ps),'source_provenance_injected':sum(p['source_provenance_injected'] for p in ps)})
    save(ROOT/'records/d0-tasks.json',output)
    save(ROOT/'records/d0-summary.json',{'tasks':len(output),'issues':issues,'summaries':summaries,'source_coverage':cross,'model_calls':0,
       'unavailable':['provider-exact per-block token/cache attribution','historical full streaming latency','isolated retrieval/write/persistence spans','verified monetary cost','D2 causal effects','cross-project/global-rule scores (not applicable)']})
    save(ROOT/'records/efficiency-pairs.json',efficiency)
    save(ROOT/'records/source-target-pairs.json',pair_metrics)
    save(ROOT/'records/legacy-retrieval-reconstructed.json',reconstructed)
    save(ROOT/'records/auxiliary-context-map.json',contexts)
    save(ROOT/'records/d0-input-hashes.json',inputs)
    save(ROOT/'records/content-state-transitions.json',content_states)
    print(json.dumps({'tasks':len(output),'summaries':len(summaries),'legacy_retrieval_reconstructions':len(reconstructed),'auxiliary_payload_maps':len(contexts),'issues':issues}))
    assert not issues


if __name__=='__main__':main()
