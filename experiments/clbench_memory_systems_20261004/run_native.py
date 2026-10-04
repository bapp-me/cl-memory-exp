"""One serial native-method/environment stream with durable task boundaries."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
import uuid
from prepare import ROOT, read, save, sha
from protocol import Boundary, digest, namespace, project_episode
from native_client import broker, put, snapshot, freeze_runtime
from native_evidence import archive, memory_snapshot, validate, usage_for, validate_attempt_accounting


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--framework', choices=['claude', 'hermes','codex'], required=True)
    p.add_argument('--environment', choices=['database_exploration','codebase_adaptation'], required=True)
    p.add_argument('--mode', choices=['canary','formal'], required=True)
    p.add_argument('--run-id', required=True); p.add_argument('--limit', type=int)
    args = p.parse_args(); method = args.framework + '_memory_ready'
    if args.framework=='codex':
        import native_client
        native_client.BROKER_KIND='codex'
    total = 40 if args.environment == 'database_exploration' else 19; limit = args.limit or total
    if not 1 <= limit <= total or not args.run_id.replace('-', '').isalnum(): raise ValueError('Invalid run scope')
    if args.mode == 'formal' and read(ROOT/'records/compatibility.json')[method][args.environment]['status'] != 'READY':
        raise RuntimeError('Acceptance required')
    directory = ROOT / 'private-runs' / args.run_id; directory.mkdir()
    ns = namespace(method, 1, args.environment); boundary = Boundary(directory/'boundary.json',ns)
    runtime = ['run_native.py','native_evidence.py','native_gateway.py','budget_control.py','native_client.py',
        'native-runtime/native_entry.py','native-runtime/business_mcp.py','native-runtime/native_budget.py']
    if args.framework == 'hermes': runtime += ['native-runtime/hermes_session.py']
    if args.framework == 'codex': runtime += ['native-runtime/codex_session.py','native-runtime/codex_catalog.py']
    runtime += ['database_adapter.py'] if total == 40 else ['codebase_adapter.py','docker_dispatch.py']
    config_hash = digest({f:sha(ROOT/f) for f in runtime})
    snapshot_dir=directory/'runtime-source'
    for file in runtime:
        destination=snapshot_dir/file; destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes((ROOT/file).read_bytes())
    native_hash=freeze_runtime()
    save(directory/'manifest.json',{'run_id':args.run_id,'namespace':ns,'mode':args.mode,'config_hash':config_hash,
        'cold_start':True,'started_at':datetime.now(timezone.utc).isoformat(),'runtime_files':runtime,
        'native_runtime_hash':native_hash,'runtime_policy':'controller modules remain loaded; each agent process mounts the immutable captured native runtime'})
    if total == 40:
        from database_adapter import DatabaseStream
        stream = DatabaseStream(directory)
    else:
        from codebase_adapter import CodebaseStream
        stream = CodebaseStream(directory)
    created = broker({'op':'create','runtime_hash':native_hash}); container = created['container_id']; save(directory/'container.json',created)
    results=[]; memory_before={}
    try:
        for index in range(limit):
            if config_hash != digest({f:sha(snapshot_dir/f) for f in runtime}): raise RuntimeError('Captured runtime changed at boundary')
            query=stream.public_query(); out=directory/f'task-{index:03d}'; out.mkdir(); task=out.name
            actions=[]; completed=False; failed=False; submitted_at=None
            session=str(uuid.uuid4()); token=uuid.uuid4().hex
            if args.framework!='codex': boundary.start(index,session)
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
                        result=stream.action(value['action']); completed=result['instance_complete']
                        actions.append({'action':value['action'],'observation':result['observation'],'toolCallId':value['toolCallId']})
                        save(out/'business-actions.json',actions)
                        if completed:
                            submitted_at=time.monotonic()
                            save(out/'submission.json',{'action':value['action'],'feedback':result['observation'],
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
                'tool_url':f'http://127.0.0.1:{server.server_port}/tool','tool_token':token,'output_limit':16384}
            save(ROOT/'.local/native-routes'/f'{route_id}.json',route)
            cfg={'framework':args.framework,'session_id':session,'project_key':route['project_key'],
                'gateway':f'http://172.30.0.1:{43193 if args.framework=="codex" else 43191}/r/{route_id}','gateway_token':route_token,'environment':args.environment,
                'tool_description':('Execute an official database QUERY or submit ANSWER; every QUERY consumes the official budget.' if total==40
                    else 'Execute one official benchmark Bash command. All commands consume the official issue action budget; use its submission sentinel to finish.'),
                'framing':query.get('brief','')+'\nUse CLBENCH_ACTION (discover it if needed) for all benchmark business actions. Local files and shell are only for native memory and bookkeeping. The benchmark workspace is accessible only through CLBENCH_ACTION. After instance_complete, end your turn.',
                'prompt':query['prompt']}
            save(out/'input.json',cfg); save(out/'memory-before.json',memory_before)
            put(container,f'/state/tasks/{task}/input.json',cfg)
            started=time.monotonic(); job=broker({'op':'launch','container_id':container,'task':task})['job_id']; poll_at=0
            while True:
                server.handle_request()
                if failed: raise RuntimeError('Controller failure; native stream stopped')
                if submitted_at and time.monotonic()-submitted_at>600: raise TimeoutError('Completion barrier exceeded 600 seconds')
                if time.monotonic()>=poll_at:
                    state=broker({'op':'poll','container_id':container,'job_id':job}); poll_at=time.monotonic()+2
                    if not state['running']: break
            server.server_close(); save(out/'process.json',state)
            snapshot(container,out/'native-state.tar.gz'); files=archive(out/'native-state.tar.gz')
            if state['exit_code'] or not completed: raise RuntimeError('Native process or business instance incomplete')
            evidence=validate(files,task,args.framework,session); save(out/'native-completion.json',evidence)
            # Audit before advancing the durable boundary. A preserved transport
            # failure can coexist with successful native recovery; its unknown
            # usage must not erase the completed business result or become zero.
            attempts=usage_for(out)
            save(out/'transport-accounting.json',validate_attempt_accounting(out,attempts))
            episode=project_episode(namespace=ns,index=index,instance_id=query['instance_id'],prompt=query['prompt'],
                assistant_text=evidence['assistant_text'],tools=actions,feedback=actions[-1]['observation'])
            watermark=digest(episode); boundary.freeze(read(out/'submission.json'),watermark)
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
            # A crash after boundary commit can be recovered from this exact row,
            # without reconstructing timings or running the business task again.
            save(out/'prepared-result.json',result)
            receipt=boundary.complete(status=status,covered_watermark=watermark,
                jobs=[{'status':status,'covered_watermark':watermark,'native_evidence':'native-completion.json'}],
                memory_version=digest(memory_after),durable=True)
            save(out/'barrier.json',receipt); memory_before=memory_after
            results.append(result); save(directory/'results.json',results)
            print(json.dumps({'run_id':args.run_id,'completed':index+1,'correct':correct,'actions':count}),flush=True)
        save(directory/'stream-status.json',{'status':'completed' if limit==total else 'prefix_completed','completed':len(results),'mode':args.mode})
    except Exception as exc:
        if 'route' in locals():
            route['disabled']=True; save(ROOT/'.local/native-routes'/f'{route_id}.json',route)
        try: broker({'op':'stop','container_id':container})
        except Exception: pass
        save(directory/'stream-status.json',{'status':'paused_error','completed':len(results),'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        stream.close()
        try: broker({'op':'remove','container_id':container})
        except Exception: pass


if __name__=='__main__': main()
