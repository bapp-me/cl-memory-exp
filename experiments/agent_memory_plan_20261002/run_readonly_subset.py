"""Twelve preregistered seen-target probes; wait for both first passes, never write memory."""
import concurrent.futures
import json
import time
import hashlib
from core import ROOT, CodeTask, CODE_TOOLS, run_pi, grade_code, save, digest
from run_stream import rows_for

RUN='readonly12-codeeval-glm-episodic_retrieval'
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def select():
    rows=rows_for('full')
    issues={(x['category'],x['id']) for x in read(ROOT/'records/scorer-issues.json')['issues']}
    eligible=[i for i,r in enumerate(rows) if r['category']=='new' and (r['category'],r['id']) not in issues]
    indices=[eligible[round(i*(len(eligible)-1)/11)] for i in range(12)]
    record={'original_indices':indices,'task_ids':[rows[i]['category']+':'+rows[i]['id'] for i in indices],
            'rule':'12 evenly spaced valid complex targets in original order; exclude preregistered broken scorers; no outcome-based selection',
            'scope':'Seen-target read-only subset, not full native second pass or unseen generalization'}
    path=ROOT/'records/readonly12-selection.json'
    if path.exists():assert read(path)==record
    else:save(path,record)
    return [rows[i] for i in indices],record

def one(index,row,history):
    folder=ROOT/'runs'/RUN/f'{index:03d}'
    if (folder/'commit.json').exists():
        c=read(folder/'commit.json');assert c['before_hash']==c['after_hash']==digest(history)
        return c['result']
    if (folder/'events.jsonl').exists():raise RuntimeError(f'Uncommitted probe: {folder}')
    task=CodeTask(row,ROOT/'.runtime/workspaces'/RUN/f'{index:03d}')
    _,execution=run_pi('glm',row['problem'],history,'episodic_retrieval',task,CODE_TOOLS,folder)
    if (execution['error'] or execution['stop_reason'] in ['error','aborted']) and not (execution['response_timed_out'] or execution['context_exceeded']):
        save(folder/'infrastructure-failure.json',execution);raise RuntimeError(str(folder))
    score=grade_code(row,task.submission or '')
    save(folder/'evaluator.json',score);save(folder/'memory-after.json',history)
    result={'index':index,'task_id':row['category']+':'+row['id'],**execution,'correct':score['correct'],'scorable':score['scorable'],'tests_run':score['tests_run'],'checks_executed':score.get('checks_executed')}
    save(folder/'commit.json',{'before_hash':digest(history),'after_hash':digest(history),'result':result})
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--register-only',action='store_true');p.add_argument('--workers',type=int,default=8);args=p.parse_args()
    assert 1<=args.workers<=12
    rows,selection=select()
    if args.register_only:print(json.dumps(selection));raise SystemExit(0)
    while not all((ROOT/'runs'/f'full-codeeval-glm-{m}'/'final-memory.json').exists() and len(list((ROOT/'runs'/f'full-codeeval-glm-{m}').glob('*/commit.json')))==96 for m in ['no_memory','episodic_retrieval']):time.sleep(5)
    history=read(ROOT/'runs/full-codeeval-glm-episodic_retrieval/final-memory.json')
    root=ROOT/'runs'/RUN;root.mkdir(exist_ok=True)
    manifest={'provider':'glm','benchmark':'codeeval','phase':'readonly_subset','method':'episodic_retrieval','task_ids':selection['task_ids'],'repetition':1,'readonly':True,'initial_memory_hash':digest(history),'workers':args.workers}
    if (root/'manifest.json').exists():assert read(root/'manifest.json')==manifest
    else:save(root/'manifest.json',manifest)
    save(root/'source-snapshot.json',{'files':{n:{'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in ['core.py','pi_runner.mjs','run_readonly_subset.py']}})
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending=[pool.submit(one,i,row,history) for i,row in enumerate(rows)]
        try:
            for future in concurrent.futures.as_completed(pending):
                results.append(future.result());save(root/'summary.json',sorted(results,key=lambda x:x['index']))
                print(json.dumps({'completed':len(results),'total':12}),flush=True)
        except BaseException:
            for f in pending:f.cancel()
            raise
    assert digest(history)==manifest['initial_memory_hash']
    save(root/'final-memory.json',history)
