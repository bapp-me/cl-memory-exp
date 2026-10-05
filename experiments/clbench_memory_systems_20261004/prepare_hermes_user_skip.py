"""Implement the user's explicit task-16 cancellation without inventing a score."""
from datetime import datetime, timezone
from pathlib import Path
import re
from prepare import ROOT, read, save, sha
from protocol import Boundary, digest
from native_evidence import archive, memory_snapshot


def main():
    run='candidate-code-hermes-64k-v2';index=15
    directory=ROOT/'private-runs'/run;out=directory/f'task-{index:03d}'
    authorization=read(ROOT/'records/hermes-code-task16-skip-authorization.json')
    if not authorization['approved'] or authorization['run_id']!=run or authorization['index']!=index:
        raise RuntimeError('Missing exact user skip authorization')
    boundary=Boundary(directory/'boundary.json',read(directory/'manifest.json')['namespace'])
    if not boundary.state['pending'] or boundary.state['pending']['index']!=index or (out/'submission.json').exists():
        raise RuntimeError('Task is no longer the unsubmitted user-selected instance')
    state=read(directory/'evaluator-private/state.json')
    if state['current_issue_idx']!=index:
        raise RuntimeError('Official code task position differs from checkpoint')
    native=out/'native-state.tar.gz';files=archive(native)
    memory=memory_snapshot(files,'hermes');before=read(out/'memory-before.json')
    if memory!=before:
        raise RuntimeError('Interrupted native memory differs from last committed state; review required')
    actions=read(out/'business-actions.json')
    if len(actions)!=state['current_steps']:
        raise RuntimeError('Official interaction count differs from saved actions')
    artifacts=[]
    pattern=re.compile(r"cat >\s*(\S+) <<'EOF'\n(.*?)\nEOF",re.S)
    for target,body in pattern.findall(actions[-1]['action']['command']):
        if target not in ['/state/home/.hermes/cache/scratch/patch_gen.py','/state/home/.hermes/cache/scratch/run_gen_tests.sh']:
            raise RuntimeError('Unexpected generated file path')
        destination=out/'preserved-generated-files'/Path(target).name
        destination.parent.mkdir(exist_ok=True);destination.write_text(body+'\n',encoding='utf8',newline='\n')
        artifacts.append({'original_path':target,'saved_path':destination.relative_to(ROOT).as_posix(),'sha256':sha(destination),'executed_for_preservation':False})
    if len(artifacts)!=2:
        raise RuntimeError('Expected both unexecuted generated scripts')
    evidence={'user_authorized':True,'index':index,'instance_id':read(ROOT/'records/task-manifest.json')['codebase_adaptation'][index]['instance_id'],
        'native_state_sha256':sha(native),'business_actions_sha256':sha(out/'business-actions.json'),
        'business_actions':len(actions),'memory_matches_previous_committed':True,
        'reason':'User clarified to interrupt only task 16 and continue tasks 17-19.',
        'native_state':native.relative_to(ROOT).as_posix(),'generated_files':artifacts,
        'workspace_limitation':'Original temporary business container was removed by the old error-cleanup path; original full filesystem is unavailable. All recorded repository commands were read-only; only two unexecuted scripts outside /testbed were written. Those scripts are recovered verbatim from the command log, not claimed as a container snapshot.',
        'original_base_commit':read(ROOT/'records/task-manifest.json')['codebase_adaptation'][index]['base_commit']}
    save(out/'boundary-before-user-skip.json',boundary.state)
    save(out/'evaluator-state-before-user-skip.json',state)
    # The official question order remains unchanged. Only this unscored question is omitted.
    state['current_issue_idx']=index+1
    state['user_skipped_steps']=state.get('user_skipped_steps',0)+state['current_steps']
    state['current_steps']=0
    save(directory/'evaluator-private/state.json',state)
    receipt=boundary.skip_by_user(index=index,evidence=evidence,memory_version=digest(memory))
    save(out/'user-interruption.json',receipt)
    save(ROOT/'records/hermes-code-user-skip.json',{'at':datetime.now(timezone.utc).isoformat(),
        'run_id':run,'status':'task16_unscored_continue_17_to_19','receipt':receipt,
        'completed_results_unchanged':15,'new_model_calls':0,'business_replayed':False})
    pause_path=ROOT/'records/native-user-pause.json';pause=read(pause_path)
    save(ROOT/'records/native-user-pause-before-task16-only-correction.json',pause)
    pause.update(status='resumed_by_user',resume_requires_user_instruction=False,
        resume_instruction='Only task 16 is cancelled; user explicitly requested tasks 17-19 continue.',
        resume_evidence='records/hermes-code-user-skip.json')
    save(pause_path,pause)
    print({'skipped_unscored_position':16,'next_position':17,'preserved_steps':len(actions),'model_calls':0})


if __name__=='__main__':main()
