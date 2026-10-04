"""Complete a paused invalid-output case through the official zero-credit hook.

Never reruns a model or executes text as a command. Existing business submissions
and transport failures are rejected; only a clean, nonterminal model stop qualifies.
"""
import argparse
from datetime import datetime,timezone
import uuid
from prepare import ROOT,read,save
from protocol import Boundary,digest,project_episode
from codebase_adapter import CodebaseStream
from src.tasks.codebase_adaptation.task import BashCommandResponse
from pydantic import ValidationError
from run_pi_database import usage_for

p=argparse.ArgumentParser(); p.add_argument('--run-id',required=True); args=p.parse_args()
d=ROOT/'private-runs'/args.run_id; manifest=read(d/'manifest.json')
method=manifest['namespace'].split('/')[0]
assert method in {'pi_none','pi_notepad','pi_jaccard'} and manifest['namespace'].endswith('/codebase_adaptation')
boundary=Boundary(d/'boundary.json',manifest['namespace']); pending=boundary.state['pending']
assert pending and pending['status']=='running'
index=pending['index']; out=d/f'task-{index:03d}'
assert not (out/'submission.json').exists() and not (out/'controller-error.json').exists()
end=read(out/'session-end.json'); assert not end['terminal']
assistant=[m for m in end['messages'] if m['role']=='assistant']
assert assistant[-1]['stopReason']=='stop', 'Do not score length/transport failures as format errors'
final_text=''.join(b['text'] for b in assistant[-1].get('content',[]) if b['type']=='text')
try: BashCommandResponse.model_validate_json(final_text)
except ValidationError: pass
else: raise RuntimeError('A valid official final JSON action needs dispatch recovery, not zero credit')
attempts=usage_for(out); assert attempts and all(a['usage'] and a['returned_model']=='glm-5.3-flash' for a in attempts)
metadata=[__import__('json').loads(x) for x in (out/'attempts.jsonl').read_text().splitlines()]
assert all(any(m['attempt_id']==a['attempt_id'] and m['phase']=='finished' and m['status']==200 for m in metadata) for a in attempts)
checkpoint=read(d/'evaluator-private/state.json'); assert checkpoint['current_issue_idx']==index
temp=ROOT/'.local/recovery'/uuid.uuid4().hex
stream=CodebaseStream(temp)
try:
    stream.task.current_issue_idx=index; stream.task.current_steps=checkpoint['current_steps']
    stream.task.issue_history=checkpoint['issue_history']
    stream.task.total_interactions=sum(r['steps'] for r in stream.task.issue_history)+stream.task.current_steps
    stream.query=stream.task.build_current_query()
    result=stream.task.handle_system_error(stream.query,ValueError('Agent ended without a valid structured business action'))
    record=stream.task.issue_history[-1]
    save(d/'evaluator-private'/f'result-{index:03d}.json',{'record':record,'outcome':result.instance_outcome.__dict__})
    save(d/'evaluator-private/state.json',{'current_issue_idx':stream.task.current_issue_idx,'current_steps':stream.task.current_steps,
        'issue_history':stream.task.issue_history})
    save(d/'evaluator-private'/f'trace-{index:03d}-format-error.json',stream.task.interaction_trace)
    text=[b['text'] for m in assistant for b in m.get('content',[]) if b['type']=='text']
    cfg=read(out/'input.json'); actions=read(out/'business-actions.json')
    episode=project_episode(namespace=manifest['namespace'],index=index,instance_id=cfg['instance_id'],prompt=cfg['prompt'],
        assistant_text=text,tools=actions,feedback=result.observation.content)
    watermark=digest(episode)
    submission={'kind':'official_system_error','feedback':result.observation.content,'artifact':None,
        'final_response_sha256':digest(text[-1] if text else '')}
    save(out/'submission.json',submission); boundary.freeze(submission,watermark)
    memory=read(d/'memory.json')
    if method=='pi_notepad': memory.update(notepad=end['notepad'],previous_feedback=result.observation.content)
    if method=='pi_jaccard': memory['history'].append(episode)
    save(out/'legal-episode.json',episode); save(out/'memory-after.json',memory); save(d/'memory.json',memory)
    receipt=boundary.complete(status='not_applicable',covered_watermark=watermark,jobs=[],memory_version=digest(memory),durable=True,no_async_mechanism=True)
    save(out/'barrier.json',receipt)
    started=datetime.fromisoformat(metadata[0]['timestamp'].replace('Z','+00:00'))
    finished=datetime.fromisoformat(metadata[-1]['timestamp'].replace('Z','+00:00'))
    rows=read(d/'results.json'); assert len(rows)==index
    rows.append({'index':index,'instance_id':cfg['instance_id'],'session_id':end['session_id'],
        'environment':'codebase_adaptation','project_key':cfg['project_key'],'correct':False,'actions':record['steps'],
        'reward':result.instance_outcome.reward,'timed_out':False,'seconds':None,
        'known_provider_start_span_seconds':round((finished-started).total_seconds(),3),
        'seconds_basis':'exact controller elapsed unavailable for recovered error; do not mix provider span with task wall time',
        'attempts':attempts,'memory_version':digest(memory),'source_watermark':watermark,'eval_status':'system_error'})
    save(d/'results.json',rows)
    save(out/'recovery.json',{'mode':'official_invalid_output_zero_credit','model_calls':0,'business_commands_replayed':0,
        'hook':'CodebaseAdaptationTask.handle_system_error','original_step_count':checkpoint['current_steps'],
        'recorded_step_count':record['steps'],'raw_evidence_preserved':True,
        'feedback_delivery':'legal episode and permitted next-instance memory state; no semantic retry to the ended agent',
        'recovered_at':datetime.now(timezone.utc).isoformat()})
    save(d/'stream-status.json',{'status':'ready_to_resume','completed':len(rows),'mode':manifest['mode'],
        'recovery':'official invalid structured response, zero credit, no model retry'})
    print({'run_id':args.run_id,'official_format_error_index':index,'correct':False,'steps':record['steps'],'model_calls':0})
finally: stream.close()
