"""Audit already-recorded native probes; no model calls or admission mutation."""
import json
from prepare import ROOT, read, save, sha
from native_evidence import archive, validate, memory_snapshot, usage_for, validate_attempt_accounting


def main():
    for framework in ['claude', 'hermes', 'codex']:
        path = ROOT / f'records/{framework}-live-capability.json'
        record = read(path)
        directory = ROOT / record['raw']
        sessions, tasks = [], []
        for index in range(2):
            out = directory / f'task-{index:03d}'
            cfg = read(out / 'input.json')
            session = read(out / 'native-session.json')['session_id'] if framework == 'codex' else cfg['session_id']
            sessions.append(session)
            files = archive(out / 'native-state.tar.gz')
            lifecycle_error = None
            try: validate(files, out.name, framework, session)
            except RuntimeError as exc: lifecycle_error = str(exc)
            marker_files = [name for name in memory_snapshot(files, framework) if b'COBALT-739' in files[name]]
            actions = read(out / 'business-actions.json')
            answer = actions[-1]['action'].get('content')
            task = {'index': index, 'session_id': session, 'process_exit_code': read(out / 'process.json')['exit_code'],
                    'current_lifecycle_contract_passed': lifecycle_error is None, 'current_contract_error': lifecycle_error,
                    'marker_in_managed_memory': bool(marker_files),
                    'recall_submission_matches_marker': answer == 'COBALT-739' if index == 1 else None,
                    'accounting': validate_attempt_accounting(out, usage_for(out)),
                    'snapshot_sha256': sha(out / 'native-state.tar.gz')}
            if framework == 'hermes':
                barrier = json.loads(files[f'tasks/{out.name}/barrier-candidate.json'])
                task['recorded_jobs_settled'] = all(j['status'] == 'returned' and j.get('native_result') not in {None, 'error'} for j in barrier['jobs'])
                task['recorded_calls_settled'] = all(c['status'] == 'returned' and c['result'].get('completed') and not c['result'].get('failed') for c in barrier['calls'])
                task['final_source_covered'] = any(j['source_hash'] == barrier['final_messages_hash'] for j in barrier['jobs'])
                task['compression_threshold_fields_recorded'] = all(c.get('compression_threshold_tokens') is not None for c in barrier['calls'])
            tasks.append(task)
        recall = tasks[0]['marker_in_managed_memory'] and tasks[1]['recall_submission_matches_marker']
        record.update({'status': 'audited_recall_passed' if recall else 'audited_recall_failed',
                       'formal_ready': False, 'admission_is_separate': 'records/compatibility.json',
                       'model_calls_in_this_audit': 0, 'fresh_session_verified': len(set(sessions)) == 2,
                       'marker_recall_passed': bool(recall), 'tasks': tasks})
        if framework == 'hermes':
            record['limitation'] = ('Legacy capability probe proves marker write and recall with settled jobs, but omitted compression-threshold fields. '
                'It alone does not pass the current lifecycle contract. candidate-db-hermes-v2 separately validates that contract and real skill visibility.')
        if framework == 'codex':
            record['limitation'] = ('Actual extraction and consolidation settled, but the native extractor rejected the artificial marker as non-durable. '
                'Do not treat pipeline completion as successful marker recall or formal readiness.')
        save(path, record)
        print(json.dumps({'framework': framework, 'fresh_sessions': len(set(sessions)), 'marker_recall': bool(recall),
                          'current_lifecycle_passes': sum(t['current_lifecycle_contract_passed'] for t in tasks)}))


if __name__ == '__main__': main()
