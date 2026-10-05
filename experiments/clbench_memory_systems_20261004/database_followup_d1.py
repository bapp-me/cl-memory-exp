"""Run only the preregistered eight isolated Codex D1 jobs, then stop.

Uses the accepted native binary and current Responses endpoint. No new provider
canary, protocol discovery, writer, whole-stream replay or quality retry.
"""
from datetime import datetime, timezone
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import tarfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

from prepare import ROOT, UPSTREAM, read, save, sha
from protocol import digest, project_episode
import native_client
from native_client import broker, restore, put, snapshot, freeze_runtime
from native_evidence import archive, memory_snapshot, usage_for, validate_attempt_accounting
from database_followup_d0 import PRIVATE, PUBLIC, ref, restored_prefix

PORT = 43195
native_client.BROKER_KIND = 'codex'


def sidebar(index):
    sources = {33: [30,31,32], 27: [24,25,26]}[index]
    records = []
    for source in sources:
        assert source < index
        episode = read(ROOT / 'trajectories/codex/database' / f'task-{source:03d}.json')
        records.append({k: episode[k] for k in ['prompt','tools','feedback']})
    return json.dumps(records, ensure_ascii=False, indent=2)


def recovery_archive(out,history,session):
    """Retain settled payloads; omit only regenerated Codex launcher symlinks."""
    source=out/'stopped-native-state.tar.gz'
    with tarfile.open(source) as original:
        names=[m.name for m in original.getmembers()]
    if not any(session in name and '/sessions/' in name for name in names):
        source=out/'native-state.tar.gz'
    shutil.copy2(source,history/source.name)
    kept=history/source.name
    target=out/'recovery-mount-state.tar.gz'
    excluded=[]
    with tarfile.open(kept) as original,tarfile.open(target,'w:gz') as cleaned:
        for item in original.getmembers():
            if item.issym() and '/home/.codex/tmp/arg0/' in item.name and item.linkname=='/native/codex':
                excluded.append({'name':item.name,'target':item.linkname});continue
            if not(item.isfile() or item.isdir()):raise ValueError('Unknown native state link')
            cleaned.addfile(item,original.extractfile(item) if item.isfile() else None)
    save(history/'restore-normalization.json',{'source':ref(kept),'mounted':ref(target),
        'excluded_regenerated_launcher_links':excluded,
        'state_database_session_and_regular_file_bytes_unchanged':True,
        'fallback_to_independent_settled_native_snapshot':source.name!='stopped-native-state.tar.gz'})
    return target


def pump(stop):
    seen = set()
    def serve(job):
        request = read(job / 'request.json')
        headers = {k:v for k,v in request['headers'].items()
                   if k.lower() not in {'host','connection','content-length'}}
        req = Request(f'http://127.0.0.1:{PORT}' + request['path'],
                      data=(job/'body.bin').read_bytes(), headers=headers)
        try:
            try:
                response = urlopen(req, timeout=630)
            except HTTPError as exc:
                response = exc
            with response, (job/'response.bin').open('wb') as output:
                save(job/'response.json', {'status':response.code,
                    'content_type':response.headers.get('Content-Type','application/json')})
                while data := response.read1(16384):
                    output.write(data)
                    output.flush()
        except Exception as exc:
            if not (job/'response.json').exists():
                (job/'response.bin').write_text(json.dumps({'error':type(exc).__name__}))
                save(job/'response.json', {'status':502,'content_type':'application/json'})
        finally:
            (job/'done').write_text('done')
    while not stop.wait(.05):
        for path in (PRIVATE/'spool').glob('*/request.json'):
            if path.parent.name not in seen:
                seen.add(path.parent.name)
                if not (path.parent/'done').exists():
                    threading.Thread(target=serve,args=(path.parent,),daemon=True).start()


