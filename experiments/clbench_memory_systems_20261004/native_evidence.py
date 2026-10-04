"""Read native snapshots without extracting untrusted paths; audit unique attempts."""
import hashlib
import json
import tarfile


def archive(path):
    with tarfile.open(path) as tar:
        return {m.name.removeprefix('./'): tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}


def memory_snapshot(files, framework):
    needles = ['/.claude/projects/'] if framework == 'claude' else ['/.hermes/memories/', '/.hermes/skills/', '/.hermes/pending/']
    return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
        if any(n in '/' + name for n in needles) and (framework != 'claude' or '/memory/' in name)}


def validate(files, task, framework, session):
    prefix = f'tasks/{task}/'
    if framework == 'claude':
        events = [json.loads(x) for x in files[prefix + 'events.jsonl'].decode().splitlines()]
        results = [e for e in events if e['type'] == 'result']
        continuations=json.loads(files.get(prefix+'continuations.json',b'[]'))
        continued={c['result_index'] for c in continuations if c['kind'] in {'output_budget','official_final_json_action'}}
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
    if not value['jobs']: raise RuntimeError('Hermes review absent')
    if not any(j['source_hash'] == value['final_messages_hash'] for j in value['jobs']):
        raise RuntimeError('Hermes review misses final source watermark')
    for job in value['jobs']:
        if job['status'] != 'returned' or job.get('native_result') in {None, 'error'}: raise RuntimeError('Hermes review failed')
    for call in value['calls']:
        if call['status'] != 'returned' or call['result'].get('failed') or not call['result'].get('completed'):
            raise RuntimeError('Hermes child incomplete')
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
