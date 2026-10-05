"""One serial native-method/environment stream with durable task boundaries."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import shutil
import time
import uuid
from prepare import ROOT, read, save, sha
from protocol import Boundary, digest, namespace, project_episode
from native_client import broker, put, snapshot, restore, freeze_runtime
from native_evidence import archive, memory_snapshot, validate, usage_for, validate_attempt_accounting


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--framework', choices=['claude', 'hermes','codex'], required=True)
    p.add_argument('--environment', choices=['database_exploration','codebase_adaptation'], required=True)
    p.add_argument('--mode', choices=['canary','formal'], required=True)
    p.add_argument('--run-id', required=True); p.add_argument('--limit', type=int)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--recover-format',action='store_true')
    p.add_argument('--retry-native-maintenance',action='store_true')
    p.add_argument('--retry-transport-maintenance',action='store_true')
    args = p.parse_args(); method = args.framework + '_memory_ready'
    if args.framework=='codex':
        import native_client
        native_client.BROKER_KIND='codex'
    total = 40 if args.environment == 'database_exploration' else 19; limit = args.limit or total
    if not 1 <= limit <= total or not args.run_id.replace('-', '').isalnum(): raise ValueError('Invalid run scope')
    if args.mode == 'formal' and read(ROOT/'records/compatibility.json')[method][args.environment]['status'] != 'READY':
        raise RuntimeError('Acceptance required')
    directory = ROOT / 'private-runs' / args.run_id
    if not args.resume: directory.mkdir()
    elif not directory.is_dir(): raise RuntimeError('No saved stream to resume')
    ns = namespace(method, 1, args.environment); boundary = Boundary(directory/'boundary.json',ns)
    first_index=boundary.state['next_index']; pending=boundary.state['pending']
    if pending and not (directory/f'task-{first_index:03d}'/'submission.json').exists():
        raise RuntimeError('Interrupted business work needs a separate same-session recovery; no replay allowed')
    if args.recover_format and (not pending or args.framework!='codex'):
        raise RuntimeError('Format recovery is only for a submitted Codex task')
    if args.retry_native_maintenance:
        authorization=read(ROOT/'records/execution-authorization.json').get('native_maintenance_invalid_json_retry',{})
        if not pending or args.framework!='codex' or not authorization.get('approved'):
            raise RuntimeError('Native failed-maintenance retry requires explicit authorization and a frozen submission')
    if args.retry_transport_maintenance:
        if not pending or args.framework!='codex':raise RuntimeError('Transport maintenance recovery requires a frozen Codex submission')
        metas=[read(p) for p in (directory/f'task-{first_index:03d}'/'requests').glob('*.attempt.json')]
        latest=max(metas,key=lambda m:m['timestamp'])
        if latest.get('error') not in {'TimeoutError','ConnectionResetError','RemoteDisconnected','URLError','ConnectionAbortedError'} and (latest.get('http_status') or 0)<500:
            raise RuntimeError('Latest request does not establish a transport failure')
    runtime = ['run_native.py','native_evidence.py','native_gateway.py','budget_control.py','native_client.py',
        'native-runtime/native_entry.py','native-runtime/business_mcp.py','native-runtime/native_budget.py']
    if args.framework == 'hermes': runtime += ['native-runtime/hermes_session.py','native-runtime/hermes_completion.py']
    if args.framework == 'codex': runtime += ['native-runtime/codex_session.py','native-runtime/codex_catalog.py','native-runtime/responses_format_proxy.py']
    runtime += ['database_adapter.py'] if total == 40 else ['codebase_adapter.py','docker_dispatch.py']
    config_hash = digest({f:sha(ROOT/f) for f in runtime})
    snapshot_dir=directory/('runtime-source-resume-'+uuid.uuid4().hex[:8] if args.resume else 'runtime-source')
    for file in runtime:
        destination=snapshot_dir/file; destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes((ROOT/file).read_bytes())
    native_hash=freeze_runtime()
    manifest=read(directory/'manifest.json') if args.resume else {'run_id':args.run_id,'namespace':ns,'mode':args.mode,'config_hash':config_hash,
        'cold_start':True,'started_at':datetime.now(timezone.utc).isoformat(),'runtime_files':runtime,
        'native_runtime_hash':native_hash,'runtime_policy':'controller modules remain loaded; each agent process mounts the immutable captured native runtime'}
    if manifest['namespace']!=ns: raise RuntimeError('Resume namespace mismatch')
    if args.resume:
        manifest.setdefault('continuations',[]).append({'from_index':first_index,'maintenance_only_first':bool(pending),
            'config_hash':config_hash,'native_runtime_hash':native_hash,'runtime_source':snapshot_dir.name,
            'at':datetime.now(timezone.utc).isoformat(),'output_limit':65536})
        if args.mode=='formal' and manifest['mode']!='formal':
            manifest['mode']='formal'; manifest['canary_prefix_reused']=True
            manifest['accepted_prefix_instances']=first_index
    save(directory/'manifest.json',manifest)
    if total == 40:
        from database_adapter import DatabaseStream
        stream = DatabaseStream(directory,restore=args.resume)
    else:
        from codebase_adapter import CodebaseStream
        stream = CodebaseStream(directory,restore=args.resume)
    created = broker({'op':'create','runtime_hash':native_hash}); container = created['container_id']; save(directory/'container.json',created)
    results=read(directory/'results.json') if args.resume else []
    memory_before=read(directory/f'task-{first_index-1:03d}'/'memory-after.json') if first_index else {}
    if args.resume and first_index+bool(pending):
        previous=directory/f'task-{first_index if pending else first_index-1:03d}'
        candidates=[previous/name for name in ['recovery-timeout-state.tar.gz','recovered-native-state.tar.gz','timeout-state.tar.gz','native-state.tar.gz'] if (previous/name).exists()]
        archive_path=max(candidates,key=lambda p:p.stat().st_mtime_ns) if candidates else None
        if archive_path is None: raise RuntimeError('Missing preserved native state')
        if pending:
            prior_files=[p for p in previous.iterdir() if p.is_file() and (p.name.startswith('recovery-') or p.name=='recovered-native-state.tar.gz')]
            if prior_files:
                history=previous/'recovery-history'/uuid.uuid4().hex;history.mkdir(parents=True)
                for file in prior_files:shutil.copy2(file,history/file.name)
                if archive_path in prior_files:archive_path=history/archive_path.name
        try: restore(container,archive_path)
        except Exception:
            stream.close();broker({'op':'remove','container_id':container})
            raise
    save(directory/'stream-status.json',{'status':'running','completed':len(results),'mode':manifest['mode'],
        'resumed':args.resume,'started_at':datetime.now(timezone.utc).isoformat()})
    try:
        for index in range(first_index,limit):
            if config_hash != digest({f:sha(snapshot_dir/f) for f in runtime}): raise RuntimeError('Captured runtime changed at boundary')
            recovering=bool(pending and index==first_index)
            out=directory/f'task-{index:03d}'; out.mkdir(exist_ok=recovering); task=out.name
            if recovering:
                original_cfg=read(out/'input.json')
                original_prompt=original_cfg.get('benchmark_prompt',original_cfg['prompt'])
                if total==19 and 'benchmark_prompt' not in original_cfg:
                    from src.systems.utils.structured_output import schema_to_prompt_instruction
                    from src.tasks.codebase_adaptation.task import BashCommandResponse
                    original_prompt=original_prompt.removesuffix(schema_to_prompt_instruction(BashCommandResponse))
                query={'prompt':original_prompt,'project_key':original_cfg['project_key'],
                    'instance_id':read(ROOT/'records/task-manifest.json')[args.environment][index]['instance_id']}
            else: query=stream.public_query()
            actions=read(out/'business-actions.json') if recovering else []
            completed=recovering; failed=False; submitted_at=None
            session=pending['session_id'] if recovering else str(uuid.uuid4()); token=uuid.uuid4().hex
            if args.framework!='codex' and not recovering: boundary.start(index,session)
            route_id=uuid.uuid4().hex; route_token=uuid.uuid4().hex
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*_): pass
                def do_POST(self):
                    nonlocal completed,failed,submitted_at,session
                    if self.headers.get('X-Run-Token')!=token: self.send_error(403); return
                    value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    if value.get('control')=='session_start' and args.framework=='codex':
                        session=str(uuid.UUID(value['session_id'])); boundary.start(index,session)
                        route['session_id']=session; save(ROOT/'.local/native-routes'/f'{route_id}.json',route)
                        save(out/'session-start.json',{'session_id':session})
                        data=b'{"registered":true}'; self.send_response(200)
                        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
                    if completed: self.send_error(409); return
                    try:
                        if value.get('control')=='final_response':
                            from src.systems.codex.system import _parse_action_text
                            schema=stream.query.response_schema
                            try: parsed=_parse_action_text(value['text'],schema)
                            except Exception as error:
                                if total==40: raise
                                result=stream.invalid_final(error)
                                action_value={'invalid_final_response':value['text']}
                            else:
                                action_value=parsed.model_dump(); result=stream.action(action_value)
                        else:
                            action_value=value['action']; result=stream.action(action_value)
                        completed=result['instance_complete']
                        actions.append({'action':action_value,'observation':result['observation'],'toolCallId':value['toolCallId']})
                        save(out/'business-actions.json',actions)
                        if completed:
                            submitted_at=time.monotonic()
                            save(out/'submission.json',{'action':action_value,'feedback':result['observation'],
                                'artifact':stream.submission_artifact(index) if hasattr(stream,'submission_artifact') else None})
                        data=json.dumps(result).encode(); self.send_response(200)
                        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
                    except Exception as exc:
                        failed=True; save(out/'controller-error.json',{'type':type(exc).__name__,'message':str(exc)})
                        self.send_error(500)
            server=HTTPServer(('127.0.0.1',0),Handler); server.timeout=.2
            route={'token':route_token,'run_id':args.run_id,'method_id':method,'instance_id':query['instance_id'],
                'project_key':query.get('project_key','database'),'session_id':session,'phase':'native_task_and_maintenance',
                'config_hash':config_hash,'audit_relative_path':out.relative_to(ROOT).as_posix(),
                'tool_url':f'http://127.0.0.1:{server.server_port}/tool','tool_token':token,'output_limit':65536,
                'output_ceiling':65536,'automatic_output_growth':False,'uniform_output_limit':True}
            save(ROOT/'.local/native-routes'/f'{route_id}.json',route)
            cfg={'framework':args.framework,'session_id':session,'project_key':route['project_key'],
                'output_limit':65536,'output_ceiling':65536,'automatic_output_growth':False,
                'gateway':f'http://172.30.0.1:{43193 if args.framework=="codex" else 43191}/r/{route_id}','gateway_token':route_token,'environment':args.environment,
                'tool_description':('Execute an official database QUERY or submit ANSWER; every QUERY consumes the official budget.' if total==40
                    else 'Execute one official benchmark Bash command. All commands consume the official issue action budget; use its submission sentinel to finish.'),
                'framing':query.get('brief','')+'\nUse CLBENCH_ACTION (discover it if needed) for all benchmark business actions. Local files and shell are only for native memory and bookkeeping. The benchmark workspace is accessible only through CLBENCH_ACTION. After instance_complete, end your turn.',
                'prompt':query['prompt'],'benchmark_prompt':query['prompt']}
            if total==19 and not recovering:
                from src.systems.utils.structured_output import schema_to_prompt_instruction
                cfg['prompt']+=schema_to_prompt_instruction(stream.query.response_schema)
            if recovering:
                cfg.update(maintenance_only=True,framing=original_cfg['framing'],recover_format_error=args.recover_format,
                    retry_native_maintenance=args.retry_native_maintenance,retry_transport_maintenance=args.retry_transport_maintenance)
                save(out/'recovery-input.json',cfg)
                save(out/'recovery-provenance.json',{'original_submission_sha256':sha(out/'submission.json'),
                    'source_archive_sha256':sha(archive_path),'source_archive':archive_path.relative_to(directory).as_posix(),
                    'original_business_actions_sha256':sha(out/'business-actions.json'),'business_replayed':False,
                    'recovery_started_at':datetime.now(timezone.utc).isoformat(),'config_hash':config_hash})
            else:
                save(out/'input.json',cfg); save(out/'memory-before.json',memory_before)
            put(container,f'/state/tasks/{task}/input.json',cfg)
            started=time.monotonic()
            if recovering: submitted_at=started
            job=broker({'op':'launch','container_id':container,'task':task})['job_id']; poll_at=0
            save(out/('recovery-job.json' if recovering else 'native-job.json'),{'job_id':job,'container_id':container})
            while True:
                server.handle_request()
                if failed: raise RuntimeError('Controller failure; native stream stopped')
                if submitted_at and time.monotonic()-submitted_at>600: raise TimeoutError('Completion barrier exceeded 600 seconds')
                if time.monotonic()>=poll_at:
                    state=broker({'op':'poll','container_id':container,'job_id':job}); poll_at=time.monotonic()+2
                    if not state['running']: break
            server.server_close(); save(out/('recovery-process.json' if recovering else 'process.json'),state)
            native_snapshot=out/('recovered-native-state.tar.gz' if recovering else 'native-state.tar.gz')
            snapshot(container,native_snapshot); files=archive(native_snapshot)
            if state['exit_code'] or not completed: raise RuntimeError('Native process or business instance incomplete')
            evidence=validate(files,task,args.framework,session); save(out/'native-completion.json',evidence)
            # Audit before advancing the durable boundary. A preserved transport
            # failure can coexist with successful native recovery; its unknown
            # usage must not erase the completed business result or become zero.
            attempts=usage_for(out)
            save(out/'transport-accounting.json',validate_attempt_accounting(out,attempts))
            episode=project_episode(namespace=ns,index=index,instance_id=query['instance_id'],prompt=query['prompt'],
                assistant_text=evidence['assistant_text'],tools=actions,feedback=actions[-1]['observation'])
            watermark=digest(episode)
            if boundary.state['pending']['status']=='running': boundary.freeze(read(out/'submission.json'),watermark)
            elif boundary.state['pending']['source_watermark']!=watermark: raise RuntimeError('Frozen source changed during recovery')
            save(out/'legal-episode.json',episode)
            memory_after=memory_snapshot(files,args.framework); save(out/'memory-after.json',memory_after)
            status='completed_changed' if memory_before!=memory_after else 'completed_noop'
            grade=read(directory/'evaluator-private'/f'result-{index:03d}.json'); record=grade['record']
            correct=record['correct'] if total==40 else record['success']; count=record['num_queries'] if total==40 else record['steps']
            result={'index':index,'instance_id':query['instance_id'],'session_id':session,'environment':args.environment,
                'project_key':route['project_key'],'correct':correct,'actions':count,
                'reward':grade['outcome']['reward'] if grade['outcome'] else 1-record['regret']/15 if total==40 else 0,
                'timed_out':record.get('timed_out',False),'seconds':round(time.monotonic()-started,3),
                'maintenance_seconds':round(time.monotonic()-submitted_at,3),'attempts':attempts,'source_watermark':watermark}
            if recovering:
                proof=read(out/'recovery-provenance.json')
                if proof['original_submission_sha256']!=sha(out/'submission.json') or proof['original_business_actions_sha256']!=sha(out/'business-actions.json'):
                    raise RuntimeError('Recovery changed frozen business evidence')
                result.update(seconds=None,seconds_basis='Interrupted task total wall time unknown; recovery time separately reported',
                    maintenance_seconds=None,maintenance_recovery_seconds=round(time.monotonic()-started,3),
                    recovered_maintenance=True)
            # A crash after boundary commit can be recovered from this exact row,
            # without reconstructing timings or running the business task again.
            save(out/'prepared-result.json',result)
            receipt=boundary.complete(status=status,covered_watermark=watermark,
                jobs=[{'status':status,'covered_watermark':watermark,'native_evidence':'native-completion.json'}],
                memory_version=digest(memory_after),durable=True)
            save(out/'barrier.json',receipt); memory_before=memory_after
            results.append(result); save(directory/'results.json',results)
            route['disabled']=True;save(ROOT/'.local/native-routes'/f'{route_id}.json',route)
            print(json.dumps({'run_id':args.run_id,'completed':index+1,'correct':correct,'actions':count}),flush=True)
        save(directory/'stream-status.json',{'status':'completed' if limit==total else 'prefix_completed','completed':len(results),'mode':args.mode})
    except Exception as exc:
        if 'route' in locals():
            route['disabled']=True; save(ROOT/'.local/native-routes'/f'{route_id}.json',route)
        try:
            broker({'op':'quiesce','container_id':container})
            if 'out' in locals(): snapshot(container,out/('recovery-timeout-state.tar.gz' if recovering else 'timeout-state.tar.gz'))
            broker({'op':'stop','container_id':container})
        except Exception: pass
        save(directory/'stream-status.json',{'status':'paused_error','completed':len(results),'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        stream.close()
        try: broker({'op':'remove','container_id':container})
        except Exception: pass


if __name__=='__main__': main()