def infra(processes, existing_broker=False):
    """Start task-owned helpers, never load the key in WSL or agent mounts."""
    no_window = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    helpers=[('request_gate.py',['--ceiling','1']),
             ('native_gateway.py',['--bind','127.0.0.1','--port',str(PORT),'--kind','codex'])]
    if not existing_broker:
        helpers.insert(1,('native_broker.py',['--kind','codex']))
    for name, args in helpers:
        log = (PRIVATE/(name+'.log')).open('wb')
        processes.append(subprocess.Popen([sys.executable,str(ROOT/name),*args],cwd=ROOT,
            stdout=log,stderr=log,creationflags=no_window))
    # Same credential-free spool relay as the accepted experiment, new private
    # spool/port so old records and services cannot be mixed into this run.
    code = (ROOT/'wsl_spool_relay.py').read_text('utf8')
    start = code.index("ROOT = Path(__file__).resolve().parent")
    end = code.index('\nROOT.mkdir',start)
    wsl_path = '/mnt/d/' + PRIVATE.relative_to(Path('D:/')).as_posix()
    code = code[:start] + 'ROOT = Path(' + repr(wsl_path+'/spool') + ')' + code[end:]
    (PRIVATE/'relay.py').write_text(code,encoding='utf8')
    (PRIVATE/'spool').mkdir(exist_ok=True)
    log = (PRIVATE/'relay.log').open('wb')
    if not existing_broker:
        processes.append(subprocess.Popen(['wsl','-d','Ubuntu','-u','root','--exec','python3',
            wsl_path+'/relay.py','--port',str(PORT)],stdout=log,stderr=log,creationflags=no_window))
    for _ in range(100):
        if any(p.poll() is not None for p in processes):
            raise RuntimeError('Task helper failed; inspect private helper logs')
        try:
            with urlopen(f'http://127.0.0.1:{PORT}/health-unavailable',timeout=.2):
                pass
        except HTTPError:
            return processes
        except OSError:
            time.sleep(.1)
    raise RuntimeError('Task gateway did not start')


