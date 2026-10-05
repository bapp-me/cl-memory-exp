"""One authorized correction task, forked from its immutable pre-task state.

Only the three user-requested targets are accepted. No original run is written,
no previous answer to the target is provided, and no subsequent task is run.
"""
import argparse
from datetime import datetime,timezone
import subprocess
import sys
from prepare import ROOT,read,save,sha
from protocol import digest,jaccard

TARGETS={('pi_none',13):'candidate-code-pi-none-v4',
         ('pi_none',16):'candidate-code-pi-none-v4',
         ('pi_jaccard',18):'candidate-code-pi-jaccard-v4'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--method',choices=['pi_none','pi_jaccard'],required=True)
    parser.add_argument('--index',type=int,required=True)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    parent_name=TARGETS[(args.method,args.index)]
    parent=ROOT/'private-runs'/parent_name; original=parent/f'task-{args.index:03d}'
    run_id=f'rerun-code-{args.method.replace("_","-")}-{args.index:03d}-64k-v1'
    directory=ROOT/'private-runs'/run_id
    if directory.exists(): raise RuntimeError('Target already prepared or run; never overwrite or silently repeat it')
    original_manifest=read(parent/'manifest.json'); ns=original_manifest['namespace']
    before=read(original/'memory-before.json')
    assert before['namespace']==ns
    assert all(e['index']<args.index for e in before['history'])
    if args.method=='pi_none': assert not before['history'] and not before['notepad'] and not before['previous_feedback']
    files=['pi_session.mjs','protocol.py','run_pi_database.py','codebase_adapter.py','docker_dispatch.py']
    config_hash=digest({'files':{f:sha(ROOT/f) for f in files},'plan':sha(ROOT/'config/experiment.json'),'namespace':ns})
    original_rows=read(parent/'results.json')
    guard_files=['manifest.json','results.json','memory.json','boundary.json',f'task-{args.index:03d}/memory-before.json',
                 f'task-{args.index:03d}/legal-episode.json',f'task-{args.index:03d}/input.json']
    guard={f:sha(parent/f) for f in guard_files}
    directory.mkdir()
    save(directory/'manifest.json',{'run_id':run_id,'namespace':ns,'mode':'targeted_rerun','config_hash':config_hash,
        'started_at':datetime.now(timezone.utc).isoformat(),'parent_run_id':parent_name,'target_index':args.index,
        'target_instance_id':original_rows[args.index]['instance_id'],'authorization':'direct user request to rerun the three prompt-deviation targets',
        'task_count_authorized':1,'output_limit':65536,'source_memory_policy':'exact original memory-before; recompute own-past retrieval on corrected prompt',
        'source_memory_sha256':sha(original/'memory-before.json'),'parent_guard':guard,
        'source_answer_visible':False,'source_feedback_visible':False,'writeback_to_parent':False,
        'runner_admission_mode':'canary bypasses full-matrix admission; first authorized target also verifies the changed 64k request setting'})
    for file in files+['config/experiment.json']:
        target=directory/'runtime-source'/file;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/file).read_bytes())
    save(directory/'memory.json',before)
    save(directory/'results.json',[])
    save(directory/'boundary.json',{'namespace':ns,'next_index':args.index,'memory_version':digest(before),
        'session_ids':[r['session_id'] for r in original_rows[:args.index]],'pending':None})
    original_checkpoint=read(parent/'evaluator-private/state.json')
    save(directory/'evaluator-private/state.json',{'current_issue_idx':args.index,'current_steps':0,
        'issue_history':original_checkpoint['issue_history'][:args.index]})
    if args.prepare_only:
        print({'prepared':run_id});return
    command=[sys.executable,str(ROOT/'run_pi_database.py'),'--method',args.method,'--environment','codebase_adaptation',
        '--mode','canary','--run-id',run_id,'--resume','--limit',str(args.index+1)]
    process=subprocess.run(command,cwd=ROOT)
    assert all(sha(parent/f)==h for f,h in guard.items()),'Parent evidence was modified'
    if process.returncode: raise RuntimeError('Rerun did not complete; preserve evidence and inspect instead of repeating')
    rows=read(directory/'results.json');assert len(rows)==1 and rows[0]['index']==args.index
    row=rows[0];out=directory/f'task-{args.index:03d}'
    expected_prompt=read(original/'input.json')['prompt'].removeprefix('NOTICE: We are now coding in a new repo.\n\n')
    cfg=read(out/'input.json');assert cfg['prompt']==expected_prompt
    assert read(out/'memory-before.json')==before
    assert row['session_id'] not in {r['session_id'] for r in original_rows}
    selected,_=jaccard(before['history'],expected_prompt,namespace=ns,current_index=args.index) if args.method=='pi_jaccard' else ([],[])
    assert read(out/'retrieval.json')['selected_source_ids']==[s['source_id'] for s in selected]
    for request in (out/'requests').glob('*.request.json'):
        wire=read(request);assert wire['max_tokens']==65536 and wire['model']=='glm-5.3-flash' and wire['reasoning_effort']=='high'
    assert all(a['usage'] and a['returned_model']=='glm-5.3-flash' for a in row['attempts'])
    assert all(a['usage']['prompt_tokens']+65536<=262144 for a in row['attempts'])
    assert read(out/'barrier.json')['durable']
    receipt={'status':'passed','run_id':run_id,'parent_run_id':parent_name,'index':args.index,'instance_id':row['instance_id'],
        'new_session_id':row['session_id'],'original':{k:original_rows[args.index][k] for k in ['correct','actions','reward']},
        'rerun':{k:row[k] for k in ['correct','actions','reward','seconds']},'target_count':1,
        'corrected_prompt_verified':True,'original_pre_task_memory_verified':True,'parent_unchanged':True,
        'actual_output_limit':65536,'total_tokens':sum(a['usage']['total_tokens'] for a in row['attempts']),
        'raw_evidence':out.relative_to(ROOT).as_posix(),'note':'Replace this target regardless of improved or worsened outcome; this is not a pure prompt-effect ablation because the output cap also changed.'}
    save(directory/'rerun-audit.json',receipt)
    save(ROOT/'records'/f'{run_id}.json',receipt)
    print(receipt)


if __name__=='__main__':main()
