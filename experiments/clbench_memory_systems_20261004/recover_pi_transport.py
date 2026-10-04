"""Recover the observed HTTP-500 case from an unchanged read-only code prefix.

Fail closed for other prefixes: a destroyed, modified worktree cannot be inferred
from a transcript. No solver retry occurs before the exact outgoing body is tested.
"""
import argparse
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
from codebase_adapter import CodebaseStream
from prepare import ROOT,read,save,sha
from protocol import Boundary,digest,project_episode
from protocol_canary import secret
from run_pi_database import usage_for


def main():
    p=argparse.ArgumentParser(); p.add_argument('--run-id',required=True); p.add_argument('--execute',action='store_true')
    args=p.parse_args(); d=ROOT/'private-runs'/args.run_id; manifest=read(d/'manifest.json')
    assert manifest['namespace']=='pi_none/r1/codebase_adaptation'
    boundary=Boundary(d/'boundary.json',manifest['namespace']); index=boundary.state['next_index']
    assert boundary.state['pending']['status']=='running'
    out=d/f'task-{index:03d}'; end=read(out/'session-end.json'); actions=read(out/'business-actions.json')
    last=[m for m in end['messages'] if m['role']=='assistant'][-1]
    assert last['stopReason']=='error' and last['errorMessage'].startswith('500:')
    readonly='ls && head -100 tenacity/__init__.py 2>/dev/null || head -100 tenacity.py'
    assert len(actions)==1 and actions[0]['action']=={'command':readonly}
    checkpoint=read(d/'evaluator-private/state.json'); assert checkpoint['current_issue_idx']==index and checkpoint['current_steps']==1
    events=[json.loads(x) for x in (out/'attempts.jsonl').read_text().splitlines()]
    failed=events[-1]; assert failed['phase']=='finished' and failed['status']==500
    sessions=list((out/'sessions').glob('*.jsonl')); assert len(sessions)==1
    probe=ROOT/'.local/fixtures'/('transport-resume-'+uuid.uuid4().hex); probe.mkdir(parents=True)
    copied=probe/'session.jsonl'; shutil.copy2(sessions[0],copied)
    cfg=read(out/'input.json'); fixture={**cfg,'out':str(probe),'run_id':'transport-recovery-fixture',
        'resume_session_file':str(copied),'failed_request_file':str(out/'requests'/f"{failed['attempt_id']}.request.json"),
        'retry_verification_file':str(probe/'wire-check.json'),'resume_dry_run':True}
    fixture.pop('request_gate',None); save(probe/'input.json',fixture)
    checked=subprocess.run(['node',str(ROOT/'resume_pi_session.mjs'),str(probe/'input.json')],
        env={**os.environ,'EXPERIMENT_API_KEY':'offline-fixture-only'},capture_output=True,text=True,encoding='utf-8')
    save(probe/'process.json',{'code':checked.returncode,'stdout':checked.stdout,'stderr':checked.stderr})
    assert read(probe/'wire-check.json')=={'wire_identical':True,'model_calls':0}
    print('Offline native-session continuation reproduces the failed request exactly.',flush=True)
    if not args.execute: return
    recovery=out/'transport-recovery'; recovery.mkdir()
    for name in ['session-start.json','session-end.json','stdout.txt','stderr.txt','input.json']:
        if (out/name).exists(): shutil.copy2(out/name,recovery/('before-'+name))
    stream=CodebaseStream(recovery/'environment')
    try:
        stream.task._cleanup_container()
        stream.task.current_issue_idx=index; stream.task.issue_history=checkpoint['issue_history']
        stream.task._update_rollout_context_for_issue(index,announce=True)
        stream.task._start_container(); stream.query=stream.task.build_current_query()
        # A controller-only read verifies identical observable base/test_patch
        # state. It is never fed to the model and does not reset its step budget.
        observed=stream.task._execute(readonly)
        expected=f"<returncode>{observed['returncode']}</returncode>\n<output>\n{observed['output']}</output>"
        assert expected==actions[0]['observation']
        stream.task.current_steps=1
        stream.task.total_interactions=sum(r['steps'] for r in checkpoint['issue_history'])+1
        token=uuid.uuid4().hex; completed=False; failed_controller=False; submitted_at=None
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_): pass
            def do_POST(self):
                nonlocal completed,failed_controller,submitted_at
                if self.headers.get('X-Run-Token')!=token: self.send_error(403); return
                if completed: self.send_error(409); return
                value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                try:
                    result=stream.action(value['action']); completed=result['instance_complete']
                    actions.append({'action':value['action'],'observation':result['observation'],'toolCallId':value['toolCallId']})
                    save(out/'business-actions.json',actions)
                    if completed:
                        submitted_at=time.monotonic()
                        save(out/'submission.json',{'action':value['action'],'feedback':result['observation'],
                            'artifact':stream.submission_artifact(index)})
                    data=json.dumps(result).encode(); self.send_response(200)
                    self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
                except Exception as exc:
                    failed_controller=True; save(out/'controller-error.json',{'message':str(exc)}); self.send_error(500)
        server=HTTPServer(('127.0.0.1',0),Handler); server.timeout=.1
        resumed={**cfg,'tool_url':f'http://127.0.0.1:{server.server_port}/tool','tool_token':token,
            'resume_session_file':str(sessions[0]),'failed_request_file':fixture['failed_request_file'],
            'retry_verification_file':str(recovery/'wire-check.json'),'resume_dry_run':False}
        save(recovery/'input.json',resumed)
        started=time.monotonic()
        with (out/'stdout.txt').open('w',encoding='utf-8') as stdout,(out/'stderr.txt').open('w',encoding='utf-8') as stderr:
            process=subprocess.Popen(['node',str(ROOT/'resume_pi_session.mjs'),str(recovery/'input.json')],
                env={**os.environ,'EXPERIMENT_API_KEY':secret()},stdout=stdout,stderr=stderr)
            while process.poll() is None:
                server.handle_request()
                if failed_controller: process.terminate(); process.wait(); raise RuntimeError('Recovery controller failed')
                if submitted_at and time.monotonic()-submitted_at>600:
                    process.terminate(); process.wait(); raise TimeoutError('Recovery completion barrier timed out')
        server.server_close()
        assert process.returncode==0 and completed
        after=read(out/'session-end.json'); assert after['session_id']==end['session_id']
        text=[b['text'] for m in after['messages'] if m['role']=='assistant' for b in m.get('content',[]) if b['type']=='text']
        episode=project_episode(namespace=manifest['namespace'],index=index,instance_id=cfg['instance_id'],prompt=cfg['prompt'],
            assistant_text=text,tools=actions,feedback=actions[-1]['observation'])
        watermark=digest(episode); boundary.freeze(read(out/'submission.json'),watermark)
        memory=read(d/'memory.json'); save(out/'legal-episode.json',episode); save(out/'memory-after.json',memory)
        receipt=boundary.complete(status='not_applicable',covered_watermark=watermark,jobs=[],memory_version=digest(memory),durable=True,no_async_mechanism=True)
        save(out/'barrier.json',receipt)
        for source in [stream.private/f'result-{index:03d}.json',stream.private/'state.json',
                       stream.private/f'submission-{index:03d}.diff',stream.private/f'trace-{index:03d}.json']:
            if source.exists(): shutil.copy2(source,d/'evaluator-private'/source.name)
        grade=read(stream.private/f'result-{index:03d}.json'); record=grade['record']
        attempts=usage_for(out); rows=read(d/'results.json'); assert len(rows)==index
        rows.append({'index':index,'instance_id':cfg['instance_id'],'session_id':after['session_id'],
            'environment':'codebase_adaptation','project_key':cfg['project_key'],'correct':record['success'],
            'actions':record['steps'],'reward':grade['outcome']['reward'],'timed_out':False,'seconds':None,
            'recovery_active_seconds':round(time.monotonic()-started,3),'seconds_basis':'interrupted task; exact original controller elapsed unavailable',
            'attempts':attempts,'source_watermark':watermark,'memory_version':digest(memory)})
        save(d/'results.json',rows)
        receipt={'status':'recovered','retry_of_attempt_id':failed['attempt_id'],'same_native_session':True,
            'same_provider_request':True,'business_prefix':'one verified read-only command; base plus official test_patch restored',
            'controller_verification_reads':1,'extra_model_observations':0,'step_budget_preserved':True,
            'offline_probe':probe.relative_to(ROOT).as_posix(),'recovery_script_sha256':sha(ROOT/'resume_pi_session.mjs')}
        save(recovery/'receipt.json',receipt)
        save(d/'stream-status.json',{'status':'ready_to_resume','completed':len(rows),'mode':'formal','recovery':'identical-request HTTP 500 retry'})
        print({'index':index,'recovered':True,'correct':record['success'],'steps':record['steps']},flush=True)
    finally:
        if (stream.private/'state.json').exists():
            shutil.copy2(stream.private/'state.json',d/'evaluator-private/state.json')
        stream.close()


if __name__=='__main__': main()