def job(index, arm, repeat, runtime_hash, lock, resume=False):
    from database_adapter import DatabaseStream
    ident = f'd1-q{index+1}-{arm.lower()}-{repeat}'
    out = PRIVATE / ident
    out.mkdir(exist_ok=resume)
    state_ref = restored_prefix('codex',index)
    initial = ROOT/state_ref['path']
    recovered_session=None
    if resume:
        if (out/'submission.json').exists():
            raise RuntimeError('Submitted work cannot be replayed')
        failed=usage_for(out)
        if not failed or not any((a['http_status'] or 0)>=500 for a in failed):
            raise RuntimeError('No captured transport failure to recover')
        history=out/('recovery-history-'+uuid.uuid4().hex[:8]);history.mkdir()
        for name in ['input.json','process.json','failure.json','attempts.json']:
            if (out/name).exists():shutil.copy2(out/name,history/name)
        recovered_session=read(out/'session-start.json')['session_id']
        initial=recovery_archive(out,history,recovered_session)
        save(out/'transport-recovery.json',{'authorization':'User explicitly requested restoring Codex HTTP 520 interruption',
            'initial_snapshot':ref(initial),'session_id':recovered_session,
            'business_state_before':ref(out/'evaluator-private/state.json'),
            'actions_before':ref(out/'business-actions.json'),'existing_failed_attempts':failed})
    historical = ROOT / 'private-runs/formal-db-codex-r1' / f'task-{index:03d}'
    cfg0 = read(historical/'input.json')
    prompt = cfg0.get('benchmark_prompt',cfg0['prompt'])
    extra = sidebar(index) if arm=='R1' else ''
    if extra:
        prompt += '\n\nRecent completed same-method task evidence (chronological, original records):\n' + extra
    if not resume:save(out/'inputs-public-fields.json', {'index':index,'arm':arm,'repeat':repeat,
        'prompt_sha256':digest(prompt),'sidebar_sha256':digest(extra) if extra else None,
        'sidebar_bytes':len(extra.encode()),'pre_state':state_ref})
    stream = DatabaseStream(out,restore=resume)
    # Correct post-drift environment, isolated from every other target/arm.
    # No prior business task is executed to reach the selected target.
    if not resume:
        stream.task._conn.close()
        db = out/'evaluator-private/target.db'
        shutil.copy2(UPSTREAM/'data/database_exploration/products_drifted.db',db)
        import sqlite3
        stream.task._conn=sqlite3.connect(db)
        stream.task._temp_db_path=db
        stream.task._current_question_idx=index
        stream.task._queries_this_question=0
        stream.task._drift_applied=True
        stream.task._stage_change_notice=None
        stream.task._question_history=[]
        stream.task._awaiting_action=True
        stream.query=stream.task.build_current_query()
    assert stream.public_query()['instance_id']=={33:'107',27:'110'}[index]
    if not resume:assert stream.query.prompt==cfg0.get('benchmark_prompt',cfg0['prompt'])
    complete=False
    actions=read(out/'business-actions.json') if resume else []
    session=recovered_session
    tool_token=uuid.uuid4().hex
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            nonlocal complete,session
            if self.headers.get('X-Run-Token')!=tool_token:
                self.send_error(403);return
            value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            try:
                if value.get('control')=='session_start':
                    session=str(uuid.UUID(value['session_id']))
                    route['session_id']=session
                    save(route_path,route)
                    save(out/'session-start.json',{'session_id':session})
                    result={'registered':True}
                elif complete:
                    self.send_error(409);return
                else:
                    if value.get('control')=='final_response':
                        from src.systems.codex.system import _parse_action_text
                        action=_parse_action_text(value['text'],stream.query.response_schema).model_dump()
                    else:
                        action=value['action']
                    result=stream.action(action)
                    actions.append({'action':action,'observation':result['observation'],
                                    'toolCallId':value['toolCallId']})
                    save(out/'business-actions.json',actions)
                    complete=result['instance_complete']
                    if complete:
                        save(out/'submission.json',{'action':action,'feedback':result['observation']})
                data=json.dumps(result).encode()
                self.send_response(200)
                self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
            except Exception as exc:
                save(out/'controller-error.json',{'error':type(exc).__name__,'message':str(exc)})
                self.send_error(500)
    server=HTTPServer(('127.0.0.1',0),Handler);server.timeout=.2
    route_id=uuid.uuid4().hex;route_token=uuid.uuid4().hex
    route_path=ROOT/'.local/native-routes'/f'{route_id}.json'
    route={'token':route_token,'run_id':'database-followup-d1','method_id':'codex_memory_ready',
        'instance_id':stream.query.instance_id,'project_key':'database','session_id':session,
        'phase':'solver','config_hash':digest(lock),'audit_relative_path':out.relative_to(ROOT).as_posix(),
        'tool_url':f'http://127.0.0.1:{server.server_port}/tool','tool_token':tool_token,
        'output_limit':65536,'output_ceiling':65536,'automatic_output_growth':False,'uniform_output_limit':True}
    save(route_path,route)
    cfg={**cfg0,'session_id':str(uuid.uuid4()),'output_limit':65536,'output_ceiling':65536,
        'automatic_output_growth':False,'gateway':f'http://172.30.0.1:{PORT}/r/{route_id}',
        'gateway_token':route_token,'prompt':prompt,'followup_solver_only':True}
    cfg.pop('consolidation_schedule',None)
    if resume:
        cfg.update(session_id=recovered_session,solver_transport_resume=True,
            transport_resume_prompt='Continue the same interrupted instance from its saved conversation and business state. The provider HTTP 520 was a transport failure. Do not repeat already completed queries or change the query budget; finish this same instance.')
    save(out/'input.json',cfg)
    container=None;restored=False
    started=time.monotonic()
    try:
        container=broker({'op':'create','runtime_hash':runtime_hash})['container_id']
        restore(container,initial)
        restored=True
        put(container,f'/state/tasks/{ident}/input.json',cfg)
        native_job=broker({'op':'launch','container_id':container,'task':ident})['job_id']
        save(out/'native-job.json',{'container_id':container,'job_id':native_job})
        next_poll=0
        while True:
            server.handle_request()
            if time.monotonic()-started>1800:
                raise TimeoutError('Bounded single-job window exhausted')
            if time.monotonic()>next_poll:
                state=broker({'op':'poll','container_id':container,'job_id':native_job})
                next_poll=time.monotonic()+2
                if not state['running']:break
        save(out/'process.json',state)
        snapshot(container,out/'native-state.tar.gz')
        files=archive(out/'native-state.tar.gz')
        attempts=usage_for(out)
        save(out/'attempts.json',attempts)
        if state['exit_code'] or not complete:
            raise RuntimeError('Native process/instance incomplete; no quality retry')
        validate_attempt_accounting(out,attempts)
        receipt=json.loads(files[f'tasks/{ident}/followup-solver-receipt.json'])
        assert receipt['session_id']==session and not receipt['source_selector_present']
        assert receipt['startup_memory_jobs_disabled'] and not receipt['post_task_maintenance_started']
        # Verify intervention exposure in actual provider inputs, every role.
        exposure=[]
        for path in out.glob('requests/*.native-request.json'):
            payload=read(path)
            cm=payload.get('client_metadata',{})
            turn=json.loads(cm.get('x-codex-turn-metadata','{}'))
            assert turn.get('request_kind')=='turn' and cm.get('thread_id')==session
            raw=json.dumps(payload.get('input'),ensure_ascii=False)
            marker='Recent completed same-method task evidence'
            assert (marker in raw)==bool(extra)
            exposure.append({**ref(path),'sidebar_present':marker in raw})
        before=read(historical/'memory-before.json')
        after=memory_snapshot(files,'codex')
        save(out/'memory-diff.json',{'before':before,'after':after})
        graded=read(out/'evaluator-private'/f'result-{index:03d}.json')
        grade=graded['record']
        episode=project_episode(namespace='database-followup/D1/'+ident,index=index,
            instance_id=stream.query.instance_id if stream.query else {33:'107',27:'110'}[index],
            prompt=prompt,assistant_text=[],tools=actions,feedback=actions[-1]['observation'])
        save(out/'legal-episode.json',episode)
        answer=read(out/'submission.json')['action']['content']
        return {'job_id':ident,'phase':'D1','method':'codex','arm':arm,'repeat':repeat,
            'index':index,'instance_id':{33:'107',27:'110'}[index],'session_id':session,
            'status':'completed','official_correct':grade['correct'],'reward':graded['outcome']['reward'],
            'queries':grade['num_queries'],'answer':answer,'seconds':round(time.monotonic()-started,3),
            'sidebar_bytes':len(extra.encode()),'pre_state':state_ref,'actual_inputs':exposure,
            'memory_refresh_receipt':receipt,'memory_files_changed':before!=after,
            'attempts':attempts,'attempt_count':len(attempts),
            'usage_basis':'one gateway usage entry per unique attempt; native usage not added again',
            'failed_unknown_usage_attempts':[a['attempt_id'] for a in attempts if a['usage'] is None],
            'monetary_cost':None,'monetary_cost_status':'unknown_account_debit',
            'business_actions':ref(out/'business-actions.json'),
            'transport_recovered_same_session':resume}
    except Exception as exc:
        save(out/'failure.json',{'type':type(exc).__name__,'message':str(exc)})
        if container:
            broker({'op':'quiesce','container_id':container})
            snapshot(container,out/('stopped-native-state.tar.gz' if restored else 'failed-restore-container.tar.gz'))
        return {'job_id':ident,'phase':'D1','arm':arm,'repeat':repeat,'index':index,
            'status':'blocked','reason':str(exc),'failure_type':type(exc).__name__,
            'attempts':usage_for(out),'score':None}
    finally:
        route['disabled']=True;save(route_path,route)
        server.server_close();stream.close()
        if container:broker({'op':'remove','container_id':container})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--recover-infrastructure',action='store_true')
    parser.add_argument('--existing-broker',action='store_true')
    parser.add_argument('--continue-authorized',action='store_true')
    args=parser.parse_args()
    previous_rows=[]
    if args.continue_authorized:
        previous=read(PUBLIC/'d1-paired-results.json')
        if previous['status']!='blocked' or len(previous['results'])!=4:
            raise RuntimeError('Continuation must match the saved four-job interruption')
        previous_rows=previous['results']
        history=PRIVATE/('continuation-history-'+uuid.uuid4().hex[:8]);history.mkdir()
        for name in ['d1-paired-results.json','d1-runtime-lock.json','conclusion.json','verification.json']:
            shutil.copy2(PUBLIC/name,history/name)
    elif (PUBLIC/'d1-paired-results.json').exists():
        old=read(PUBLIC/'d1-paired-results.json')
        if not args.recover_infrastructure or old['native_jobs'] or old['results']:
            raise RuntimeError('D1 result already exists; no solver/quality rerun authorized')
        history=PRIVATE/('infrastructure-history-'+uuid.uuid4().hex[:8])
        history.mkdir()
        for source in [PUBLIC/'d1-paired-results.json',PUBLIC/'d1-runtime-lock.json',
                       PRIVATE/'infra-failure.json',PRIVATE/'native_gateway.py.log']:
            shutil.copy2(source,history/source.name)
    assert read(PUBLIC/'d0-evidence.json')['status']=='completed'
    plan=read(ROOT/'config/database-followup.plan.json')
    assert read(ROOT/'config/active-provider.json')['provider']=='aixoras'
    runtime_hash=freeze_runtime()
    lock={'schema_version':'database-followup.runtime-lock.v1','phase':'D1',
        'at':datetime.now(timezone.utc).isoformat(),'plan_sha256':sha(ROOT/'config/database-followup.plan.json'),
        'authorization':'Current user asked to complete the bounded follow-up plan',
        'native_jobs_cap':8,'solver_jobs_cap':8,'maintenance_jobs_cap':0,
        'job_concurrency':1,'all_role_http_concurrency':1,'model':'glm-5.3-flash',
        'provider':'aixoras','endpoint':'https://api.aixoras.com/v1/responses',
        'context_window_tokens':262144,'output_tokens':65536,'compaction_trigger_tokens':196608,
        'effort':'high','database_query_budget':15,'quality_retry':False,'provider_fallback':None,
        'transport_policy':'same pinned CLI request_max_retries=0 / stream_max_retries=0; preserve failed attempts and stop',
        'native_runtime_hash':runtime_hash,'codex_build':ref(ROOT/'records/codex-build.json'),
        'codex_binary_sha256':sha(ROOT/'.local/native-bin/codex'),
        'source_files':{n:sha(ROOT/n) for n in ['database_followup_d1.py','database_adapter.py','native_gateway.py','request_gate.py','protocol.py']},
        'grading':read(PUBLIC/'d0-evidence.json')['grading'],
        'common_adaptations':['current accepted Responses route used by both arms; fresh concurrent-period R0',
            'native startup boundary patch disables jobs without source selector; post-task writer omitted equally',
            'each job restores original complete archive preceding its target; correct drifted DB in evaluator only'],
        'order':[[33,'R0',1],[33,'R1',1],[27,'R1',1],[27,'R0',1],
                 [33,'R1',2],[33,'R0',2],[27,'R0',2],[27,'R1',2]],
        'hidden_material_mounts':False,'monetary_cap':None,
        'cost_policy':'all attempts input/output/cache/unknown retained, unknown cost never zero'}
    lock['execution_identity_policy']='Aixoras credential owner runs host gateway; credential-free ordinary-account broker/relay accesses WSL'
    lock_name='d1-continuation-runtime-lock.json' if args.continue_authorized else 'd1-runtime-lock.json'
    if args.continue_authorized:
        lock.update(authorization='User explicitly requested resuming the Codex 520 interruption and completing Claude',
            original_runtime_lock=ref(PUBLIC/'d1-runtime-lock.json'),
            same_session_transport_recovery_authorized=True)
    save(PUBLIC/lock_name,lock)
    save(PRIVATE/lock_name,lock)
    frozen=PRIVATE/('runtime-source-continuation' if args.continue_authorized else 'runtime-source')
    frozen.mkdir(exist_ok=True)
    for name,value in lock['source_files'].items():
        assert sha(ROOT/name)==value
        shutil.copy2(ROOT/name,frozen/name)
    # Stage records are written even when an unaccepted native route blocks work.
    save(PUBLIC/'d2-claim-review.json',{'phase':'D2','status':'blocked','native_jobs':0,'model_calls':0,
        'reason':'Authorized active provider has accepted Responses only. Claude native Anthropic route unavailable; plan prohibits provider exploration and silent framework/protocol replacement.',
        'source_audit':'d0-evidence.json','scores':None,'effect_claim':None})
    save(PUBLIC/'d3-downstream-results.json',{'phase':'D3','status':'blocked','native_jobs':0,'model_calls':0,
        'reason':'D2 not executed; its paired semantic qualification is required.','scores':None})
    processes=[];stop=threading.Event();rows=list(previous_rows)
    try:
        infra(processes,args.existing_broker)
        threading.Thread(target=pump,args=(stop,),daemon=True).start()
        for index,arm,repeat in lock['order']:
            prior=next((j for j in rows if (j['index'],j['arm'],j['repeat'])==(index,arm,repeat)),None)
            if prior and prior['status']=='completed':continue
            row=job(index,arm,repeat,runtime_hash,lock,resume=prior is not None)
            if prior:rows[rows.index(prior)]=row
            else:rows.append(row)
            save(PRIVATE/'d1-progress.json',{'jobs':rows})
            print(json.dumps({k:row.get(k) for k in ['job_id','status','official_correct','answer','queries','reason']}),flush=True)
            if row['status']!='completed':break
    except Exception as exc:
        save(PRIVATE/'infra-failure.json',{'type':type(exc).__name__,'message':str(exc)})
        print(json.dumps({'infrastructure_block':type(exc).__name__}),flush=True)
    finally:
        stop.set()
        for proc in reversed(processes):
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill()
    save(PUBLIC/'d1-paired-results.json',{'phase':'D1','status':'completed' if len(rows)==8 and
        all(r['status']=='completed' for r in rows) else 'blocked','lock_sha256':sha(PUBLIC/'d1-runtime-lock.json'),
        'continuation_lock_sha256':sha(PUBLIC/lock_name) if args.continue_authorized else None,
        'native_jobs':len(rows),'results':rows,'inference':'purpose-selected development diagnosis, not generalization or statistical significance'})


if __name__=='__main__':main()
