"""Read native snapshots without extracting untrusted paths; audit unique attempts."""
import hashlib
import json
import tarfile
import time


def wait_for_settled_attempts(out, deadline):
    """Drain already-issued requests without starting any new model work."""
    while any(json.loads(p.read_text(encoding='utf8'))['phase']=='started' for p in (out/'requests').glob('*.attempt.json')):
        if time.monotonic()>=deadline:
            raise TimeoutError('Captured provider requests did not settle within the maintenance window')
        time.sleep(.1)


def archive(path):
    with tarfile.open(path) as tar:
        return {m.name.removeprefix('./'): tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}


def memory_snapshot(files, framework):
    needles = (['/.claude/projects/'] if framework == 'claude' else ['/.codex/memories/'] if framework=='codex'
        else ['/.hermes/memories/', '/.hermes/skills/', '/.hermes/pending/'])
    return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
        if any(n in '/' + name for n in needles) and '/.git/' not in name and (framework != 'claude' or '/memory/' in name)}


def validate(files, task, framework, session):
    prefix = f'tasks/{task}/'
    if framework=='codex':
        barrier=json.loads(files[prefix+'barrier-candidate.json'])
        if barrier['session_id']!=session:
            raise RuntimeError('Wrong Codex native session or barrier')
        if 'schedule' in barrier:
            import importlib.util
            from prepare import ROOT
            spec=importlib.util.spec_from_file_location('codex_completion_audit',ROOT/'native-runtime/codex_completion.py')
            completion=importlib.util.module_from_spec(spec);spec.loader.exec_module(completion)
            completion.validate_barrier(barrier)
            cfg=json.loads(files[prefix+'input.json'])
            if cfg.get('consolidation_schedule')!=barrier['schedule']:
                raise RuntimeError('Native consolidation schedule differs from controller input')
            if barrier['schedule']!=completion.schedule(cfg['environment'],int(task.removeprefix('task-'))):
                raise RuntimeError('Consolidation schedule does not match the instance position')
        elif barrier['status']!='native_pipeline_verified':
            raise RuntimeError('Wrong legacy Codex barrier')
        if len(barrier['stage1'])!=1 or barrier['stage1'][0]['status']!='done': raise RuntimeError('Extraction incomplete')
        if barrier['stage1'][0]['last_success_watermark']<barrier['source_updated_at']: raise RuntimeError('Stale extraction')
        required=barrier.get('schedule',{}).get('consolidation_required',True)
        if required and any(j['status']!='done' for j in barrier['phase2']): raise RuntimeError('Consolidation incomplete')
        if required and barrier['has_stage1_output'] and (not barrier['phase2'] or barrier['phase2'][0]['last_success_watermark']<barrier['source_updated_at']):
            raise RuntimeError('Stale consolidation')
        events=[json.loads(x) for x in files[prefix+'events.jsonl'].decode().splitlines()]
        if not any(e.get('type')=='turn.completed' for e in events): raise RuntimeError('Codex turn incomplete')
        text=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
        return {'kind':'native_codex_two_phase_pipeline' if required else 'native_codex_extraction_consolidation_deferred','jobs':barrier,'assistant_text':text}
    if framework == 'claude':
        events = [json.loads(x) for x in files[prefix + 'events.jsonl'].decode().splitlines()]
        results = [e for e in events if e['type'] == 'result']
        continuations=json.loads(files.get(prefix+'continuations.json',b'[]'))
        continued={c['result_index'] for c in continuations if c['kind'] in {'output_budget','official_final_json_action','transport_resume'}}
        if not results or any(i not in continued for i in range(len(results)-1)):
            raise RuntimeError('Native result event missing/ambiguous')
        result = results[-1]
        if result.get('is_error') or result.get('terminal_reason') != 'completed': raise RuntimeError('Claude incomplete')
        if result['session_id'] != session: raise RuntimeError('Wrong session')
        sub = result.get('subagent_stats', {})
        if sub.get('spawned', 0) != sub.get('completed', 0) or sub.get('failed', 0) or any(sub.get('killed', {}).values()):
            raise RuntimeError('Native child did not complete')
        if result.get('queued_turn_count', 0): raise RuntimeError('Native queued turn remains')
        for model, info in result['modelUsage'].items():
            if model != 'glm-5.3-flash' or info['contextWindow'] != 262144: raise RuntimeError('Wrong native model/window')
        text = [b['text'] for e in events if e['type'] == 'assistant' for b in e['message'].get('content', []) if b['type'] == 'text']
        return {'kind': 'native_auto_memory_foreground_turn', 'result': result, 'assistant_text': text,
                'observability': 'all requests captured; child content and IDs in native transcripts when emitted'}
    value = json.loads(files[prefix + 'barrier-candidate.json'])
    import importlib.util
    from prepare import ROOT
    spec=importlib.util.spec_from_file_location('hermes_completion_audit',ROOT/'native-runtime/hermes_completion.py')
    completion=importlib.util.module_from_spec(spec);spec.loader.exec_module(completion)
    supersession,_=completion.validate_calls(value['jobs'],value['calls'],value['final_messages_hash'])
    if supersession!=value.get('supersession_evidence',[]):raise RuntimeError('Supersession receipt differs from native evidence')
    if not value['jobs']: raise RuntimeError('Hermes review absent')
    if not any(j['source_hash'] == value['final_messages_hash'] for j in value['jobs']):
        raise RuntimeError('Hermes review misses final source watermark')
    for job in value['jobs']:
        if job['status'] != 'returned' or job.get('native_result') in {None, 'error'}: raise RuntimeError('Hermes review failed')
    for call in value['calls']:
        if call['context_length'] != 262144: raise RuntimeError('Child context differs')
        if call.get('compression_threshold_tokens') not in {245760,229376,196608,131072}:
            raise RuntimeError('Child compression trigger differs')
    result = json.loads(files[prefix + 'main-result.json'])
    text = [m['content'] for m in result['messages'] if m['role'] == 'assistant' and isinstance(m.get('content'), str)]
    return {'kind': 'native_review', 'jobs': value['jobs'], 'assistant_text': text,
            'native_source_watermark': value['final_messages_hash']}


