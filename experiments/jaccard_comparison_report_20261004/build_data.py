"""Recompute seven-profile comparisons from saved evidence, without executing tasks."""
from collections import Counter
import ast
import json
import re
import statistics
from common_report import *

NAMES={'jaccard':'Jaccard 全轨迹 top-3','lexical':'关键词事件检索','hybrid_context':'混合检索与上下文','graph_walk':'图导航检索',
       'native_files':'原生文件','native_shell':'原生终端','compact_r3':'精简原生文件（第3轮）'}
SOURCES={}
def tracked(path):
    SOURCES[path.relative_to(REPO).as_posix()]=sha(path)
    return read(path)
def lines(path):
    if path.exists():SOURCES[path.relative_to(REPO).as_posix()]=sha(path)
    return jsonl(path)
def duplicate(calls):
    return sum(n-1 for n in Counter(digest([c['name'],c.get('arguments',{})]) for c in calls).values())
def metric_function():
    p=REPO/'experiments/section7_analysis_20261003/analyze_d0.py'
    node=next(n for n in ast.parse(p.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='tool_metrics')
    ns=dict(json=json,re=re,Counter=Counter,digest=digest);exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),ns)
    return ns['tool_metrics']
def aggregate(rows):
    totals={k:sum(r[k] for r in rows) for k in ('tokens','input_tokens','cache_tokens','output_tokens','model_calls','python_calls','memory_calls',
        'memory_response_bytes','content_bytes','noncontent_bytes','static_exposure_bytes','dynamic_exposure_bytes','request_bytes_sum',
        'duplicate_queries','duplicate_python_args','duplicate_memory_args','error_observations','memory_errors','truncated_calls')}
    return dict(tasks=len(rows),scorable=sum(r['scorable'] for r in rows),correct=sum(r['correct'] is True for r in rows),
        tokens_median=statistics.median(r['tokens'] for r in rows),seconds_median=statistics.median(r['seconds'] for r in rows),
        seconds_sum=sum(r['seconds'] for r in rows),no_memory_call_tasks=sum(not r['memory_calls'] for r in rows),
        corresponding_source_exposed=None if any(r['source_exposed'] is None for r in rows) else sum(r['source_exposed'] for r in rows),
        empty_search_calls=None if any(r['empty_search_calls'] is None for r in rows) else sum(r['empty_search_calls'] for r in rows),
        noncontent_fraction=totals['noncontent_bytes']/totals['memory_response_bytes'] if totals['memory_response_bytes'] else None,
        max_input_tokens=max(r['max_input_tokens'] for r in rows),max_request_bytes=max(r['max_request_bytes'] for r in rows),
        status_counts=dict(Counter(r['status'] for r in rows)),**totals)

