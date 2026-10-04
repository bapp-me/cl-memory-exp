"""Unmodified upstream task and scorer behind a public-field-only boundary."""
from __future__ import annotations
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from prepare import ROOT, UPSTREAM, read, save
from protocol import database_feedback

# This module runs only in the controller/evaluator, never in the agent process.
sys.path.insert(0, str(UPSTREAM))
from src.interface import Response, format_task_agent_brief
from src.tasks.database_exploration.task import DatabaseExploration, DatabaseAction


class DatabaseStream:
    def __init__(self, directory, *, restore=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.private = self.directory / 'evaluator-private'
        self.private.mkdir(exist_ok=True)
        os.chdir(UPSTREAM)
        tempfile.tempdir = str(self.private)
        self.task = DatabaseExploration(schedule='default', run_index=0)
        self.query = self.task.reset()
        self._snapshot_signature = None
        expected = read(ROOT / 'records/task-manifest.json')['database_exploration']
        if [str(q['question_id']) for q in self.task.instances] != [q['instance_id'] for q in expected]:
            raise RuntimeError('Task order differs from manifest')
        if restore and (self.private / 'state.json').exists():
            self._restore()

    def public_query(self):
        query = self.query
        return {'prompt': query.prompt, 'instance_id': query.instance_id, 'index': query.instance_index,
                'brief': format_task_agent_brief(self.task.get_agent_brief())}

    def action(self, value, *, timed_out=False):
        index = self.task._current_question_idx
        result = self.task.step(Response(action=DatabaseAction(**value),
            metadata={'latency_timeout': True} if timed_out else {}))
        # Upstream consumes the migration notice when constructing next_query.
        # Keep that exact query private until the previous memory barrier passes.
        self.query = result.next_query
        if result.observation.instance_complete:
            record = self.task._question_history[-1]
            save(self.private / f'result-{index:03d}.json', {'record': record,
                'official_feedback': result.observation.content,
                'outcome': result.instance_outcome.__dict__ if result.instance_outcome else None})
            observation = database_feedback(record, index + 1)
        else:
            observation = result.observation.content
        self.checkpoint()
        return {'observation': observation, 'instance_complete': result.observation.instance_complete,
                'done': result.done}

    def checkpoint(self):
        # SQLite backup includes committed WAL content; never copy only the live main file.
        if self.task._conn.in_transaction:
            raise RuntimeError('Uncommitted upstream SQL transaction; preserve state and stop before backup')
        live_path = Path(self.task._conn.execute('PRAGMA database_list').fetchone()[2])
        candidates = [live_path, Path(str(live_path) + '-wal')]
        signature = (str(live_path), self.task._conn.total_changes,
                     tuple((p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None for p in candidates))
        if signature != self._snapshot_signature:
            temp = self.private / 'database.next.db'
            target = sqlite3.connect(str(temp))
            try:
                self.task._conn.backup(target)
                target.execute('PRAGMA journal_mode=DELETE')
            finally: target.close()
            temp.replace(self.private / 'database.snapshot.db')
            self._snapshot_signature = signature
        fields = ['_current_question_idx', '_queries_this_question', '_question_history',
                  '_awaiting_action', '_drift_applied', '_stage_change_notice']
        snapshot = {k: getattr(self.task, k) for k in fields}
        snapshot['next_query'] = ({'prompt': self.query.prompt, 'instance_id': self.query.instance_id,
                                  'instance_index': self.query.instance_index} if self.query else None)
        save(self.private / 'state.json', snapshot)

    def _restore(self):
        snapshot = read(self.private / 'state.json')
        from src.interface import Query
        query = snapshot.pop('next_query')
        self.query = Query(response_schema=DatabaseAction, **query) if query else None
        for name, value in snapshot.items(): setattr(self.task, name, value)
        self.task._conn.close()
        self.task._conn = sqlite3.connect(str(self.private / 'database.snapshot.db'))
        # Restore to a separate live DB so future backup never targets itself.
        live = sqlite3.connect(str(self.private / 'database.resumed.db'))
        self.task._conn.backup(live); self.task._conn.close(); self.task._conn = live
        self.task._temp_db_path = self.private / 'database.resumed.db'

    def close(self):
        if self.task._conn: self.task._conn.close()


def main():
    import uuid
    directory = ROOT / '.local/fixtures' / ('database-' + uuid.uuid4().hex)
    stream = DatabaseStream(directory)
    first = stream.public_query()
    assert 'db_path' not in first and 'answer' not in first and 'sql' not in first
    r = stream.action({'action': 'QUERY', 'content': '.tables'})
    assert not r['instance_complete'] and 'Query result (1/15' in r['observation']
    r = stream.action({'action': 'QUERY', 'content': 'SELECT definitely_absent FROM definitely_absent'})
    assert 'ERROR' in r['observation'] and stream.task._queries_this_question == 2
    r = stream.action({'action': 'ANSWER', 'content': 'FIXTURE_WRONG_ANSWER'})
    assert r['instance_complete'] and 'INCORRECT' in r['observation']
    assert 'Correct answer:' not in r['observation']
    first_id = first['instance_id']
    stream.close()
    stream = DatabaseStream(directory, restore=True)
    assert stream.public_query()['index'] == 1 and stream.public_query()['instance_id'] != first_id
    for _ in range(16): r = stream.action({'action': 'QUERY', 'content': 'SELECT 1'})
    assert r['instance_complete'] and 'budget exceeded' in r['observation']
    r = stream.action({'action': 'ANSWER', 'content': ''}, timed_out=True)
    assert r['instance_complete'] and 'TIMED OUT' in r['observation']
    while stream.task._current_question_idx < 20:
        stream.action({'action': 'ANSWER', 'content': 'FIXTURE_WRONG_ANSWER'})
    assert stream.task._drift_applied and stream.public_query()['index'] == 20
    assert 'NOTICE' in stream.public_query()['prompt']
    stream.close()
    save(ROOT / 'records/database-fixtures.json', {'status': 'passed', 'model_calls': 0,
        'checks': ['official QUERY success/error counts', 'ANSWER grading', 'hidden feedback projection',
                   'resume after submission', 'query budget exhaustion', 'timeout', 'migration at index20'],
        'raw': directory.relative_to(ROOT).as_posix(), 'formal_ready': False})
    print({'database_fixtures': 'passed', 'model_calls': 0})


if __name__ == '__main__': main()