def usage_for(out):
    attempts = []
    for request in (out / 'requests').glob('*.request.json'):
        response = request.with_name(request.name.replace('.request.json', '.response.bin'))
        meta = json.loads(request.with_name(request.name.replace('.request.json', '.attempt.json')).read_text())
        usage = {}; model = None; finish = None
        raw = response.read_text(encoding='utf-8') if response.exists() else ''
        values = []
        for line in raw.splitlines():
            if line.startswith('data: ') and line[6:] != '[DONE]':
                try: values.append(json.loads(line[6:]))
                except json.JSONDecodeError: pass
        if not values:
            try: values = [json.loads(raw)]
            except json.JSONDecodeError: pass
        for v in values:
            if v.get('type') == 'message_start': v = v['message']
            if 'response' in v: v = v['response']
            model = v.get('model') or model
            usage.update(v.get('usage') or {})
            delta=v.get('delta')
            finish = v.get('stop_reason') or (delta.get('stop_reason') if isinstance(delta,dict) else None) or finish
            if (v.get('incomplete_details') or {}).get('reason')=='max_output_tokens': finish='max_tokens'
            for c in v.get('choices', []): finish = c.get('finish_reason') or finish
        attempts.append({'attempt_id': meta['attempt_id'], 'protocol': meta['protocol'], 'http_status': meta.get('http_status'),
            'phase': meta['phase'], 'returned_model': model, 'usage': usage or None, 'finish_reason': finish})
    return attempts


def validate_attempt_accounting(out, attempts):
    """Require settled, preserved attempts; failed usage remains unknown, not zero.

    This does not validate task completion or authorize a retry. The caller must
    separately verify the native lifecycle and frozen benchmark submission.
    """
    if not attempts:
        raise RuntimeError('Native task has no captured attempts')
    expected = {p.name.removesuffix('.request.json') for p in (out / 'requests').glob('*.request.json')}
    ids = [a['attempt_id'] for a in attempts]
    if len(set(ids)) != len(ids) or set(ids) != expected:
        raise RuntimeError('Attempt inventory mismatch')
    known_successes = 0
    unknown_failures = []
    for attempt in attempts:
        stem = out / 'requests' / attempt['attempt_id']
        request = json.loads(stem.with_suffix('.request.json').read_text(encoding='utf-8'))
        meta = json.loads(stem.with_suffix('.attempt.json').read_text(encoding='utf-8'))
        if request.get('model') != 'glm-5.3-flash' or attempt['returned_model'] not in {None, 'glm-5.3-flash'}:
            raise RuntimeError('Native model identity mismatch')
        if attempt['phase'] not in {'finished', 'failed'}:
            raise RuntimeError('Native request is still in flight')
        response = stem.with_suffix('.response.bin')
        raw = response.read_text(encoding='utf-8') if response.exists() else ''
        values = []
        for line in raw.splitlines():
            line = line.removeprefix('data: ').strip()
            try: values.append(json.loads(line))
            except json.JSONDecodeError: pass
        try: values.append(json.loads(raw))
        except json.JSONDecodeError: pass
        provider_error = any(isinstance(v, dict) and (v.get('error') or v.get('type') in {'error', 'response.failed'}
            or isinstance(v.get('response'), dict) and v['response'].get('error')) for v in values)
        failed = bool(meta.get('error') or provider_error or (attempt['http_status'] is not None and attempt['http_status'] >= 400))
        if not failed:
            if not response.exists() or attempt['http_status'] != 200 or not attempt['usage'] or attempt['returned_model'] != 'glm-5.3-flash':
                raise RuntimeError('Successful response lacks verifiable usage or model evidence')
            known_successes += 1
        elif attempt['usage'] is None:
            unknown_failures.append(attempt['attempt_id'])
    if not known_successes:
        raise RuntimeError('No verified model completion')
    return {'status': 'captured_settled', 'attempts': len(attempts),
            'successful_responses_with_usage': known_successes,
            'failed_attempts_with_unknown_usage': unknown_failures,
            'cost_interpretation': 'Reported usage only; unknown failure usage is not zero.'}
