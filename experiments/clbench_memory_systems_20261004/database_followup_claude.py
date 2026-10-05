"""Eight isolated native Claude D2 maintenance fixtures, then a review gate."""
from datetime import datetime,timezone
import argparse
import difflib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import threading
import time
import uuid

from prepare import ROOT,read,save,sha
from protocol import digest
from database_followup_d0 import PRIVATE,PUBLIC,ref,restored_prefix
from database_followup_d1 import pump,PORT
import native_client
from native_client import broker,restore,put,snapshot,freeze_runtime
from native_evidence import archive,memory_snapshot,usage_for,validate,validate_attempt_accounting,wait_for_settled_attempts

MEMORY='home/.claude/projects/-state-work-database/memory/'


def sources(index):
    values={}
    for source in range(index+1):
        path=ROOT/'trajectories/claude_code/database'/f'task-{source:03d}.json'
        episode=read(path)
        values[source]={k:episode[k] for k in ['prompt','tools','feedback']}
    return values


def helpers(processes):
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    for name,args in [('request_gate.py',['--ceiling','1']),('native_gateway.py',['--bind','127.0.0.1','--port',str(PORT)])]:
        log=(PRIVATE/(name+'.d2.log')).open('wb')
        processes.append(subprocess.Popen([sys.executable,str(ROOT/name),*args],cwd=ROOT,
            stdout=log,stderr=log,creationflags=flags))
    for _ in range(150):
        if any(p.poll() is not None for p in processes):raise RuntimeError('D2 helper failed')
        try:
            from urllib.request import urlopen
            from urllib.error import HTTPError
            with urlopen(f'http://127.0.0.1:{PORT}/health',timeout=.2):pass
        except HTTPError:return
        except OSError:time.sleep(.1)
    raise RuntimeError('D2 gateway not ready')


