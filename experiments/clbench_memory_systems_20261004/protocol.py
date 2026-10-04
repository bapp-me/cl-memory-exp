"""Method state and crash-safe, fail-closed task boundaries. No model code."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from prepare import save, read


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def namespace(method, repetition, environment):
    if method not in {'pi_none', 'pi_notepad', 'pi_jaccard', 'codex_memory_ready',
                      'claude_memory_ready', 'hermes_memory_ready'}:
        raise ValueError('Unknown method')
    if repetition != 1 or environment not in {'database_exploration', 'codebase_adaptation'}:
        raise ValueError('Outside the authorized R1 environments')
    return f'{method}/r{repetition}/{environment}'


def database_feedback(record, question_num):
    """Construct public feedback from an allowlist, never redact arbitrary gold text."""
    status = ('TIMED OUT' if record['timed_out'] else 'Query budget exceeded'
              if record['budget_exceeded'] else 'CORRECT' if record['correct'] else 'INCORRECT')
    return (f'Question {question_num}: {status}.\n'
            f'Your answer: {record["submitted_answer"]}\n'
            f'Exploratory queries used: {record["num_queries"]}')


def apply_notepad(current, action):
    clean = deepcopy(action)
    value = clean.pop('notepad_update', None)
    if value is not None and not isinstance(value, str):
        raise ValueError('notepad_update must be string or null')
    return current if value is None else value, clean


def project_episode(*, namespace, index, instance_id, prompt, assistant_text, tools, feedback):
    # Callers provide only public fields. No raw session/system/reasoning/evaluator blobs.
    return {'namespace': namespace, 'index': index, 'instance_id': instance_id,
            'prompt': prompt, 'assistant_text': list(assistant_text),
            'tools': [{'action': deepcopy(t['action']), 'observation': t['observation']} for t in tools],
            'feedback': feedback}


def jaccard(history, prompt, *, namespace, current_index):
    query = set(re.findall(r'\w+', prompt.lower()))
    candidates = []
    for episode in history:
        if episode['namespace'] != namespace or episode['index'] >= current_index:
            raise ValueError('Cross-stream or future episode in history')
        text = json.dumps({k: episode[k] for k in ('prompt', 'assistant_text', 'tools', 'feedback')}, ensure_ascii=False)
        words = set(re.findall(r'\w+', text.lower()))
        score = len(query & words) / (len(query | words) or 1)
        candidates.append({'episode': episode, 'score': score, 'source_id': digest(episode)})
    ranked = sorted(candidates, key=lambda x: (x['score'], x['episode']['index']), reverse=True)
    selected = sorted(ranked[:3], key=lambda x: x['episode']['index'])
    return selected, [{'source_id': c['source_id'], 'score': c['score'], 'index': c['episode']['index']} for c in ranked]


class Boundary:
    """Submission is immutable after freeze; failed maintenance never advances state.

    A runtime adapter must provide actual completed job evidence. This class does
    not infer completion from files, elapsed time or a parent process exit.
    """
    def __init__(self, path, namespace):
        self.path = Path(path)
        self.namespace = namespace
        self.state = read(self.path) if self.path.exists() else {
            'namespace': namespace, 'next_index': 0, 'memory_version': None,
            'session_ids': [], 'pending': None}
        if self.state['namespace'] != namespace:
            raise ValueError('State namespace mismatch')

    def start(self, index, session_id):
        if self.state['pending'] is not None or index != self.state['next_index']:
            raise RuntimeError('Prior boundary incomplete or out-of-order task')
        if session_id in self.state['session_ids']:
            raise RuntimeError('Cross-instance session reuse')
        self.state['session_ids'].append(session_id)
        self.state['pending'] = {'index': index, 'session_id': session_id, 'status': 'running'}
        save(self.path, self.state)

    def freeze(self, submission, source_watermark):
        pending = self.state['pending']
        if not pending or pending['status'] != 'running':
            raise RuntimeError('Cannot resubmit a frozen business result')
        pending.update(status='submitted', submission=deepcopy(submission),
                       submission_hash=digest(submission), source_watermark=source_watermark)
        save(self.path, self.state)

    def complete(self, *, status, covered_watermark, jobs, memory_version,
                 durable, no_async_mechanism=False):
        pending = self.state['pending']
        if not pending or pending['status'] != 'submitted':
            raise RuntimeError('No frozen submission')
        if covered_watermark != pending['source_watermark'] or not durable:
            raise RuntimeError('Incomplete watermark or storage commit')
        if status not in {'completed_changed', 'completed_noop', 'completed_staged', 'not_applicable'}:
            raise RuntimeError('Maintenance did not complete')
        if status == 'not_applicable':
            if not no_async_mechanism:
                raise RuntimeError('Absence of async work must be established')
        elif not jobs:
            raise RuntimeError('Missing native maintenance result')
        if any(j.get('status') not in {'completed_changed', 'completed_noop', 'completed_staged'}
               or j.get('covered_watermark') != covered_watermark for j in jobs):
            raise RuntimeError('Unfinished or stale child job')
        receipt = {**pending, 'status': status, 'jobs': deepcopy(jobs),
                   'memory_version': memory_version, 'durable': True}
        self.state.update(next_index=pending['index'] + 1, memory_version=memory_version,
                          pending=None, last_barrier=receipt)
        save(self.path, self.state)
        return receipt
