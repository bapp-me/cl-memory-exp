"""One isolated, serial Pi/CL-Bench stream; every task uses a fresh SDK session.

Canaries use a distinct run identity. Formal mode is fail-closed on acceptance.
Only this controller holds the database, hidden labels and audit directories.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from prepare import ROOT, read, save, sha
from protocol import Boundary, digest, jaccard, namespace, project_episode
from protocol_canary import secret
from database_adapter import DatabaseStream


def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()] if Path(path).exists() else []


def usage_for(out):
    attempts = []
    for request in (out / 'requests').glob('*.request.json'):
        file = request.with_name(request.name.replace('.request.json', '.response.txt'))
        usage, model = None, None
        for line in (file.read_text(encoding='utf-8').splitlines() if file.exists() else []):
            if line.startswith('data: ') and line[6:] != '[DONE]':
                try: value = json.loads(line[6:])
                except json.JSONDecodeError: continue
                model = value.get('model', model)
                usage = value.get('usage') or usage
        attempts.append({'attempt_id': file.name.split('.')[0], 'returned_model': model, 'usage': usage})
    return attempts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', choices=['pi_none', 'pi_notepad', 'pi_jaccard'], required=True)
    parser.add_argument('--mode', choices=['canary', 'formal'], required=True)
    parser.add_argument('--environment', choices=['database_exploration', 'codebase_adaptation'], default='database_exploration')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    total_instances = 40 if args.environment == 'database_exploration' else 19
    args.limit = args.limit or total_instances
    if not args.run_id.replace('-', '').replace('_', '').isalnum(): raise ValueError('Invalid run identifier')
    if not 1 <= args.limit <= total_instances: raise ValueError('Outside frozen schedule')
    if args.mode == 'formal':
        acceptance = read(ROOT / 'records/compatibility.json')
        if acceptance[args.method][args.environment]['status'] != 'READY':
            raise RuntimeError('Formal execution requires recorded acceptance')
        if not (ROOT / '.local/request-gate.json').exists(): raise RuntimeError('Shared request gate required')
    directory = ROOT / 'private-runs' / args.run_id
    if directory.exists() and not args.resume: raise RuntimeError('Run already exists; never overwrite it')
    directory.mkdir(parents=True, exist_ok=True)
    ns = namespace(args.method, 1, args.environment)
    boundary = Boundary(directory / 'boundary.json', ns)
    if boundary.state['pending']: raise RuntimeError('Pending task requires recovery, not business resubmission')
    if args.environment == 'database_exploration':
        stream = DatabaseStream(directory, restore=args.resume)
    else:
        from codebase_adapter import CodebaseStream
        stream = CodebaseStream(directory, restore=args.resume)
    state = read(directory / 'memory.json') if (directory / 'memory.json').exists() else {
        'namespace': ns, 'history': [], 'notepad': '', 'previous_feedback': ''}
    if state['namespace'] != ns: raise ValueError('Cross-environment memory')
    runtime_files = ['pi_session.mjs', 'protocol.py', 'run_pi_database.py']
    runtime_files += (['database_adapter.py'] if args.environment == 'database_exploration'
                      else ['codebase_adapter.py', 'docker_dispatch.py'])
    config_hash = digest({'files': {f: sha(ROOT / f) for f in runtime_files},
                          'plan': sha(ROOT / 'config/experiment.json'), 'namespace': ns})
    manifest = {'run_id': args.run_id, 'namespace': ns, 'mode': args.mode, 'config_hash': config_hash,
                'started_at': datetime.now(timezone.utc).isoformat(), 'cold_start': not args.resume,
                'task_manifest_sha256': sha(ROOT / 'records/task-manifest.json'),
                'isolation': 'only CLBENCH_ACTION registered; no filesystem/network agent tools or resource discovery',
                'accounting': 'actual unique HTTP attempts; no costs inferred from Pi catalog zero placeholders'}
    if (directory / 'manifest.json').exists():
        if read(directory / 'manifest.json')['config_hash'] != config_hash: raise RuntimeError('Config changed; cannot resume frozen stream')
    else: save(directory / 'manifest.json', manifest)
    key = secret()
    results = read(directory / 'results.json') if (directory / 'results.json').exists() else []
    try:
        while boundary.state['next_index'] < args.limit:
            current_hash = digest({'files': {f: sha(ROOT / f) for f in runtime_files},
                'plan': sha(ROOT / 'config/experiment.json'), 'namespace': ns})
            if current_hash != config_hash:
                raise RuntimeError('Runtime files changed during stream; stop at committed boundary')
            index = boundary.state['next_index']
            query = stream.public_query()
            if query['index'] != index: raise RuntimeError('Evaluator and boundary out of sync')
            out = directory / f'task-{index:03d}'; out.mkdir()
            project_key = query.get('project_key', 'database')
            workspace = directory / 'workspace' / project_key.replace('/', '_'); workspace.mkdir(parents=True, exist_ok=True)
            selected, ranked = (jaccard(state['history'], query['prompt'], namespace=ns, current_index=index)
                if args.method == 'pi_jaccard' else ([], []))
            save(out / 'memory-before.json', state)
            save(out / 'retrieval.json', {'selected_source_ids': [s['source_id'] for s in selected], 'ranked': ranked})
            token = uuid.uuid4().hex
            action_records = []
            completed = False
            controller_failed = False
            last_progress = time.monotonic()
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_): pass
                def do_POST(self):
                    nonlocal completed, last_progress, controller_failed
                    if self.headers.get('X-Run-Token') != token:
                        self.send_error(403); return
                    value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    if completed:
                        self.send_error(409, 'Submission already frozen'); return
                    try:
                        result = stream.action(value['action'])
                        completed = result['instance_complete']
                        record = {'action': value['action'], 'observation': result['observation'],
                                  'toolCallId': value['toolCallId'], 'at': datetime.now(timezone.utc).isoformat()}
                        action_records.append(record)
                        save(out / 'business-actions.json', action_records)
                        if completed:
                            save(out / 'submission.json', {'action': value['action'], 'feedback': result['observation'],
                                'artifact': stream.submission_artifact(index) if hasattr(stream, 'submission_artifact') else None})
                        body = json.dumps(result).encode()
                        self.send_response(200); self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
                        last_progress = time.monotonic()
                    except Exception as exc:
                        controller_failed = True
                        save(out / 'controller-error.json', {'type': type(exc).__name__, 'message': str(exc)})
                        self.send_error(500, 'Controller failed; stream is stopped')
            server = HTTPServer(('127.0.0.1', 0), Handler); server.timeout = 0.1
            is_database = args.environment == 'database_exploration'
            tool_description = ('Execute the official database QUERY or submit ANSWER. Each QUERY consumes the shared per-question budget.'
                if is_database else 'Execute one official benchmark Bash command. All commands share the issue action budget; use the official submission sentinel to finish.')
            framing = (query.get('brief', '') + '\nUse CLBENCH_ACTION for all business actions. '
                + ('Submit the exact answer via ANSWER. ' if is_database else 'Use its command field for each Bash command. ')
                + 'When the instance completes, end your turn. No other task information is available.')
            cfg = {'out': str(out), 'workspace': str(workspace), 'run_id': args.run_id,
                'method_id': args.method, 'instance_id': query['instance_id'], 'project_key': project_key,
                'environment': args.environment, 'config_hash': config_hash,
                'output_limit': 65536, 'output_ceiling': 65536, 'automatic_output_growth': False,
                'base_url': 'https://api.z.ai/api/paas/v4', 'tool_url': f'http://127.0.0.1:{server.server_port}/tool',
                'tool_token': token, 'tool_description': tool_description,
                'system_append': framing,
                'prompt': query['prompt'], 'notepad': state['notepad'] if args.method == 'pi_notepad' else '',
                'previous_feedback': state['previous_feedback'] if args.method == 'pi_notepad' else '', 'sources': selected}
            if (ROOT / '.local/request-gate.json').exists():
                cfg['request_gate'] = read(ROOT / '.local/request-gate.json')
            save(out / 'input.json', cfg)
            start = time.monotonic()
            registered = False
            with (out / 'stdout.txt').open('w', encoding='utf-8') as stdout, (out / 'stderr.txt').open('w', encoding='utf-8') as stderr:
                proc = subprocess.Popen(['node', str(ROOT / 'pi_session.mjs'), str(out / 'input.json')],
                    env={**os.environ, 'EXPERIMENT_API_KEY': key}, stdout=stdout, stderr=stderr)
                try:
                    while proc.poll() is None:
                        if not registered and (out / 'session-start.json').exists():
                            boundary.start(index, read(out / 'session-start.json')['session_id']); registered = True
                            last_progress = time.monotonic()
                        server.handle_request()
                        if controller_failed:
                            raise RuntimeError('Business controller failed; stop before another model request')
                        # The pinned official runner does NOT invoke the task's
                        # get_response_timeout_seconds hook. Do not activate it here.
                        if completed and time.monotonic() - last_progress > 600:
                            proc.terminate(); proc.wait(); raise TimeoutError('Post-submission completion barrier timed out')
                finally:
                    server.server_close()
                    if proc.poll() is None: proc.terminate(); proc.wait()
            if proc.returncode or not completed:
                raise RuntimeError('Pi did not finish cleanly; raw evidence and any business submission retained')
            end = read(out / 'session-end.json')
            if not registered: boundary.start(index, end['session_id'])
            assistant_text = [block['text'] for message in end['messages'] if message['role'] == 'assistant'
                for block in message.get('content', []) if block['type'] == 'text']
            episode = project_episode(namespace=ns, index=index, instance_id=query['instance_id'],
                prompt=query['prompt'], assistant_text=assistant_text, tools=action_records,
                feedback=action_records[-1]['observation'])
            watermark = digest(episode)
            boundary.freeze(read(out / 'submission.json'), watermark)
            if args.method == 'pi_jaccard': state['history'].append(episode)
            if args.method == 'pi_notepad':
                state['notepad'] = end['notepad']; state['previous_feedback'] = episode['feedback']
            save(out / 'legal-episode.json', episode)
            save(out / 'memory-after.json', state); save(directory / 'memory.json', state)
            receipt = boundary.complete(status='not_applicable', covered_watermark=watermark,
                jobs=[], memory_version=digest(state), durable=True, no_async_mechanism=True)
            save(out / 'barrier.json', receipt)
            grade = read(directory / 'evaluator-private' / f'result-{index:03d}.json')['record']
            correct = grade['correct'] if is_database else grade['success']
            actions = grade['num_queries'] if is_database else grade['steps']
            native_outcome = read(directory / 'evaluator-private' / f'result-{index:03d}.json')['outcome']
            reward = (native_outcome['reward'] if native_outcome else
                      1 - grade['regret'] / 15 if is_database else 0.0)
            result = {'index': index, 'instance_id': query['instance_id'], 'session_id': end['session_id'],
                'environment': args.environment, 'project_key': project_key,
                'correct': correct, 'actions': actions, 'reward': reward,
                'timed_out': grade.get('timed_out', False),
                'seconds': round(time.monotonic() - start, 3), 'attempts': usage_for(out),
                'memory_version': digest(state), 'source_watermark': watermark}
            results.append(result); save(directory / 'results.json', results)
            print(json.dumps({'run_id': args.run_id, 'completed': index + 1, 'correct': correct,
                              'actions': actions, 'seconds': result['seconds']}), flush=True)
        save(directory / 'stream-status.json', {'status': 'completed' if args.limit == total_instances else 'prefix_completed',
            'completed': len(results), 'mode': args.mode})
    except Exception as exc:
        save(directory / 'stream-status.json', {'status': 'paused_error', 'type': type(exc).__name__,
            'message': str(exc), 'completed': len(results), 'mode': args.mode})
        raise
    finally: stream.close()


if __name__ == '__main__': main()
