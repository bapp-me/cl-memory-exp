"""Sequential online stream with task commit points and resume checks."""
import argparse
import json
import hashlib
from core import ROOT,CACHE,Database,CodeTask,DB_TOOLS,CODE_TOOLS,run_pi,grade_code,save,digest

def rows_for(mode):
    rows=json.loads((CACHE/'agentcl-codeeval.json').read_text(encoding='utf-8'))
    if mode=='full':return rows
    manifest=json.loads((ROOT/'records/agentcl-selection.json').read_text(encoding='utf-8'))
    selected={(x['category'],x['id']) for x in manifest['ordered_task_ids']}
    if mode=='calibration':
        first=manifest['ordered_task_ids'][0]['id']
        return [r for r in rows if r['id']==first]
    return [r for r in rows if (r['category'],r['id']) in selected]

def run(args):
    root=ROOT/'runs'/args.run_id
    root.mkdir(parents=True,exist_ok=True)
    history=[]
    db=Database() if args.benchmark=='database' else None
    rows=db.rows if db else rows_for(args.phase)
    if db and args.phase=='calibration':rows=rows[:20]
    readonly=args.frozen_memory is not None
    if readonly:history=json.loads(args.frozen_memory.read_text(encoding='utf-8'))
    manifest={'provider':args.provider,'benchmark':args.benchmark,'phase':args.phase,'method':args.method,
              'task_ids':[str(r['question_id']) if db else r['category']+':'+r['id'] for r in rows],
              'repetition':1,'readonly':readonly,'initial_memory_hash':digest(history)}
    if (root/'manifest.json').exists():
        if json.loads((root/'manifest.json').read_text(encoding='utf-8'))!=manifest:raise RuntimeError('Resume configuration mismatch')
    else:save(root/'manifest.json',manifest)
    if not (root/'source-snapshot.json').exists():
        files=['core.py','pi_runner.mjs','run_stream.py','sandbox.sh','records/protocol.json']
        save(root/'source-snapshot.json',{'files':{name:{'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),'text':(ROOT/name).read_text(encoding='utf-8')} for name in files},
                                        'note':'Captured before starting this process; resumed earlier calibration tasks may predate this snapshot.'})
    summary=[]
    for index,row in enumerate(rows):
        folder=root/f'{index:03d}'
        if (folder/'commit.json').exists():
            committed=json.loads((folder/'commit.json').read_text(encoding='utf-8'))
            if committed['before_hash']!=digest(history):raise RuntimeError('State chain mismatch')
            summary.append(committed['result'])
            if not readonly:history=json.loads((folder/'memory-after.json').read_text(encoding='utf-8'))
            continue
        if (folder/'events.jsonl').exists():
            raise RuntimeError(f'Uncommitted attempt at {folder}; audit before retry')
        before=digest(history)
        if db:
            db.start(index);task=db;prompt=db.prompt();tools=DB_TOOLS
        else:
            task=CodeTask(row,ROOT/'.runtime/workspaces'/args.run_id/f'{index:03d}')
            prompt=row['problem'];tools=CODE_TOOLS
        episode,execution=run_pi(args.provider,prompt,history,args.method,task,tools,folder)
        if (execution['error'] or execution['stop_reason'] in ['error','aborted']) and not (execution['response_timed_out'] or execution['context_exceeded']):
            save(folder/'infrastructure-failure.json',execution)
            raise RuntimeError(f'Model/runtime failure at {folder}; investigate before resume')
        score=db.score() if db else grade_code(row,task.submission or '')
        # Full grader logs stay researcher-only and are never used in memory.
        save(folder/'evaluator.json',score)
        if not readonly and args.method!='no_memory':history.append(episode)
        save(folder/'memory-after.json',history)
        record={'index':index,'task_id':manifest['task_ids'][index],**execution,
                'correct':score['correct'],'scorable':score['scorable'],
                **({'queries':score['queries'],'reward':score['reward']} if db else {'tests_run':score['tests_run'],'checks_executed':score.get('checks_executed')})}
        save(folder/'commit.json',{'before_hash':before,'after_hash':digest(history),'result':record})
        summary.append(record)
        save(root/'summary.json',summary)
        print(json.dumps({'run':args.run_id,'task':index+1,'total':len(rows),'correct':record['correct'],'seconds':record['seconds'],'tokens':record['usage']['totalTokens']}),flush=True)
    save(root/'final-memory.json',history)
    save(root/'summary.json',summary)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--provider',choices=['deepseek','glm'],required=True)
    p.add_argument('--benchmark',choices=['database','codeeval'],required=True)
    p.add_argument('--phase',choices=['calibration','pilot','full'],required=True)
    p.add_argument('--method',choices=['no_memory','bounded_icl','episodic_retrieval'],required=True)
    p.add_argument('--run-id',required=True)
    from pathlib import Path
    p.add_argument('--frozen-memory',type=Path)
    run(p.parse_args())
