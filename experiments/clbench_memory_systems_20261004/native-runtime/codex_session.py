"""Pinned Codex CLI plus an input-free native startup maintenance session."""
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import threading
import time
from urllib.request import Request,urlopen


def run_solver(cfg,out,project,home,env):
    """Continue the same native thread only after proven output exhaustion."""
    from native_budget import grow
    base=['/native/codex','exec','--json','--skip-git-repo-check','--dangerously-bypass-approvals-and-sandbox',
        '-C',str(project),'--output-last-message',str(out/'final.txt')]
    session=None; output_limit=16384; prompt=cfg['prompt']; continuations=[]
    with (out/'events.jsonl').open('w') as events,(out/'stderr.txt').open('w') as stderr:
        while True:
            command=base+([prompt] if session is None else ['resume',session,prompt])
            proc=subprocess.Popen(command,env=env,cwd=project,stdout=subprocess.PIPE,stderr=stderr,text=True)
            for line in proc.stdout:
                events.write(line); events.flush()
                value=json.loads(line)
                if value.get('type')=='thread.started':
                    received=value['thread_id']
                    if session is not None:
                        if received!=session: raise RuntimeError('Output continuation created a different Codex session')
                        continue
                    session=received; (out/'session-start.json').write_text(json.dumps({'session_id':session}))
                    request=Request(cfg['gateway']+'/tool',data=json.dumps({'control':'session_start','session_id':session}).encode(),
                        headers={'Authorization':'Bearer '+cfg['gateway_token'],'Content-Type':'application/json'})
                    with urlopen(request,timeout=30) as response: response.read()
            code=proc.wait()
            observed=json.loads((out/'last-business-result.json').read_text()) if (out/'last-business-result.json').exists() else {}
            if not code and session and observed.get('instance_complete'): return session
            if not session: raise RuntimeError('Native Codex did not produce a session')
            # /budget rejects normal stop, network errors, input exhaustion,
            # reused evidence and growth beyond the provider output maximum.
            decision=grow(cfg,output_limit)
            output_limit=decision['output_limit']
            config_path=home/'config.toml'; config=config_path.read_text()
            lines=config.splitlines()
            positions=[i for i,line in enumerate(lines) if line.startswith('model_auto_compact_token_limit = ')]
            if len(positions)!=1: raise RuntimeError('Ambiguous Codex compression reserve')
            lines[positions[0]]=f"model_auto_compact_token_limit = {decision['compression_threshold']}"
            config_path.write_text('\n'.join(lines)+'\n')
            continuations.append({**decision,'kind':'output_budget','session_id':session,
                'previous_exit_code':code,'business_already_complete':bool(observed.get('instance_complete'))})
            (out/'solver-continuations.json').write_text(json.dumps(continuations))
            prompt=('The previous response exhausted its output budget; the output allowance is now larger. '
                'Continue this same task from the saved state. Do not repeat already completed actions. '
                + ('The benchmark submission is already fixed. Finish only the current turn; do not perform further benchmark actions.'
                   if observed.get('instance_complete') else 'Finish the current benchmark instance.'))


