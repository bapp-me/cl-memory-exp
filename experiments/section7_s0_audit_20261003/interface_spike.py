"""Bounded native-interface probe, not an agent benchmark or S0 acceptance.

Run with an existing Hermes Python environment and the pinned source checkout.
No credentials, network, subprocesses, task data, or model responses are used.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import traceback
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'records/interface-spike.json')
    args = parser.parse_args()
    source = args.source.resolve()
    for key in list(os.environ):
        if any(token in key.upper() for token in ('API_KEY', 'API_TOKEN', 'AUTH_TOKEN')):
            os.environ.pop(key)
    scratch = ROOT / '.runtime'
    scratch.mkdir(exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix='interface-', dir=scratch))
    work = home / 'work'
    work.mkdir()
    os.environ.update(HERMES_HOME=str(home), HERMES_RUNTIME_DIR=str(home / 'runtime'),
                      HERMES_TELEMETRY_ENABLED='false', TERMINAL_CWD=str(work),
                      LOCALAPPDATA=str(home / 'localappdata'), UV_CACHE_DIR=str(home / 'uv'),
                      HERMES_SESSION_PLATFORM='api_server')
    (home / 'config.yaml').write_text(
        'memory:\n  memory_enabled: true\n  user_profile_enabled: true\n'
        '  write_approval: false\nskills:\n  write_approval: false\n'
        '  external_dirs: []\n  sync:\n    enabled: false\n', encoding='utf-8')
    os.chdir(work)
    sys.path.insert(0, str(source))
    sys.dont_write_bytecode = True
    # CPython's Windows platform detection invokes the OS version command.
    # Warm only that stdlib metadata cache before prohibiting child processes.
    host_platform = platform.uname()._asdict()
    blocked = []

    def audit(event, values):
        if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system', 'os.posix_spawn'}:
            blocked.append({'event': event})
            raise OSError('Interface spike prohibits network and subprocesses')

    sys.addaudithook(audit)
    checks = []

    def check(name, operation):
        try:
            evidence = operation()
            checks.append({'name': name, 'passed': True, 'evidence': evidence})
        except Exception as exc:
            checks.append({'name': name, 'passed': False, 'error': f'{type(exc).__name__}: {exc}',
                           'traceback': traceback.format_exc()})

    def memory():
        from tools.memory_tool import MemoryStore
        store = MemoryStore()
        store.load_from_disk()
        before = store.format_for_system_prompt('memory')
        assert store.add('memory', 'Fixture schema version is blue.')['success']
        assert store.format_for_system_prompt('memory') == before
        fresh = MemoryStore()
        fresh.load_from_disk()
        assert 'blue' in fresh.format_for_system_prompt('memory')
        assert fresh.replace('memory', 'blue', 'Fixture schema version is green.')['success']
        assert 'green' in (home / 'memories/MEMORY.md').read_text(encoding='utf-8')
        return {'native_memory_store': True, 'frozen_prompt_unchanged_after_write': True,
                'next_store_load_observes_disk': True, 'replace_persisted': True}

    def sessions():
        from hermes_state import SessionDB
        from tools.session_search_tool import session_search
        db = SessionDB(home / 'state.db')
        try:
            db.create_session('fixture-source', 'cli')
            anchor = db.append_message('fixture-source', 'user', 'Fixture cobalt schema exploration')
            db.append_message('fixture-source', 'assistant', 'The source column is cobalt_total.')
            db.end_session('fixture-source', 'fixture')
            discovery = json.loads(session_search(query='cobalt', db=db))
            read = json.loads(session_search(session_id='fixture-source', db=db))
            scroll = json.loads(session_search(session_id='fixture-source', around_message_id=anchor, db=db))
            absent = json.loads(session_search(query='impossibletokenzxq', db=db))
            assert discovery['success'] and 'cobalt_total' in json.dumps(discovery)
            assert read['success'] and 'cobalt_total' in json.dumps(read)
            assert scroll['success'] and 'cobalt_total' in json.dumps(scroll)
            assert absent['success'] and 'cobalt_total' not in json.dumps(absent)
        finally:
            db.close()
        with sqlite3.connect(home / 'state.db') as original, sqlite3.connect(home / 'snapshot.db') as snapshot:
            original.backup(snapshot)
        restored = SessionDB(home / 'snapshot.db', read_only=True)
        try:
            assert 'cobalt_total' in session_search(query='cobalt', db=restored)
            rejected = False
            try:
                restored.append_message('fixture-source', 'user', 'MUST NOT WRITE')
            except Exception:
                rejected = True
            assert rejected
        finally:
            restored.close()
        return {'search_shapes': ['discovery', 'read', 'scroll', 'no_match'],
                'sqlite_backup_restored': True, 'native_readonly_db_write_rejected': True,
                'scope': 'SQLite only; not a whole-profile read-only guarantee'}

    def skills():
        from tools.skill_manager_tool import skill_manage
        from tools.skills_tool import skill_view
        content = '---\nname: fixture-skill\ndescription: Synthetic interface fixture.\n---\n# Fixture\nRead the current schema before calculating.\n'
        created = json.loads(skill_manage('create', 'fixture-skill', content=content))
        assert created['success'], created
        viewed = json.loads(skill_view('fixture-skill', preprocess=False))
        assert 'Read the current schema' in json.dumps(viewed)
        edited = json.loads(skill_manage('patch', 'fixture-skill', old_string='before calculating', new_string='before aggregating'))
        assert edited['success'], edited
        assert 'before aggregating' in skill_view('fixture-skill', preprocess=False)
        invalid = json.loads(skill_manage('create', '../escape', content=content))
        assert not invalid.get('success', False)
        return {'create_view_patch': True, 'traversal_name_rejected': True,
                'preprocess': False, 'limitation': 'No skill script execution or whole sandbox test'}

    def pending():
        from tools import write_approval as wa
        from tools.skill_manager_tool import skill_manage
        # Exercise the native staging branch without changing production config.
        with patch.object(wa, 'write_approval_enabled', return_value=True):
            result = json.loads(skill_manage('patch', 'fixture-skill', old_string='before aggregating', new_string='before joining'))
        assert result.get('staged'), result
        assert wa.get_pending(wa.SKILLS, result['pending_id'])
        current = next((home / 'skills').rglob('SKILL.md')).read_text(encoding='utf-8')
        assert 'before aggregating' in current and 'before joining' not in current
        from tools.memory_tool import MemoryStore, memory_tool
        from tools.skill_provenance import set_current_write_origin, reset_current_write_origin
        store = MemoryStore()
        store.load_from_disk()
        origin = set_current_write_origin('background_review')
        try:
            # Native safety rule applies even with memory.write_approval=false.
            background = json.loads(memory_tool('replace', old_text='green',
                                    content='Fixture schema version is violet.', store=store))
        finally:
            reset_current_write_origin(origin)
        assert background.get('proposal_staged'), background
        assert 'green' in (home / 'memories/MEMORY.md').read_text(encoding='utf-8')
        return {'native_pending_file_created': True, 'unapproved_content_not_committed': True,
                'background_memory_replace_staged_even_with_approval_config_false': True,
                'mock': 'skill write_approval_enabled=True branch; memory uses actual config and native origin context'}

    def nudges():
        from agent.turn_context import _tick_memory_nudge
        agent = SimpleNamespace(_memory_nudge_interval=10, valid_tool_names={'memory'},
                                _memory_store=object(), _turns_since_memory=0)
        results = [_tick_memory_nudge(agent) for _ in range(10)]
        assert results == [False] * 9 + [True]
        independent = [_tick_memory_nudge(SimpleNamespace(_memory_nudge_interval=10,
                       valid_tool_names={'memory'}, _memory_store=object(), _turns_since_memory=0)) for _ in range(12)]
        assert independent == [False] * 12
        return {'one_session_ten_turns': results, 'twelve_fresh_one_turn_sessions': independent,
                'mock': 'parent state only; actual native counter function'}

    def native_entry():
        from run_agent import AIAgent
        signature = inspect.signature(AIAgent)
        needed = {'session_db', 'skip_background_review', 'enabled_toolsets', 'api_mode', 'base_url'}
        assert needed <= set(signature.parameters)
        return {'AIAgent_imported': True, 'required_parameters': sorted(needed),
                'constructed': False, 'run_conversation_called': False}

    for name, fn in [('memory_snapshot', memory), ('session_search_and_db_restore', sessions),
                     ('skill_interfaces', skills), ('pending_write_semantics', pending),
                     ('native_review_trigger', nudges), ('native_entry_import', native_entry)]:
        check(name, fn)
    packages = {}
    for name in ['openai', 'anthropic', 'httpx', 'pydantic', 'ruamel.yaml', 'psutil']:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    report = {'schema': 's0-interface-spike-v1', 'python': sys.version, 'packages': packages,
              'platform': host_platform,
              'source': str(source), 'synthetic_only': True, 'model_calls': 0,
              'network_policy': 'Python audit hook denies DNS/connect and subprocesses before upstream imports',
              'blocked_attempts': blocked, 'checks': checks,
              'limitations': ['No performance task or provider compatibility test',
                              'Not S0 end-to-end acceptance', 'No review model or background completion test'],
              'passed': all(row['passed'] for row in checks),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({**{k: report[k] for k in ('passed', 'python', 'packages', 'blocked_attempts')},
                      'checks': [{k: row[k] for k in ('name', 'passed', 'error') if k in row} for row in checks]},
                     ensure_ascii=True, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
