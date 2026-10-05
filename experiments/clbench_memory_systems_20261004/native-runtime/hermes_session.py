"""Native Hermes AIAgent with transparent job/result instrumentation only."""
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid


def run(path, cfg, out, project):
    output_limit=int(cfg.get('output_limit',65536))
    home = Path('/state/home/.hermes'); home.mkdir(exist_ok=True)
    os.environ.update(HERMES_HOME=str(home), HOME='/state/home',
        OPENAI_API_KEY=cfg['gateway_token'], OPENAI_BASE_URL=cfg['gateway'])
    settings = {'model': {'default': 'glm-5.3-flash', 'provider': 'custom', 'base_url': cfg['gateway'], 'context_length': 262144},
        'compression': {'enabled': True, 'threshold': .9375},
        'memory': {'memory_enabled': True, 'user_profile_enabled': True, 'write_approval': False, 'nudge_interval': 10},
        'auxiliary': {'compression': {'provider': 'main', 'model': 'glm-5.3-flash', 'context_length': 262144},
            'background_review': {'enabled': True, 'provider': 'auto', 'model': 'glm-5.3-flash', 'defer': 'never', 'max_input_tokens': 2097152}},
        'terminal': {'backend': 'local', 'cwd': str(project)}, 'checkpoints': {'enabled': False}}
    (home / 'config.yaml').write_text(json.dumps(settings))
    os.chdir(project); sys.path.insert(0, '/opt/hermes')
    from run_agent import AIAgent
    from hermes_state import SessionDB
    from tools.registry import registry
    from business_mcp import SCHEMA, action
    from agent import background_review as review
    from agent import turn_response_check
    from native_budget import grow
    original_truncation=turn_response_check.recover_from_truncation
    def truncation(agent,response,*args,**kwargs):
        usage=getattr(response,'usage',None)
        output=getattr(usage,'completion_tokens',0) or 0
        old=int(agent.max_tokens or output_limit)
        if cfg.get('automatic_output_growth',False) and output>=old and old<cfg.get('output_ceiling',65536):
            receipt=grow(cfg,old)
            agent.max_tokens=receipt['output_limit']
            agent.context_compressor.max_tokens=receipt['output_limit']
            agent.context_compressor.threshold_tokens=receipt['compression_threshold']
            event('output_budget_increase',receipt)
        return original_truncation(agent,response,*args,**kwargs)
    turn_response_check.recover_from_truncation=truncation
    last_business_result = None
    def business_action(arguments):
        nonlocal last_business_result
        last_business_result = action(arguments, uuid.uuid4().hex)
        return last_business_result
    registry.register(name='CLBENCH_ACTION', toolset='clbench',
        schema={'name': 'CLBENCH_ACTION', 'description': cfg['tool_description'], 'parameters': SCHEMA},
        handler=lambda arguments, **kwargs: json.dumps(business_action(arguments)),
        check_fn=lambda: True)
    jobs = []; calls = []; failures = []; lock = threading.RLock(); local = threading.local()
    def save(name, value):
        with lock:
            p = out / (name + '.tmp'); p.write_text(json.dumps(value, default=str, ensure_ascii=False)); p.replace(out / name)
    def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
    def event(kind, data):
        with lock:
            with (out / 'events.jsonl').open('a') as f:
                f.write(json.dumps({'event': kind, 'data': data, 'thread': threading.current_thread().name}, default=str) + '\n')
    original_spawn = review.spawn_background_review_thread
    def spawn(agent, messages_snapshot, *args, **kwargs):
        target, prompt = original_spawn(agent, messages_snapshot, *args, **kwargs)
        job = {'id': uuid.uuid4().hex, 'parent_session_id': agent.session_id,
            'source_hash': digest(messages_snapshot), 'messages': messages_snapshot, 'status': 'created',
            'review_memory':kwargs.get('review_memory',False),'review_skills':kwargs.get('review_skills',False),
            'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
        jobs.append(job); save('jobs.json', jobs)
        def wrapped():
            local.job = job['id']; job['status'] = 'running'; save('jobs.json', jobs)
            try: target()
            except BaseException as exc:
                job['error'] = repr(exc); raise
            finally:
                job['status'] = 'returned'; save('jobs.json', jobs)
        return wrapped, prompt
    review.spawn_background_review_thread = spawn
    original_completion = review._log_review_completion
    def completion(usage, result):
        for job in jobs:
            if job['id'] == getattr(local, 'job', None): job.update(native_result=result, usage=usage)
        save('jobs.json', jobs); return original_completion(usage, result)
    review._log_review_completion = completion
    original_failure = AIAgent._emit_auxiliary_failure
    def failure(self, task, exc):
        failures.append({'task': task, 'error': repr(exc), 'session_id': self.session_id}); save('failures.json', failures)
        return original_failure(self, task, exc)
    AIAgent._emit_auxiliary_failure = failure
    original_run = AIAgent.run_conversation
    def conversation(self, *args, **kwargs):
        call = {'id': uuid.uuid4().hex, 'session_id': self.session_id,
            'parent_session_id': getattr(self, 'parent_session_id', None), 'job_id': getattr(local, 'job', None),
            'status': 'running', 'context_length': self.context_compressor.context_length,
            'compression_threshold_tokens': self.context_compressor.threshold_tokens}
        calls.append(call); save('conversations.json', calls)
        try:
            result = original_run(self, *args, **kwargs)
            call['result'] = result; call['status'] = 'returned'; return result
        except BaseException as exc:
            call['error'] = repr(exc); call['status'] = 'failed'; raise
        finally: save('conversations.json', calls)
    AIAgent.run_conversation = conversation
    original_init = AIAgent.__init__
    def initialize(self, *args, **kwargs):
        bound=inspect.signature(original_init).bind_partial(self,*args,**kwargs)
        bound.arguments['max_tokens']=output_limit
        original_init(*bound.args,**bound.kwargs)
        # Current Hermes computes its percentage after reserving output tokens.
        # Use its public token-threshold setter to map the agreed exact trigger.
        self.context_compressor.max_tokens=output_limit
        self.context_compressor.threshold_tokens = 262144 - output_limit
    AIAgent.__init__ = initialize
    db = SessionDB()
    agent = AIAgent(model='glm-5.3-flash', provider='custom', api_mode='chat_completions',
        base_url=cfg['gateway'], api_key=cfg['gateway_token'], max_tokens=output_limit,
        reasoning_config={'enabled': True, 'effort': 'high'},
        request_overrides={'reasoning_effort': 'high', 'extra_body': {'thinking': {'type': 'enabled'}}},
        session_id=cfg['session_id'], session_db=db, cwd=str(project), platform='cli',
        enabled_toolsets=['memory', 'skills', 'session_search', 'delegation', 'file', 'terminal', 'clbench'],
        event_callback=event, skip_context_files=False, skip_memory=False, skip_background_review=False,
        quiet_mode=True)
    try:
        save('effective-config.json', {'context_length': agent.context_compressor.context_length,
            'compression_threshold': agent.context_compressor.threshold_tokens,
            'tools': sorted(agent.valid_tool_names), 'session_id': agent.session_id})
        if agent.context_compressor.context_length != 262144: raise RuntimeError('Wrong native context window')
        from model_tools import get_tool_definitions
        available = get_tool_definitions(enabled_toolsets=agent.enabled_toolsets,
            disabled_toolsets=agent.disabled_toolsets, quiet_mode=True, skip_tool_search_assembly=True)
        if not any(t['function']['name'] == 'CLBENCH_ACTION' for t in available):
            raise RuntimeError('Business tool missing from native searchable registry')
        if cfg.get('maintenance_only'):
            result=json.loads((out/'main-result.json').read_text())
            prior=json.loads((out/'jobs.json').read_text())
            save('jobs-before-recovery.json',prior)
            if any(j.get('native_result') not in {None,'error'} for j in prior):
                raise RuntimeError('Recovery must not repeat already completed review jobs')
            if len(prior)!=1 or prior[0]['source_hash']!=digest(result['messages']):
                raise RuntimeError('Unfinished review does not cover the frozen final source')
            # The preserved request proves this historical job used the native
            # skill-only prompt. Reuse the same source and native writer scope.
            agent._spawn_background_review(messages_snapshot=prior[0]['messages'],review_memory=False,review_skills=True)
            last_business_result={'instance_complete':True}
        else:
            result = agent.run_conversation(cfg['prompt'], system_message=cfg['framing'])
        main_turns = 1
        while not (last_business_result or {}).get('instance_complete'):
            if result.get('failed') or not result.get('completed'):
                raise RuntimeError('Native main turn incomplete')
            # The official task asks for a final JSON action. Accept that exact
            # schema through the same counted controller, as its own runner does.
            # This is not a new solve or a fabricated submission command.
            from business_mcp import final_action
            observed = final_action(result['final_response'],uuid.uuid4().hex)
            last_business_result=observed
            event('final_json_action_dispatch', {'final_response':result['final_response'], 'result': observed})
            result = agent.run_conversation(json.dumps(observed), system_message=cfg['framing'],
                                            conversation_history=result['messages'])
            main_turns += 1
        save('main-result.json', result)
        if result.get('failed') or not result.get('completed'): raise RuntimeError('Native main turn incomplete')
        deadline = time.monotonic() + 600
        while any(j['status'] != 'returned' for j in jobs) or any(c['status'] == 'running' for c in calls):
            if time.monotonic() > deadline: raise TimeoutError('Native jobs did not drain')
            time.sleep(.1)
        final_hash = digest(result['messages'])
        if not any(j['source_hash']==final_hash for j in jobs):
            # One explicit boundary review after all legal terminal feedback;
            # intermediate native skill/memory jobs retain their normal triggers.
            agent._spawn_background_review(messages_snapshot=list(result['messages']), review_memory=True)
            if not any(j['source_hash']==final_hash for j in jobs):
                raise RuntimeError('Native boundary review was not admitted')
            while any(j['status']!='returned' for j in jobs) or any(c['status']=='running' for c in calls):
                if time.monotonic()>deadline: raise TimeoutError('Native boundary review did not drain')
                time.sleep(.1)
        if failures or any(j.get('error') or j.get('native_result') in {None, 'error'} for j in jobs):
            raise RuntimeError('Native review failed or lacks completion evidence')
        if any(c.get('error') or c.get('result', {}).get('failed') or not c.get('result', {}).get('completed') for c in calls):
            raise RuntimeError('Native child returned incomplete')
        save('barrier-candidate.json', {'jobs': jobs, 'calls': calls, 'final_messages_hash': final_hash, 'main_turns':main_turns,
            'status': 'native_jobs_returned_requires_external_audit'})
        return 0
    finally:
        agent.close(); db.close()