def run(path,cfg,out,project):
    from codex_catalog import CATALOG
    home=Path('/state/home/.codex'); home.mkdir(exist_ok=True)
    (home/'models.json').write_text(json.dumps(CATALOG))
    config=f'''model = "glm-5.3-flash"
model_provider = "glm_experiment"
model_reasoning_effort = "high"
model_context_window = 262144
model_auto_compact_token_limit = 245760
model_catalog_json = "{home}/models.json"
approval_policy = "never"
sandbox_mode = "danger-full-access"
web_search = "disabled"
developer_instructions = {json.dumps(cfg['framing'])}
[features]
memories = true
[model_providers.glm_experiment]
name = "GLM experiment"
base_url = "{cfg['gateway']}"
env_key = "EXPERIMENT_API_KEY"
wire_api = "responses"
request_max_retries = 0
stream_max_retries = 0
stream_idle_timeout_ms = 300000
[memories]
generate_memories = true
use_memories = true
disable_on_external_context = false
extract_model = "glm-5.3-flash"
consolidation_model = "glm-5.3-flash"
[mcp_servers.clbench]
command = "python"
args = ["/runtime/business_mcp.py", {json.dumps(str(path))}]
'''
    (home/'config.toml').write_text(config)
    env={**os.environ,'HOME':'/state/home','CODEX_HOME':str(home),'PATH':'/native:'+os.environ['PATH'],
        'EXPERIMENT_API_KEY':cfg['gateway_token'],'CLBENCH_MEMORY_BOUNDARY_MODE':'1'}
    env.pop('CLBENCH_MEMORY_SOURCE_THREAD',None)
    session=run_solver(cfg,out,project,home,env)
    # No future question and no user turn are sent to this maintenance process.
    receipt=home/'clbench-memory-pipeline.json'
    if receipt.exists(): receipt.unlink()
    maint_env={**env,'CLBENCH_MEMORY_SOURCE_THREAD':session}
    messages=queue.Queue()
    with (out/'maintenance-stderr.txt').open('w') as stderr,(out/'maintenance-events.jsonl').open('w') as event_log:
        maint=subprocess.Popen(['/native/codex','app-server'],env=maint_env,cwd=project,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True)
        def pump():
            for line in maint.stdout:
                event_log.write(line); event_log.flush()
                try: messages.put(json.loads(line))
                except json.JSONDecodeError: pass
        thread=threading.Thread(target=pump); thread.start()
        def send(value): maint.stdin.write(json.dumps(value)+'\n'); maint.stdin.flush()
        def response(ident):
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                value=messages.get(timeout=max(.1,deadline-time.monotonic()))
                if value.get('id')==ident:
                    if 'error' in value: raise RuntimeError(str(value['error']))
                    return value['result']
            raise TimeoutError('Native app-server RPC timed out')
        try:
            send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'clbench-memory-boundary','version':'1'},
                'capabilities':{'experimentalApi':True}}}); response(1)
            send({'method':'initialized'})
            send({'id':2,'method':'thread/start','params':{'cwd':str(project)}}); started=response(2)
            (out/'maintenance-start.json').write_text(json.dumps(started))
            # In this pinned release the startup hook is invoked on the first
            # turn/start, not on thread/start itself. This synchronization turn
            # carries no future problem and does not ask a second writer to
            # summarize anything. Its ordinary model call is fully accounted.
            send({'id':3,'method':'turn/start','params':{'threadId':started['thread']['id'],
                'input':[{'type':'text','text':'This is a maintenance synchronization turn. Reply ACK only. Do not use tools, read files, edit memory, or perform benchmark actions. The native background memory pipeline is handled independently.'}]}})
            response(3)
            deadline=time.monotonic()+600
            while not receipt.exists():
                if maint.poll() is not None: raise RuntimeError('Maintenance process ended before pipeline return')
                if time.monotonic()>deadline: raise TimeoutError('Native memory pipeline did not return')
                time.sleep(.2)
            (out/'pipeline-receipt.json').write_bytes(receipt.read_bytes())
            # phase2::run spawns its monitor and can return while consolidation
            # is still running. A returned pipeline receipt is not a barrier.
            while True:
                live_jobs=[]
                for dbpath in home.glob('memories_*.sqlite'):
                    with sqlite3.connect(dbpath) as db:
                        db.row_factory=sqlite3.Row
                        live_jobs.extend(dict(r) for r in db.execute('SELECT * FROM jobs'))
                if any(j['status']=='error' for j in live_jobs):
                    (out/'failed-memory-jobs.json').write_text(json.dumps(live_jobs))
                    raise RuntimeError('Native memory job failed')
                if not any(j['status']=='running' for j in live_jobs): break
                if time.monotonic()>deadline: raise TimeoutError('Native consolidation did not settle')
                time.sleep(.2)
            databases={}
            for dbpath in home.glob('*.sqlite'):
                with sqlite3.connect(dbpath) as db:
                    db.row_factory=sqlite3.Row
                    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    data={}
                    if 'jobs' in tables: data['jobs']=[dict(r) for r in db.execute('SELECT * FROM jobs')]
                    if 'stage1_outputs' in tables: data['stage1_outputs']=[dict(r) for r in db.execute('SELECT * FROM stage1_outputs')]
                    if 'threads' in tables:
                        data['source_thread']=[dict(r) for r in db.execute('SELECT * FROM threads WHERE id=?',(session,))]
                    if data: databases[dbpath.name]=data
                    with sqlite3.connect(out/dbpath.name) as backup: db.backup(backup)
            (out/'memory-jobs.json').write_text(json.dumps(databases))
            stage1=[j for value in databases.values() for j in value.get('jobs',[]) if j['kind']=='memory_stage1' and j['job_key']==session]
            if len(stage1)!=1 or stage1[0]['status']!='done': raise RuntimeError('Native extraction lacks success evidence')
            source=[s for value in databases.values() for s in value.get('source_thread',[])]
            source_time=int(source[0]['updated_at_ms'])//1000
            if (stage1[0].get('last_success_watermark') or 0)<source_time: raise RuntimeError('Extraction watermark is stale')
            outputs=[r for value in databases.values() for r in value.get('stage1_outputs',[]) if r['thread_id']==session]
            phase2=[j for value in databases.values() for j in value.get('jobs',[]) if j['kind']=='memory_consolidate_global']
            if any(j['status']!='done' for j in phase2): raise RuntimeError('Started consolidation did not complete')
            if outputs and (len(phase2)!=1 or phase2[0]['status']!='done' or (phase2[0].get('last_success_watermark') or 0)<source_time):
                raise RuntimeError('Native consolidation lacks committed watermark')
            (out/'barrier-candidate.json').write_text(json.dumps({'session_id':session,'source_updated_at':source_time,
                'stage1':stage1,'phase2':phase2,'has_stage1_output':bool(outputs),'status':'native_pipeline_verified'}))
        finally:
            maint.stdin.close()
            try: maint.wait(timeout=30)
            except subprocess.TimeoutExpired: maint.terminate(); maint.wait()
            thread.join(timeout=5)
    return 0