def job(index,arm,repeat,runtime_hash,lock,resume=False):
    ident=f'd2-q{index+1}-{arm.lower()}-{repeat}'
    out=PRIVATE/ident;out.mkdir(exist_ok=resume)
    values=sources(index)
    pre=restored_prefix('claude',index)
    original=ROOT/pre['path'];initial=original
    if resume:
        failure=read(out/'failure.json')
        if failure['type']!='TimeoutError' and not any((a.get('http_status') or 0)>=500 for a in usage_for(out)):
            raise RuntimeError('No infrastructure/transport interruption to restore')
        if (out/'result.json').exists():raise RuntimeError('Completed maintenance cannot be replayed')
        history=out/('recovery-history-'+uuid.uuid4().hex[:8]);history.mkdir()
        for name in ['input.json','failure.json','process.json','stopped-native-state.tar.gz']:
            if (out/name).exists():shutil.copy2(out/name,history/name)
        initial=out/'stopped-native-state.tar.gz'
        old_cfg=read(out/'input.json');session=old_cfg['session_id']
        if not any(session in name and '/.claude/projects/' in '/'+name for name in archive(initial)):
            raise RuntimeError('Interrupted native Claude session is missing')
        save(out/'transport-recovery.json',{'authorization':'User requested completing Claude; recover the same infrastructure-interrupted maintenance job, never quality replay',
            'session_id':session,'interrupted_state':ref(initial),'original_before':ref(original),
            'prior_failure':failure,'existing_attempts':usage_for(out),'original_completed_business_feedback_unchanged':True})
    else:session=str(uuid.uuid4())
    route_id=uuid.uuid4().hex;token=uuid.uuid4().hex
    route_path=ROOT/'.local/native-routes'/f'{route_id}.json'
    route={'token':token,'run_id':'database-followup-d2','phase':'native_maintenance_and_any_auxiliary',
        'method_id':'claude_memory_ready',
        'session_id':session,'instance_id':{22:'103',24:'101'}[index],'project_key':'database',
        'config_hash':digest(lock),'audit_relative_path':out.relative_to(ROOT).as_posix(),
        'output_limit':65536,'output_ceiling':65536,'automatic_output_growth':False,'uniform_output_limit':True}
    save(route_path,route)
    extra=read(ROOT/'config/database-followup.plan.json')['D2']['extra_instruction'] if arm=='W1' else ''
    current=json.dumps(values[index],ensure_ascii=False,indent=2)
    prompt=('Maintain the native project memory for the just-completed task from the legal record below. '
        'Historical source records through this event are available at /state/work/database/followup-sources/source-index.json. '
        'Use the existing native memory files and tools. Do not change a business submission or run new business/database queries.\n\n'
        'Completed task legal record:\n'+current)
    if extra:prompt+='\n\n'+extra
    cfg={'framework':'claude','followup_maintenance':True,'session_id':session,'project_key':'database',
        'gateway':f'http://172.30.0.1:{PORT}/r/{route_id}','gateway_token':token,'output_limit':65536,
        'framing':'This is controlled memory maintenance. The task submission and binary feedback are fixed. '
            'Only update files within /state/home/.claude/projects/-state-work-database/memory/. '
            'The source directory contains this method\'s legal history through the current event; no new business actions are available.',
        'prompt':prompt}
    if resume:cfg.update(maintenance_transport_resume=True,maintenance_resume_prompt='Continue this same interrupted memory-maintenance session from its saved source records and memory files. The host waiting window interrupted the unfinished provider stream. Finish the same maintenance operation with the existing tools and budgets; do not redo business actions.')
    save(out/'input.json',cfg)
    source_refs=[{**ref(ROOT/'trajectories/claude_code/database'/f'task-{i:03d}.json'),
        'index':i,'legal_projection_sha256':digest(v)} for i,v in values.items()]
    save(out/'input-materials.json',{'index':index,'arm':arm,'repeat':repeat,'pre_state':pre,
        'sources':source_refs,'source_projection':'prompt, complete tools/action/observation, final legal binary feedback; no posthoc writer text',
        'current_record_sha256':digest(values[index]),'common_prompt_sha256':digest(prompt.removesuffix('\n\n'+extra) if extra else prompt),
        'extra_instruction':extra,'source_cutoff':index,'future_sources':False})
    before_files=archive(original)
    before={n:d for n,d in before_files.items() if n.startswith(MEMORY)}
    container=None;restored=False;started=time.monotonic()
    try:
        container=broker({'op':'create','runtime_hash':runtime_hash})['container_id']
        restore(container,initial)
        restored=True
        catalog=[]
        for i,value in values.items():
            rel=f'/state/work/database/followup-sources/task-{i:03d}.json'
            put(container,rel,value)
            catalog.append({'index':i,'task_position':i+1,'path':rel,'question':value['prompt'].split('\n\n')[1]})
        put(container,'/state/work/database/followup-sources/source-index.json',catalog)
        put(container,f'/state/tasks/{ident}/input.json',cfg)
        native_job=broker({'op':'launch','container_id':container,'task':ident})['job_id']
        save(out/'native-job.json',{'container_id':container,'job_id':native_job})
        while True:
            time.sleep(.5)
            state=broker({'op':'poll','container_id':container,'job_id':native_job})
            if not state['running']:break
            if time.monotonic()-started>1800:raise TimeoutError('D2 maintenance job window exhausted')
        save(out/'process.json',state)
        wait_for_settled_attempts(out,time.monotonic()+600)
        snapshot(container,out/'native-state.tar.gz')
        files=archive(out/'native-state.tar.gz')
        if state['exit_code']:raise RuntimeError('Native maintenance did not complete')
        evidence=validate(files,ident,'claude',session)
        save(out/'native-completion.json',evidence)
        attempts=usage_for(out);validate_attempt_accounting(out,attempts)
        for path in out.glob('requests/*.request.json'):
            p=read(path)
            assert p['model']=='glm-5.3-flash' and p['max_tokens']==65536
            assert p.get('output_config',{}).get('effort')=='high'
        after={n:d for n,d in files.items() if n.startswith(MEMORY)}
        changes={}
        for name in sorted(set(before)|set(after)):
            if before.get(name)!=after.get(name):
                changes[name]=''.join(difflib.unified_diff(before.get(name,b'').decode().splitlines(True),
                    after.get(name,b'').decode().splitlines(True),fromfile='before/'+name,tofile='after/'+name))
        save(out/'memory-diff.json',changes)
        events=[json.loads(l) for l in files[f'tasks/{ident}/events.jsonl'].decode().splitlines()]
        calls=[b for e in events if e.get('type')=='assistant' for b in e['message'].get('content',[]) if b.get('type')=='tool_use']
        results={b['tool_use_id']:b for e in events if e.get('type')=='user' for b in e.get('message',{}).get('content',[]) if isinstance(b,dict) and b.get('type')=='tool_result'}
        assert all(c['name'] in {'Read','Write','Edit','Glob','Grep'} for c in calls)
        rejected=[]
        for c in calls:
            if c['name'] in {'Write','Edit'}:
                if not Path(c['input']['file_path']).as_posix().startswith('/state/'+MEMORY):
                    assert results.get(c['id'],{}).get('is_error'), 'Out-of-scope write was not rejected'
                    rejected.append(c['id'])
        result={'job_id':ident,'phase':'D2','method':'claude_code','arm':arm,'repeat':repeat,
            'index':index,'instance_id':route['instance_id'],'session_id':session,'status':'completed',
            'seconds':round(time.monotonic()-started,3),'pre_state':pre,'inputs':ref(out/'input-materials.json'),
            'attempts':attempts,'attempt_count':len(attempts),'tool_count':len(calls),
            'writes':[{'id':c['id'],'name':c['name'],'path':c['input']['file_path']} for c in calls if c['name'] in {'Write','Edit'}],
            'rejected_write_attempts':rejected,
            'memory_diff':ref(out/'memory-diff.json'),'native_state':ref(out/'native-state.tar.gz'),
            'common_source_cutoff':index,'semantic_review':'pending_source_based_review_not_human_gold',
            'same_session_infrastructure_recovery':resume,
            'cost_basis':'unique native Anthropic gateway attempts; native duplicate usage not added again','monetary_cost':None}
        save(out/'result.json',result);return result
    except Exception as exc:
        save(out/'failure.json',{'type':type(exc).__name__,'message':str(exc)})
        if container:
            broker({'op':'quiesce','container_id':container})
            snapshot(container,out/('stopped-native-state.tar.gz' if restored else 'failed-restore-container.tar.gz'))
        return {'job_id':ident,'phase':'D2','arm':arm,'repeat':repeat,'index':index,'status':'blocked',
                'reason':str(exc),'attempts':usage_for(out),'claim_scores':None}
    finally:
        route['disabled']=True;save(route_path,route)
        if container:broker({'op':'remove','container_id':container})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--recover-infrastructure',action='store_true')
    parser.add_argument('--continue-authorized',action='store_true')
    args=parser.parse_args()
    native_client.BROKER_KIND='default'
    old=read(PUBLIC/'d2-claim-review.json')
    previous=[]
    if old.get('native_jobs',0):
        if args.continue_authorized:
            if old['status']!='blocked' or old['results'][-1]['status']!='blocked':
                raise RuntimeError('Continuation requires an interrupted logical job')
            previous=old['results']
            history=PRIVATE/('d2-continuation-history-'+uuid.uuid4().hex[:8]);history.mkdir()
            for name in ['d2-claim-review.json','d2-runtime-lock.json','d2-continuation-runtime-lock.json']:
                if (PUBLIC/name).exists():shutil.copy2(PUBLIC/name,history/name)
            interrupted=PRIVATE/previous[-1]['job_id']
            failed=read(interrupted/'failure.json')
            if failed['type']=='TimeoutError':
                assert (interrupted/'stopped-native-state.tar.gz').exists()
                pending=[]
                for path in interrupted.glob('requests/*.attempt.json'):
                    meta=read(path)
                    if meta['phase']=='started':
                        shutil.copy2(path,history/path.name)
                        meta.update(phase='failed',error='controller_wait_window_interrupted_unfinished_stream',
                            capture_closed_at=datetime.now(timezone.utc).isoformat(),usage_status='final_provider_usage_unknown')
                        save(path,meta);pending.append(meta['attempt_id'])
                save(history/'interrupted-provider-streams.json',{'attempt_ids':pending,
                    'basis':'Controller timeout, quiesced native process, stopped snapshot and terminated task-owned gateway',
                    'provider_side_charge_and_late_completion':'unknown; neither inferred zero nor replayed as a new logical job'})
        else:
            if not args.recover_infrastructure or any(r.get('attempts') or r['status']!='blocked' for r in old['results']):
                raise RuntimeError('D2 already executed; no automatic quality retry')
            history=PRIVATE/('d2-infrastructure-history-'+uuid.uuid4().hex[:8]);history.mkdir()
            for name in ['d2-claim-review.json','d2-runtime-lock.json']:shutil.copy2(PUBLIC/name,history/name)
            for row in old['results']:
                source=(PRIVATE/row['job_id']).resolve();target=(history/row['job_id']).resolve()
                assert source.is_relative_to(PRIVATE.resolve()) and target.is_relative_to(PRIVATE.resolve())
                if list((source/'requests').glob('*.attempt.json')):raise RuntimeError('Model requests cannot be erased or replayed')
                shutil.move(source,target)
            save(history/'reason.json',{'reason':'Missing gateway method_id before any provider request',
                 'model_calls':0,'native_state_restarted_from_original_before':True})
    runtime_hash=freeze_runtime()
    lock={'schema_version':'database-followup.runtime-lock.v1','phase':'D2','at':datetime.now(timezone.utc).isoformat(),
        'authorization':'User explicitly requested completing Claude using supplied Aixoras documentation',
        'plan_sha256':sha(ROOT/'config/database-followup.plan.json'),'model':'glm-5.3-flash','provider':'aixoras',
        'endpoint':'https://api.aixoras.com/v1/messages','native_framework':'Claude Code 2.1.289',
        'image':'sha256:9fff76673f01c927d531e7c8e0891240c1c9509cf845865e3965edba5ae4ee0d',
        'context_tokens':262144,'max_output_tokens':65536,'compaction_target':196608,'effort':'high',
        'max_maintenance_jobs':8,'max_business_queries':0,'job_concurrency':1,'http_concurrency':1,
        'quality_retry':False,'transport_retry':'native existing transport policy; no answer retry; failed attempts retained',
        'common_native_tools':['Read','Write','Edit','Glob','Grep'],'writes_only':'isolated native project memory via PreToolUse hook',
        'common_adaptations':['native foreground maintenance fixture, no business MCP, same tools/sources in both arms',
            'direct native Anthropic Messages endpoint accepted by user-requested actual probe; no protocol conversion'],
        'native_runtime_hash':runtime_hash,'source_files':{n:sha(ROOT/n) for n in
            ['database_followup_claude.py','native_gateway.py','analysis_provider.py','native_evidence.py','native_client.py']},
        'order':[[22,'W0',1],[22,'W1',1],[24,'W1',1],[24,'W0',1],
                 [22,'W1',2],[22,'W0',2],[24,'W0',2],[24,'W1',2]],
        'hidden_evaluator_mounts':False,'source_policy':'same-method legal prefix through event; before state independently restored',
        'monetary_cost':'unknown account charge, never zero'}
    lock_name='d2-continuation-runtime-lock.json' if args.continue_authorized else 'd2-runtime-lock.json'
    save(PUBLIC/lock_name,lock)
    frozen=PRIVATE/('runtime-source-d2-continuation' if args.continue_authorized else 'runtime-source-d2')
    if frozen.exists() and args.continue_authorized:shutil.copytree(frozen,history/'runtime-source-d2-continuation')
    frozen.mkdir(exist_ok=True)
    for name,h in lock['source_files'].items():
        assert sha(ROOT/name)==h
        (frozen/name).write_bytes((ROOT/name).read_bytes())
    processes=[];stop=threading.Event();rows=[r for r in previous if r['status']=='completed']
    try:
        helpers(processes);threading.Thread(target=pump,args=(stop,),daemon=True).start()
        for index,arm,repeat in lock['order']:
            if any((r['index'],r['arm'],r['repeat'])==(index,arm,repeat) for r in rows):continue
            recover=any((r['index'],r['arm'],r['repeat'])==(index,arm,repeat) and r['status']=='blocked' for r in previous)
            result=job(index,arm,repeat,runtime_hash,lock,resume=recover);rows.append(result)
            save(PRIVATE/'d2-progress.json',{'jobs':rows})
            print(json.dumps({k:result.get(k) for k in ['job_id','status','attempt_count','tool_count','reason']}),flush=True)
            if result['status']!='completed':break
    finally:
        stop.set()
        for process in reversed(processes):
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()
        save(PUBLIC/'d2-claim-review.json',{'phase':'D2','status':'awaiting_semantic_review' if len(rows)==8 and
            all(r['status']=='completed' for r in rows) else 'blocked','native_jobs':len(rows),'results':rows,
            'lock_sha256':sha(PUBLIC/'d2-runtime-lock.json'),'D3_gate':'closed_pending_bounded_claim_review'})
        if args.continue_authorized:
            value=read(PUBLIC/'d2-claim-review.json');value['continuation_lock_sha256']=sha(PUBLIC/lock_name)
            save(PUBLIC/'d2-claim-review.json',value)


if __name__=='__main__':main()