def main():
    assets=tracked(OBS/'.cache/agentcl-codeeval.json');source_map={r['id']:i for i,r in enumerate(assets[:48])}
    library=tracked(REPO/'experiments/section7_frozen_jaccard_20261004/records/simple-library.json')
    assert len(assets)==96 and len(library)==48
    original=tracked(BASE/'records/analysis.json')['rows']+tracked(NATIVE/'records/analysis.json')['rows']
    jaccard=tracked(REPO/'experiments/section7_frozen_jaccard_20261004/records/results.json')['rows']
    r3=tracked(OPT/'rounds/r3/analysis.json')['rows']
    groups={'jaccard':jaccard,**{m:[r for r in original if r['method']==m] for m in METHODS},'compact_r3':r3}
    metric=metric_function();rows=[];source_ranks=[]
    for method,group in groups.items():
        assert len(group)==48
        for old in group:
            folder=REPO/old['source_path'];idx=old['index'];source=source_map[assets[idx]['id']];sid=f's{source:03d}'
            pi=tracked(folder/'pi-result.json');initial=tracked(folder/'input-public.json');evaluation=tracked(folder/'evaluator.json')
            assert initial['prompt']==assets[idx]['problem']
            assert digest(tracked(folder/'memory-before.json'))==digest(library)==digest(tracked(folder/'memory-after.json'))
            requests=lines(folder/'requests.jsonl');access=[a for a in lines(folder/'memory-access.jsonl') if a.get('event')=='memory_access'];exposure=lines(folder/'memory-exposure.jsonl')
            ledger=tracked(folder/'call-ledger.json');attempts=[a for c in ledger for a in c['http_attempts']]
            assert len(attempts)==old['http_attempts'] and all(a.get('raw_usage') for a in attempts)
            raw_usage=[a['raw_usage'] for a in attempts]
            prompt=sum(u['prompt_tokens'] for u in raw_usage);cache=sum(u.get('prompt_tokens_details',{}).get('cached_tokens',0) for u in raw_usage)
            output=sum(u['completion_tokens'] for u in raw_usage);total=sum(u['total_tokens'] for u in raw_usage)
            assert total==old['known_usage_subtotal']['totalTokens']==prompt+output
            calls=[c for m in pi['messages'] if m['role']=='assistant' for c in m.get('content',[]) if c.get('type')=='toolCall']
            tools=metric(pi);memcalls=[c for c in calls if c['name'].startswith('MEMORY_')];pycalls=[c for c in calls if c['name']=='PYTHON']
            results=lines(folder/'memory-results.jsonl');response_bytes=sum(len(r['serialized'].encode()) for r in results)
            content_bytes=0
            for result in results:
                for item in json.loads(result['serialized']).get('items',[]):
                    for key in ('content','stderr'):
                        if isinstance(item.get(key),str):content_bytes+=len(json.dumps(item[key],ensure_ascii=False)[1:-1].encode())
            exposed=set();opened=set()
            for event in exposure:
                for mapping in event['mappings']:
                    if not mapping['matches']:continue
                    for part in mapping['ranges']:
                        if 'source_id' in part:exposed.add(part['source_id'])
                        elif part.get('path','').startswith(('/memory/episodes/','/memory/raw/')):exposed.update(part.get('source_ids',[]))
                        elif part.get('kind')=='terminal_output':opened.update(part.get('source_ids',[]))
            queries=[a['args'].get('query',a['args'].get('pattern',a['args'].get('command',''))) for a in access]
            queries=[q for q in queries if q]
            injected=tracked(folder/'injected.json')
            static_bytes=sum(m['utf8_bytes'] for r in requests for b in r.get('blocks',[]) for m in b['matches'])
            dynamic_bytes=sum(m['utf8_bytes'] for r in exposure for b in r['mappings'] for m in b['matches'])
            source_exposed=None if method=='native_shell' else (source in [r['sequence'] for r in injected] if method=='jaccard' else sid in exposed)
            if method=='jaccard':
                retrieval=tracked(folder/'retrieval.json');rank=next(x['rank'] for x in retrieval['observable_candidates'] if x['history_index']==source)
                source_ranks.append(dict(index=idx,source_index=source,rank=rank,dropped=len(retrieval['dropped']),injected_bytes=retrieval['injected_utf8_bytes']))
            status='asset_unscorable' if not old['scorable'] else 'success' if old['correct'] else 'scorable_failure'
            rows.append(dict(method=method,index=idx,task_id=old['task_id'],source_index=source,source_path=old['source_path'],scorable=bool(old['scorable']),correct=old['correct'],status=status,
                tokens=total,input_tokens=prompt-cache,cache_tokens=cache,output_tokens=output,model_calls=len(ledger),http_attempts=len(attempts),unknown_usage=0,
                seconds=old['seconds'],python_calls=len(pycalls),memory_calls=len(memcalls),submit_calls=sum(c['name']=='SUBMIT' for c in calls),tools_by_name=tools['by_name'],
                memory_response_bytes=response_bytes,content_bytes=content_bytes,noncontent_bytes=response_bytes-content_bytes,
                static_exposure_bytes=static_bytes,dynamic_exposure_bytes=dynamic_bytes,request_bytes_sum=sum(r['bytes'] for r in requests),
                startup_memory_bytes=sum(len(b.get('text','').encode()) for b in initial.get('memory_blocks',[])),
                duplicate_queries=sum(n-1 for n in Counter(queries).values()),duplicate_python_args=duplicate(pycalls),duplicate_memory_args=duplicate(memcalls),
                error_observations=tools['observations_with_error_signals'],error_signal_types=tools['error_signal_types'],
                recovery_proxy=tools['calls_to_next_same_tool_without_error_signal'],memory_errors=sum(bool(a['result'].get('error')) for a in access),
                truncated_calls=sum(bool(a['result'].get('packing_truncated')) for a in access),
                empty_search_calls=None if method=='native_shell' else sum(a['result'].get('total_matches')==0 for a in access),
                source_exposed=source_exposed,source_opened=sid in opened if method=='native_shell' else None,
                max_input_tokens=max(u['prompt_tokens'] for u in raw_usage),max_request_bytes=max(r['bytes'] for r in requests),
                context_exceeded=old['context_exceeded'],source_only_verified=True,queries=queries,
                evaluation=dict(tests_run=evaluation.get('tests_run'),checks_executed=evaluation.get('checks_executed'),returncode=evaluation.get('returncode'))))
    baseline={r['index']:r for r in rows if r['method']=='jaccard'}
    for row in rows:
        b=baseline[row['index']];assert b['scorable']==row['scorable']
        row.update(jaccard_correct=b['correct'],token_delta=row['tokens']-b['tokens'],python_delta=row['python_calls']-b['python_calls'],model_call_delta=row['model_calls']-b['model_calls'],
                   outcome_pair='unscorable' if not row['scorable'] else 'both_success' if row['correct'] and b['correct'] else 'gain' if row['correct'] else 'loss' if b['correct'] else 'both_failure')
    summary={}
    for method in NAMES:
        group=[r for r in rows if r['method']==method]
        summary[method]={scope:aggregate([r for r in group if keep(r)]) for scope,keep in {
            'all48':lambda r:True,'scored46':lambda r:r['scorable'],'diagnostic45':lambda r:r['scorable'] and r['index']!=49,
            'diagnostic44':lambda r:r['scorable'] and r['index'] not in (49,56)}.items()}
        valid=[r for r in group if r['scorable']]
        summary[method]['paired']=dict(outcomes=dict(Counter(r['outcome_pair'] for r in valid)),
            gains=[r['task_id'] for r in valid if r['outcome_pair']=='gain'],losses=[r['task_id'] for r in valid if r['outcome_pair']=='loss'],
            lower_token_tasks=sum(r['token_delta']<0 for r in valid),token_delta=sum(r['token_delta'] for r in valid),
            token_ratio=sum(r['tokens'] for r in valid)/sum(baseline[r['index']]['tokens'] for r in valid),
            python_delta=sum(r['python_delta'] for r in valid),median_token_delta=statistics.median(r['token_delta'] for r in valid))
    examples=[]
    for number in (325,559,47,928,983):
        idx=next(i for i,a in enumerate(assets) if i>=48 and a['id']==f'BigCodeBench/{number}');si=source_map[assets[idx]['id']]
        examples.append(dict(index=idx,task_id=f'BigCodeBench/{number}',source_index=si,source_prompt=assets[si]['problem'],target_prompt=assets[idx]['problem'],
            runs=[dict(method=r['method'],correct=r['correct'],tokens=r['tokens'],python_calls=r['python_calls'],memory_calls=r['memory_calls'],
                trajectory=visible(tracked(REPO/r['source_path']/'pi-result.json')['messages']),
                submission=(REPO/r['source_path']/'submission.py').read_text(encoding='utf-8') if (REPO/r['source_path']/'submission.py').exists() else None,
                evaluation=tracked(REPO/r['source_path']/'evaluator.json')) for r in rows if r['index']==idx and r['method'] in ('jaccard','native_files','compact_r3')]))
    sourcescores=[tracked(REPO/'experiments/agent_memory_plan_20261002/runs/full-codeeval-glm-no_memory'/f'{i:03d}'/'evaluator.json') for i in range(48)]
    data=dict(names=NAMES,rows=rows,summary=summary,task_count=336,independent_target_count=48,
        dataset=dict(revision='a01e2ca6e33fd07d9cf80e4bd69a5b3585d3400f',file='codeeval-pro/bigcodebench_lite_pro.dependent.json',
            file_sha256=sha(OBS/'.cache/agentcl-codeeval.json'),source_count=48,target_count=48,source_correct=sum(r.get('correct') is True for r in sourcescores),
            source_scorable=sum(r.get('scorable') is True for r in sourcescores),library_hash=digest(library),library_bytes=len(json.dumps(library,ensure_ascii=False).encode())),
        jaccard_source_ranks=source_ranks,examples=examples,all_source_and_usage_checks_passed=True,model_calls_during_analysis=0,
        method_scope='Frozen Jaccard plus five initial modes and compact r3; r1/r2 are historical context, not extra independent methods',
        limitations=['Same development tasks reused; no held-out test or concurrent randomization','Source exposure is not semantic recall or causal use','Money unknown; total tokens include cached inputs'],
        old_optimization_still_closed=read(OPT/'records/round-budget.json')['closed'])
    save(ROOT/'records/report-data.json',data);save(ROOT/'records/analysis-source-hashes.json',SOURCES)
    print(json.dumps(dict(tasks=len(rows),source_score=(data['dataset']['source_correct'],data['dataset']['source_scorable']),
        rows={m:dict(correct=v['scored46']['correct'],tokens=v['scored46']['tokens'],paired=v['paired']) for m,v in summary.items()}),ensure_ascii=False))


if __name__=='__main__':main()
