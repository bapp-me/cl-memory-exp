"""Mechanical audit of committed results; no model calls or hidden-data export."""
from collections import Counter
import json
from prepare import ROOT,read,save,sha
from protocol import digest,database_feedback,jaccard


def main():
    manifest=read(ROOT/'records/task-manifest.json'); summaries=[]; all_sessions=set()
    for directory in sorted((ROOT/'private-runs').iterdir()):
        if not (directory/'manifest.json').exists(): continue
        run=read(directory/'manifest.json')
        if run.get('mode')!='formal': continue
        method,_,environment=run['namespace'].split('/')
        rows=read(directory/'results.json') if (directory/'results.json').exists() else []
        previous_memory=None; errors=[]; metrics=Counter(); max_prompt=0
        for index,row in enumerate(rows):
            def check(condition,message):
                if not condition: errors.append({'index':index,'check':message})
            out=directory/f'task-{index:03d}'
            check(row['index']==index and str(row['instance_id'])==str(manifest[environment][index]['instance_id']),'fixed official order')
            check(row['session_id'] not in all_sessions,'fresh session across instances/methods/environments')
            all_sessions.add(row['session_id'])
            grade=read(directory/'evaluator-private'/f'result-{index:03d}.json'); record=grade['record']
            check(row['correct']==record['correct' if environment=='database_exploration' else 'success'],'official correctness')
            check(row['actions']==record['num_queries' if environment=='database_exploration' else 'steps'],'official action count')
            if grade['outcome']: check(row['reward']==grade['outcome']['reward'],'official reward')
            if record.get('eval_status')=='system_error': metrics['official_format_failures']+=1
            before,after=read(out/'memory-before.json'),read(out/'memory-after.json')
            if previous_memory is not None: check(before==previous_memory,'previous committed memory loaded')
            previous_memory=after
            episode=read(out/'legal-episode.json'); barrier=read(out/'barrier.json')
            check(digest(episode)==row['source_watermark']==barrier['source_watermark'],'final legal watermark')
            check(barrier['durable'] and barrier['status'] in {'not_applicable','completed_noop','completed_changed','completed_staged'},'completed durable barrier')
            if environment=='database_exploration':
                check(episode['feedback']==database_feedback(record,index+1),'feedback allowlist hides gold')
            submission=read(out/'submission.json')
            artifact=submission.get('artifact')
            if artifact:
                check((directory/artifact['path']).exists() and sha(directory/artifact['path'])==artifact['sha256'],'frozen submitted artifact hash')
            if method=='pi_none': check(before==after and not after['history'] and not after['notepad'] and not after['previous_feedback'],'no explicit cross-instance memory')
            if method=='pi_jaccard':
                selected,_=jaccard(before['history'],read(out/'input.json')['prompt'],namespace=run['namespace'],current_index=index)
                check([s['source_id'] for s in selected]==read(out/'retrieval.json')['selected_source_ids'],'own-past Jaccard top-3 selection')
                check(len(after['history'])==index+1 and after['history'][-1]==episode,'exactly one legal episode appended')
            for p in (out/'requests').glob('*.request.json'):
                request=read(p); check(request['model']=='glm-5.3-flash','same requested model')
                cap=request.get('max_tokens',request.get('max_output_tokens'))
                check(cap is not None and 0<cap<=131072,'bounded actual output cap')
                if method.startswith('pi_'): check(request.get('reasoning_effort')=='high','Pi actual high mapping')
            for attempt in row['attempts']:
                metrics['attempts']+=1
                usage=attempt.get('usage')
                check(attempt.get('returned_model') in {None,'glm-5.3-flash'},'no returned model fallback')
                if not usage: metrics['unknown_usage_attempts']+=1; continue
                if 'prompt_tokens' in usage: prompt=usage['prompt_tokens']
                else: prompt=usage.get('input_tokens',0)+usage.get('cache_read_input_tokens',0)+usage.get('cache_creation_input_tokens',0)
                # Responses input_tokens already includes cache, and does not have the Anthropic top-level cache fields.
                max_prompt=max(max_prompt,prompt)
                request=read(out/'requests'/f"{attempt['attempt_id']}.request.json")
                cap=request.get('max_tokens',request.get('max_output_tokens'))
                check(prompt+cap<=262144,'reported input plus reserved output fits common window')
            metrics['tasks']+=1
            metrics['correct']+=int(row['correct']); metrics['official_actions']+=row['actions']
            metrics['unknown_task_wall_times']+=int(bool(row.get('seconds_basis')) or row.get('seconds') is None)
        summaries.append({'run_id':directory.name,'method':method,'environment':environment,
            'committed_tasks':len(rows),'full_schedule':len(rows)==len(manifest[environment]),'status':'passed' if not errors else 'failed',
            'metrics':dict(metrics),'maximum_reported_input_tokens':max_prompt,'errors':errors})
    output={'status':'passed' if all(s['status']=='passed' for s in summaries) else 'failed',
        'scope':'committed formal tasks only; unfinished submissions and maintenance are not silently admitted',
        'model_calls':0,'streams':summaries,'checks':['official order and grader parity','unique native sessions',
            'memory handoff and own-past retrieval','legal feedback projection','frozen submission hashes',
            'actual model/effort/output budget and measured window','all reported failed-attempt usage retained as unknown']}
    save(ROOT/'records/mechanical-audit.json',output)
    print(json.dumps({'status':output['status'],'streams':[(s['run_id'],s['committed_tasks'],s['status'],s['errors']) for s in summaries]}))


if __name__=='__main__': main()
