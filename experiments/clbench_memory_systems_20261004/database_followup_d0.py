"""Bounded, read-only Database follow-up audit. Never calls a model."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tarfile
import time

from prepare import ROOT, UPSTREAM, read, save, sha
from export_database_memory_snapshots import verify as verify_snapshots
from export_business_trajectories import verify as verify_trajectories

PUBLIC = ROOT / 'followup-records'
PRIVATE = ROOT / 'private-runs/database-followup-20261005'
BASE = 'ef79ae2e40dddbec3bbfcd27576b72da48ca6473'


def ref(path, **extra):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), **extra}


def member(path, name):
    with tarfile.open(path) as source:
        data = source.extractfile('./' + name).read()
    return data


def member_ref(path, name, **extra):
    return {**ref(path), 'member': name,
            'member_sha256': hashlib.sha256(member(path, name)).hexdigest(), **extra}


def texts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from texts(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in {'encrypted_content', 'signature'}:
                yield from texts(item)


def requests(out):
    result = []
    for path in out.glob('requests/*.attempt.json'):
        meta = read(path)
        native = path.with_name(path.name.replace('.attempt.json', '.native-request.json'))
        wire = path.with_name(path.name.replace('.attempt.json', '.request.json'))
        result.append((meta, read(native), native, wire))
    return sorted(result, key=lambda item: item[0]['timestamp'])


def archive_path(method, index):
    run = 'formal-db-' + method + '-r1'
    out = ROOT / 'private-runs' / run / f'task-{index:03d}'
    return out, out / 'native-state.tar.gz'


def restored_prefix(method, target):
    out, path = archive_path(method, target - 1)
    with tarfile.open(path) as source:
        names = [m.name.removeprefix('./') for m in source.getmembers() if m.isfile()]
    before = read(ROOT / 'database-memory-snapshots' /
                  ('codex' if method == 'codex' else 'claude_code') /
                  f'task-{target:03d}/before/.snapshot.json')
    checks = [hashlib.sha256(member(path, item['path'])).hexdigest() == item['sha256']
              for item in before['files']]
    assert all(checks)
    assert not any(n.startswith(f'tasks/task-{target:03d}/') for n in names)
    return {**ref(path), 'target_index': target, 'matches_exported_before': True,
            'memory_files_checked': len(checks), 'session_files': sum('/sessions/' in n or
                    ('.claude/projects/' in n and n.endswith('.jsonl')) for n in names),
            'native_database_files': [n for n in names if n.startswith('home/') and
                                     n.endswith('.sqlite')],
            'contains_target_task_directory': False,
            'meaning': 'original complete preceding archive, not reconstructed from final memories'}


def codex_chain():
    out, path = archive_path('codex', 30)
    target, _ = archive_path('codex', 33)
    sid = read(out / 'barrier.json')['session_id']
    jobs = json.loads(member(path, 'tasks/task-030/memory-jobs.json'))
    rows = [r for value in jobs.values() for r in value.get('stage1_outputs', [])
            if r['thread_id'] == sid]
    assert len(rows) == 1
    row = rows[0]
    stage = [r for value in jobs.values() for r in value.get('jobs', [])
             if r['kind'] == 'memory_stage1' and r['job_key'] == sid]
    assert len(stage) == 1 and stage[0]['status'] == 'done'
    # Inspect a standalone native DB backup rather than opening the source home.
    dbbytes = member(path, 'tasks/task-030/memories_1.sqlite')
    dbpath = PRIVATE / 'audit-only-Q31-memories.sqlite'
    dbpath.write_bytes(dbbytes)
    db = sqlite3.connect(dbpath.as_uri() + '?mode=ro&immutable=1', uri=True)
    db.row_factory = sqlite3.Row
    actual = dict(db.execute('SELECT * FROM stage1_outputs WHERE thread_id=?', (sid,)).fetchone())
    db.close()
    assert actual == row
    extraction = []
    for meta, payload, native, wire in requests(out):
        cm = payload.get('client_metadata', {})
        turn = json.loads(cm.get('x-codex-turn-metadata', '{}'))
        if turn.get('request_kind') == 'memory':
            content = '\n'.join(texts(payload.get('input', [])))
            extraction.append({**ref(native, attempt_id=meta['attempt_id']),
                'contains_final_binary_feedback': all(x in content for x in
                    ['Question 31: INCORRECT', '66.3', '94.8']),
                'kind': turn.get('request_kind'), 'wire': ref(wire)})
    assert extraction and all(x['contains_final_binary_feedback'] for x in extraction)
    main = []
    main_sid = read(target / 'barrier.json')['session_id']
    for meta, payload, native, wire in requests(target):
        cm = payload.get('client_metadata', {})
        turn = json.loads(cm.get('x-codex-turn-metadata', '{}'))
        if cm.get('thread_id') == main_sid and turn.get('request_kind') == 'turn':
            content = '\n'.join(texts([payload.get('instructions'), payload.get('input')]))
            main.append({**ref(native, attempt_id=meta['attempt_id']), 'wire': ref(wire),
                         'Q31_feedback_present': 'Question 31: INCORRECT' in content,
                         'Q31_candidate_values_present': '66.3' in content or '94.8' in content,
                         'input_sha256': hashlib.sha256(content.encode()).hexdigest()})
    assert main and all(not r['Q31_feedback_present'] and not r['Q31_candidate_values_present']
                        for r in main)
    relative = 'database-memory-snapshots/codex/task-{index:03d}/{phase}/home/.codex/memories'
    trees = []
    for index, phase in [(29, 'after'), (33, 'before')]:
        name = relative.format(index=index, phase=phase)
        tree = subprocess.check_output(['git', 'rev-parse', BASE + ':' +
            ROOT.relative_to(ROOT.parents[1]).as_posix() + '/' + name], cwd=ROOT, text=True).strip()
        files = sorted((ROOT / name).rglob('*'))
        files = [f for f in files if f.is_file()]
        trees.append({'path': name, 'git_tree': tree, 'files': len(files),
                      'bytes': sum(f.stat().st_size for f in files),
                      'file_sha256': {f.relative_to(ROOT / name).as_posix(): sha(f) for f in files}})
    assert trees[0]['file_sha256'] == trees[1]['file_sha256']
    assert trees[0]['git_tree'] == trees[1]['git_tree'] == 'dc2c365993a9d53376f4626d4b26507a38ee0273'
    return {'source_index': 30, 'target_index': 33, 'session_id': sid,
        'feedback': ref(out / 'legal-episode.json', field='feedback'),
        'stage1_input': extraction,
        'stage1_db': member_ref(path, 'tasks/task-030/memories_1.sqlite',
                                table='stage1_outputs', row_key=sid),
        'stage1_output': {'raw_memory_sha256': hashlib.sha256(row['raw_memory'].encode()).hexdigest(),
            'rollout_summary_sha256': hashlib.sha256(row['rollout_summary'].encode()).hexdigest(),
            'source_updated_at': row['source_updated_at'], 'selected_for_phase2': row['selected_for_phase2'],
            'excerpt': next(l for l in row['raw_memory'].splitlines() if '66.3%' in l)},
        'watermarks': {'extracted': 'verified_contains_feedback_and_both_candidates',
                       'materialized': 'not_in_Q34_pre_target_memory_files',
                       'solver_visible': 'not_in_any_captured_Q34_main_request'},
        'memory_trees': trees, 'actual_main_requests': main,
        'unknowns': ['This demonstrates captured input absence; it does not predict whether R1 improves behavior.',
                     'Extraction calls its alternative likely intended but does not validate it.'],
        'D1_decision': 'execute_when_current_responses_route_is_ready'}


def claude_chain():
    base = ROOT / 'database-memory-snapshots/claude_code'
    snapshots = []
    for idx, phase in [(20, 'after'), (22, 'before'), (22, 'after'), (24, 'before'), (24, 'after')]:
        p = base / f'task-{idx:03d}' / phase / 'home/.claude/projects/-state-work-database/memory'
        files = [f for f in p.glob('*.md') if f.name in ['MEMORY.md',
                 'clbench-schema-conventions.md', 'clbench-list-price-column-ambiguity.md']]
        snapshots.append({'index': idx, 'phase': phase, 'files': [ref(f) for f in files]})
    events = []
    for idx in [20, 22, 24]:
        out, path = archive_path('claude', idx)
        values = [json.loads(l) for l in member(path, f'tasks/task-{idx:03d}/events.jsonl').decode().splitlines()]
        for event in values:
            if event.get('type') != 'assistant':
                continue
            for b in event['message'].get('content', []):
                inp = b.get('input', {})
                content = inp.get('content', inp.get('new_string', ''))
                if b.get('type') == 'tool_use' and b.get('name') in {'Write', 'Edit'} and (
                        'no prc_v2 recorded' in content or 'CONFIRMED GT' in content or '21.99 CORRECT' in content):
                    events.append({**member_ref(path, f'tasks/task-{idx:03d}/events.jsonl'),
                        'index': idx, 'timestamp': event.get('timestamp'), 'tool_id': b['id'],
                        'tool': b['name'], 'file_path': inp.get('file_path'),
                        'write_sha256': hashlib.sha256(content.encode()).hexdigest(),
                        'historical_absence_claim': 'no prc_v2 recorded' in content,
                        'strong_binding_claim': 'CONFIRMED GT' in content or 'verified twice' in content})
    claim_event = next(e for e in events if e['historical_absence_claim'])
    out, _ = archive_path('claude', 22)
    claim_requests = []
    preceding = []
    for meta, payload, native, wire in requests(out):
        content = '\n'.join(texts(payload.get('messages', [])))
        # Only history visible before the response that emits the Write counts as writer input.
        if meta['timestamp'] < claim_event['timestamp']:
            preceding.append({**ref(native, attempt_id=meta['attempt_id']),
                              'Q21_summary_mentioned': 'Q21' in content,
                              'historical_Q21_DDL_provenance': 'not_demonstrated_by_current_Q23_DDL',
                              'current_schema_and_old_summary_do_not_establish_historical_schema_exposure': True})
        if 'no prc_v2 recorded' in content:
            claim_requests.append(ref(native, attempt_id=meta['attempt_id']))
    q21 = read(ROOT / 'trajectories/claude_code/database/task-020.json')
    ddl = next(t['observation'] for t in q21['tools'] if 'prc_v2' in str(t['observation']) and 'CREATE TABLE' in str(t['observation']))
    assert 'prc_v2' in ddl
    return {'snapshots': snapshots, 'write_events': events,
        'first_historical_absence_write': claim_event, 'requests_containing_claim': claim_requests,
        'pre_write_requests': preceding,
        'Q21_contradictory_source': ref(ROOT / 'trajectories/claude_code/database/task-020.json',
            locator='tools: schema DDL observation contains prc_v2',
            observation_sha256=hashlib.sha256(ddl.encode()).hexdigest()),
        'watermarks': {'extracted': 'native_foreground_Write_and_Edit_observed',
                       'materialized': 'claim_persisted_in_Q23_and_Q25_snapshots',
                       'solver_visible': 'Q25_reads_old_claim_before_editing_it'},
        'unknowns': ['Q23 current schema is visible, but this alone does not establish that Q21 DDL was read by the Q23 writer.',
                     'Historical-source access is available through the restored same-method session prefix; access is not exposure.',
                     'No net behavioral effect is inferred from historical snapshots.'],
        'reviewer': 'Codex /root source audit, not human gold labels or a paid LLM judge'}


def grading():
    source = UPSTREAM / 'src/tasks/database_exploration/task.py'
    tree = ast.parse(source.read_text('utf8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DatabaseExploration')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_evaluate_answer')
    scope = {'re': re, 'Any': object}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(source), 'exec'), scope)
    evaluate = scope['_evaluate_answer']
    qs = read(UPSTREAM / 'data/database_exploration/questions_post_drift.json')
    questions = {str(q['question_id']): q for q in qs}
    assets = []
    for row in read(ROOT / 'records/database-assets.json')['assets']:
        path = UPSTREAM / 'data/database_exploration' / row['name']
        actual = ref(path)
        assert actual['sha256'] == row['sha256']
        assets.append({**actual, 'bytes': path.stat().st_size, 'matches_accepted_asset': True})
    checks = []
    for method, idx in [('claude_code',20),('claude_code',22),('claude_code',24),('no_memory',24),('codex',33),('codex',27)]:
        path = ROOT / 'trajectories' / method / 'database' / f'task-{idx:03d}.json'
        episode = read(path)
        answer = next(t['action']['content'] for t in episode['tools'] if t['action']['action'] == 'ANSWER')
        actual = evaluate(None, answer, questions[str(episode['instance_id'])])
        assert actual == ('INCORRECT' not in episode['feedback'] and 'CORRECT' in episode['feedback'])
        checks.append({**ref(path), 'method': method, 'index': idx, 'instance_id': episode['instance_id'],
                       'recorded_answer': answer, 'official_correct': actual, 'feedback_matches_actual_grader': True})
    return {'grader': ref(source), 'matches_recorded_grader': sha(source) == read(ROOT/'records/grading-policy.json')['source_sha256'],
        'question_files': [ref(UPSTREAM / 'data/database_exploration' / n) for n in ['questions.json', 'questions_post_drift.json']],
        'databases': assets, 'adapters': [ref(ROOT / n) for n in ['database_adapter.py', 'protocol.py']],
        'selected_recorded_submissions': checks,
        'feedback_boundary': 'original binary feedback retained; reference answers, SQL, tolerance never mounted into solver',
        'hidden_grading_material': 'private researcher/evaluator process only', 'official_scores_changed': False}


def verify_recorded_queries():
    """Reproduce only recorded queries, with the installed upstream formatter.

    This researcher-only check executes no new candidate or reference SQL and
    supplies no output to any solver/writer. Source databases open immutable RO.
    """
    source=UPSTREAM/'src/tasks/database_exploration/task.py'
    tree=ast.parse(source.read_text('utf8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DatabaseExploration')
    functions=[n for n in cls.body if isinstance(n,ast.FunctionDef) and
               n.name in {'_execute_sql','_format_results'}]
    mini=ast.ClassDef(name='ReadonlyQueries',bases=[],keywords=[],body=functions,decorator_list=[])
    scope={'time':time,'sqlite3':sqlite3,'MAX_QUERY_RESULT_ROWS':50,'SQL_QUERY_TIMEOUT_SECONDS':10}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[mini],type_ignores=[])),str(source),'exec'),scope)
    query=scope['ReadonlyQueries']()
    dbpath=UPSTREAM/'data/database_exploration/products_drifted.db'
    query._conn=sqlite3.connect(dbpath.as_uri()+'?mode=ro&immutable=1',uri=True)
    query._conn.execute('PRAGMA query_only=ON')
    results=[]
    try:
        for method,index in [('claude_code',20),('claude_code',22),('claude_code',24),
                             ('codex',30),('codex',33),('codex',27)]:
            path=ROOT/'trajectories'/method/'database'/f'task-{index:03d}.json'
            episode=read(path)
            for offset,tool in enumerate(episode['tools']):
                if tool['action']['action']!='QUERY':continue
                sql=tool['action']['content']
                actual=query._execute_sql(sql)
                observed=tool['observation'].split('\n\n',1)[1]
                matches=actual==observed
                results.append({**ref(path),'index':index,'method':method,'tool_offset':offset,
                    'query_sha256':hashlib.sha256(sql.encode()).hexdigest(),
                    'observation_body_sha256':hashlib.sha256(observed.encode()).hexdigest(),
                    'replayed_body_sha256':hashlib.sha256(actual.encode()).hexdigest(),
                    'matches_recorded_candidate_observation':matches})
                assert matches, f'Recorded query mismatch: {method}/{index}/{offset}'
    finally:query._conn.close()
    return {'status':'passed','queries':results,'model_calls':0,
            'read_only_database':ref(dbpath),'new_candidate_SQL':False,
            'scope':'Recorded queries including multi-candidate values; no uncomputed Q23 alternative is invented.'}


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    plan = read(ROOT / 'config/database-followup.plan.json')
    assert plan['evidence_commit'] == BASE
    report = {'schema_version': 'database-followup.d0.v1', 'at': datetime.now(timezone.utc).isoformat(),
        'execution_authorization': 'User requested completing DATABASE_FOLLOWUP_LOCAL_CODEX.md; bounded plan applies.',
        'evidence_commit': BASE, 'plan': ref(ROOT / 'config/database-followup.plan.json'),
        'status': 'completed', 'model_calls': 0,
        'verification': {'snapshots': verify_snapshots(), 'trajectories': verify_trajectories()},
        'codex': codex_chain(), 'claude': claude_chain(), 'grading': grading(),
        'recorded_candidate_reproduction':verify_recorded_queries(),
        'complete_prefixes': [restored_prefix('codex', idx) for idx in [27,33]] +
                             [restored_prefix('claude', idx) for idx in [22,24]],
        'route': {'configuration': ref(ROOT / 'config/active-provider.json'),
                  'active_provider': 'aixoras', 'accepted_protocol': 'responses',
                  'native_anthropic_acceptance': 'unavailable',
                  'legacy_gateway': 'Z.AI loader explicitly rejects retired route'},
        'decisions': {'D1': 'eligible; common active Responses route and fresh R0 required',
                      'D2': 'blocked: no accepted native Anthropic endpoint for authorized active provider; no exploration allowed',
                      'D3': 'blocked_by_D2'},
        'privacy': 'Only bounded source identifiers, hashes and already-exported excerpts published; raw requests/state stay ignored.'}
    assert report['grading']['matches_recorded_grader']
    save(PUBLIC / 'd0-evidence.json', report)
    print(json.dumps({'status': report['status'], 'model_calls': 0, 'decisions': report['decisions']}))


if __name__ == '__main__':
    main()
