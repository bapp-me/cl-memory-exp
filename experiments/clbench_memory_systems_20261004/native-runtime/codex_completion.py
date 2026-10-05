"""Evidence checks for native extraction and user-requested batched consolidation."""
from contextlib import closing
import json
import sqlite3


def schedule(environment, index):
    interval, total = {'database_exploration': (10, 40), 'codebase_adaptation': (5, 19)}[environment]
    if not 0 <= index < total:
        raise ValueError('Invalid task index')
    position = index + 1
    return {'policy': 'codex_batched_v1', 'environment': environment, 'position': position,
            'interval': interval, 'total': total,
            'consolidation_required': position % interval == 0 or position == total}


def read_databases(home, session, out=None):
    databases = {}
    for path in home.glob('*.sqlite'):
        with closing(sqlite3.connect(path)) as db:
            db.row_factory = sqlite3.Row
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            value = {}
            if 'jobs' in tables:
                value['jobs'] = [dict(r) for r in db.execute('SELECT * FROM jobs')]
            if 'stage1_outputs' in tables:
                value['stage1_outputs'] = [dict(r) for r in db.execute('SELECT * FROM stage1_outputs')]
            if 'threads' in tables:
                value['source_thread'] = [dict(r) for r in db.execute('SELECT * FROM threads WHERE id=?', (session,))]
            if value:
                databases[path.name] = value
                if out is not None:
                    with closing(sqlite3.connect(out / path.name)) as backup:
                        db.backup(backup)
    return databases


def phase2_jobs(databases):
    return [j for v in databases.values() for j in v.get('jobs', []) if j['kind'] == 'memory_consolidate_global']


def build_barrier(databases, session, plan, before, receipt):
    stage1 = [j for v in databases.values() for j in v.get('jobs', [])
              if j['kind'] == 'memory_stage1' and j['job_key'] == session]
    sources = [s for v in databases.values() for s in v.get('source_thread', [])]
    if len(sources) != 1:
        raise RuntimeError('Ambiguous native source thread')
    source_time = int(sources[0]['updated_at_ms']) // 1000
    outputs = [r for v in databases.values() for r in v.get('stage1_outputs', [])]
    value = {'session_id': session, 'source_updated_at': source_time, 'stage1': stage1,
             'phase2': phase2_jobs(databases), 'phase2_before': before,
             'has_stage1_output': any(r['thread_id'] == session for r in outputs),
             'extracted_sources': [{k: r.get(k) for k in ['thread_id', 'source_updated_at',
                 'selected_for_phase2', 'selected_for_phase2_source_updated_at']} for r in outputs],
             'schedule': plan, 'pipeline_receipt': receipt,
             'status': 'native_pipeline_verified' if plan['consolidation_required'] else
                       'native_extraction_verified_consolidation_deferred'}
    validate_barrier(value)
    return value


def validate_barrier(value):
    plan = value['schedule']
    if plan != schedule(plan['environment'], plan['position'] - 1):
        raise RuntimeError('Consolidation schedule differs from user-authorized policy')
    stage1 = value['stage1']
    if len(stage1) != 1 or stage1[0]['status'] != 'done' or stage1[0]['job_key'] != value['session_id']:
        raise RuntimeError('Native extraction lacks completed source job')
    if (stage1[0].get('last_success_watermark') or 0) < value['source_updated_at']:
        raise RuntimeError('Native extraction watermark is stale')
    phase2 = value['phase2']
    if len(phase2) > 1 or any(j['status'] == 'running' for j in phase2):
        raise RuntimeError('Unsettled or ambiguous consolidation job')
    if not plan['consolidation_required']:
        if value['status'] != 'native_extraction_verified_consolidation_deferred':
            raise RuntimeError('Deferred consolidation must be explicit')
        if not value['pipeline_receipt'].get('consolidation_deferred'):
            raise RuntimeError('Native scheduler did not defer consolidation')
        # Extraction may enqueue global work, but must not start another writer.
        fields = ['worker_id', 'ownership_token', 'started_at', 'finished_at', 'last_success_watermark']
        for job in phase2:
            prior = next((j for j in value['phase2_before'] if j['job_key'] == job['job_key']), {})
            if any((job.get(k) or 0) != (prior.get(k) or 0) for k in fields):
                raise RuntimeError('Consolidation executed outside the batch boundary')
        return
    if value['status'] != 'native_pipeline_verified' or value['pipeline_receipt'].get('consolidation_deferred'):
        raise RuntimeError('Batch boundary requires native consolidation')
    if any(j['status'] != 'done' for j in phase2):
        raise RuntimeError('Consolidation incomplete')
    outputs = value['extracted_sources']
    if outputs:
        required = max(r['source_updated_at'] for r in outputs)
        if len(phase2) != 1 or (phase2[0].get('last_success_watermark') or 0) < required:
            raise RuntimeError('Consolidation misses extracted source watermark')
        if any(not r['selected_for_phase2'] or (r['selected_for_phase2_source_updated_at'] or 0) < r['source_updated_at'] for r in outputs):
            raise RuntimeError('Consolidation did not commit every extracted source in this study')


def save_barrier(home, out, session, plan, before, receipt):
    databases = read_databases(home, session, out)
    value = build_barrier(databases, session, plan, before, receipt)
    (out / 'memory-jobs.json').write_text(json.dumps(databases))
    (out / 'barrier-candidate.json').write_text(json.dumps(value))
    return value
