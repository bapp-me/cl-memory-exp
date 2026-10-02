"""Safe in-process task tools and two swappable persistent-memory protocols."""
import copy
import csv
import hashlib
import io
import json
import re
import sqlite3
import threading
import time
from pathlib import Path

MEMORY_BUDGET = 3200


def schema(name, description, properties, required=()):
    return {'name': name, 'description': description, 'parameters': {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}}


S = {'type': 'string'}
I = {'type': 'integer'}
O = {'type': 'object', 'additionalProperties': True}
SCHEMAS = {
    'list_files': schema('list_files', 'List all files in the current isolated task workspace.', {}),
    'read_file': schema('read_file', 'Read a workspace file. Binary files return a short byte prefix and size.', {'path': S}, ['path']),
    'write_file': schema('write_file', 'Replace a workspace JSON configuration file with JSON text.', {'path': S, 'content': S}, ['path', 'content']),
    'sql': schema('sql', 'Execute a read-only SQLite query. Schema PRAGMAs and sqlite_master are available. Maximum 50 rows.', {'query': S}, ['query']),
    'api': schema('api', 'Call the local mock API. Discover available endpoints and methods in workspace documentation. No external network.', {'method': S, 'path': S, 'params': O, 'body': O}, ['method', 'path']),
    'build': schema('build', 'Run a command in the local mock pnpm test engine; actual fixture assertions are evaluated. Available command forms are documented in README.md.', {'command': S}, ['command']),
    'config': schema('config', 'Read the effective application runtime configuration after applying deployment overrides.', {}),
    'parse_csv': schema('parse_csv', 'Parse a local CSV export and return all rows (at most 50). Defaults: UTF-8, comma, no skipped preamble. Supply parser parameters when needed.', {'path': S, 'encoding': S, 'delimiter': S, 'skip_lines': I}, ['path']),
    'render_report': schema('render_report', 'Save a numeric report specification in the isolated workspace. Supply language, layout, decimals and value.', {'language': S, 'layout': S, 'decimals': I, 'value': {'type': 'number'}}, ['language', 'layout', 'decimals', 'value']),
    'experience': schema('experience', 'Persistent experience store across independent tasks. Search/get, put (create or fully replace an entry) or delete. You may curate useful experience at your discretion. Content budget 3200 characters; no automatic end-of-task write. Empty search lists entries. Changes are immediately searchable.', {'op': {'type': 'string', 'enum': ['search', 'get', 'put', 'delete']}, 'id': S, 'query': S, 'content': S, 'title': S}, ['op']),
}


class Environment:
    def __init__(self, spec, directory, mechanism='file', seed=None):
        self.spec = copy.deepcopy(spec)
        self.files = self.spec['files']
        self.data = self.spec['data']
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.mechanism = mechanism
        self.entries = copy.deepcopy(seed or {})
        self.lock = threading.RLock()
        self.calls = []
        self.phase = 'consumer'
        self.db = None
        if 'sql' in self.data:
            self.db = sqlite3.connect(':memory:', check_same_thread=False)
            for stmt in self.data['sql']['schema']:
                self.db.execute(stmt)
            for table, rows in self.data['sql']['rows'].items():
                self.db.executemany(f'INSERT INTO {table} VALUES({",".join("?" for _ in rows[0])})', rows)
            self.db.commit()
            self.db.execute('PRAGMA query_only=ON')
        self.save_memory('memory_before')

    def save_memory(self, name='memory_after'):
        target = self.directory / name
        target.mkdir(exist_ok=True)
        content = json.dumps(self.entries, ensure_ascii=False, indent=2)
        (target / 'entries.json').write_text(content + '\n', encoding='utf-8')
        (target / 'MEMORY.md').write_text(self.memory_text(), encoding='utf-8')
        # Deterministic on-demand lexical index; rebuilt synchronously after every write.
        index = {key: {'version': v['version'], 'tokens': sorted(set(re.findall(r'\w+', v.get('title', '') + ' ' + v['content'].lower())))} for key, v in self.entries.items()}
        (target / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return hashlib.sha256(content.encode()).hexdigest()

    def memory_text(self):
        return '\n\n'.join(f'[{k} v{v["version"]}] {v.get("title", "")}\n{v["content"]}' for k, v in self.entries.items())

    def system_memory(self, ensure=False):
        if self.mechanism == 'none':
            return ''
        if self.mechanism == 'file' or ensure:
            return '\nPersistent experience loaded from the current store:\n' + (self.memory_text() or '(empty)')
        return '\nA persistent experience store is available through experience search/get. No entries are automatically loaded.'

    def tool_schemas(self):
        names = self.spec['tools'] + (['experience'] if self.mechanism != 'none' else [])
        return [SCHEMAS[x] for x in names]

    def call(self, name, args):
        with self.lock:
            started = time.monotonic()
            before = copy.deepcopy(self.entries)
            try:
                if name not in [s['name'] for s in self.tool_schemas()]:
                    raise ValueError('Tool is not available in this task')
                result = self._call(name, args)
            except Exception as exc:
                result = {'error': type(exc).__name__ + ': ' + str(exc)}
            row = {'step': len(self.calls) + 1, 'phase': self.phase, 'tool': name, 'args': args, 'result': result, 'seconds': round(time.monotonic() - started, 6), 'error': bool(isinstance(result, dict) and ('error' in result or result.get('status', 200) >= 400))}
            if before != self.entries:
                row['memory_before'] = before
                row['memory_after'] = copy.deepcopy(self.entries)
            self.calls.append(row)
            with (self.directory / 'tools.jsonl').open('a', encoding='utf-8') as file:
                file.write(json.dumps(row, ensure_ascii=False) + '\n')
            self.save_memory()
            return result

    def _call(self, name, a):
        if name == 'list_files':
            return sorted(set(self.files) | set(self.data.get('blobs', {})))
        if name == 'read_file':
            if a['path'] in self.files:
                return {'path': a['path'], 'content': self.files[a['path']]}
            blob = bytes.fromhex(self.data.get('blobs', {})[a['path']])
            return {'path': a['path'], 'bytes': len(blob), 'prefix_hex': blob[:80].hex()}
        if name == 'write_file':
            if a['path'] not in ('settings.json', 'deployment.json'):
                raise ValueError('This task permits only the two application configuration files')
            json.loads(a['content'])
            self.files[a['path']] = a['content']
            return {'saved': a['path']}
        if name == 'sql':
            q = a['query']
            if not re.match(r'^\s*(SELECT|WITH|PRAGMA\s+(table_info|table_list|index_list))\b', q, re.I):
                raise ValueError('Only read-only SELECT/WITH and schema PRAGMAs permitted')
            cur = self.db.execute(q)
            rows = cur.fetchmany(51)
            return {'columns': [d[0] for d in cur.description], 'rows': rows[:50], 'truncated': len(rows) > 50}
        if name == 'api':
            path, method = a['path'], a['method'].upper()
            if path == '/info' and method == 'GET':
                return {'version': self.data['version'], 'documentation': 'api.json'}
            if path == '/items' and method == 'GET' and 'items' in self.data:
                p = a.get('params', {})
                limit = min(max(int(p.get('limit', 3)), 1), 3)
                cursor_mode = self.data['version'] == 2
                start = int(str(p.get('cursor') or 'pos:0').split(':')[-1]) if cursor_mode else (int(p.get('page', 1)) - 1) * limit
                items = self.data['items'][start:start + limit]
                end = start + len(items)
                return {'items': items, 'total': len(self.data['items']), 'next_cursor' if cursor_mode else 'next_page': (f'pos:{end}' if cursor_mode else int(p.get('page', 1)) + 1) if end < len(self.data['items']) else None}
            if path == '/profile' and 'profile' in self.data:
                if method == 'GET':
                    return copy.deepcopy(self.data['profile'])
                expected = 'PUT' if self.data['version'] == 2 else 'PATCH'
                if method != expected:
                    return {'status': 405, 'error': 'Method not allowed', 'Allow': 'GET, ' + expected}
                body = a.get('body', {})
                if set(body) - {'timezone', 'email', 'digest'}:
                    return {'status': 400, 'error': 'Unknown profile field'}
                self.data['profile'] = ({'timezone': 'UTC', 'email': None, 'digest': False} | body) if expected == 'PUT' else (self.data['profile'] | body)
                return {'status': 200, 'profile': copy.deepcopy(self.data['profile'])}
            return {'status': 404, 'error': 'Unknown endpoint; see api.json'}
        if name == 'build':
            command = a['command'].strip()
            if command == 'pnpm test':
                suite = json.loads(self.files['package.json'])['scripts']['test'].split()[-1]
            elif command == 'pnpm --filter ui test':
                suite = 'ui'
            else:
                return {'exit_code': 1, 'error': 'Unsupported local command; see README.md'}
            passed = True
            if suite == 'ui':
                source = json.loads(self.files['packages/ui/source.json'])
                passed = source['base'] + source['increment'] == source['expected']
            self.data['tested'].append(suite)
            return {'exit_code': 0 if passed else 1, 'executed_suites': [suite], 'passed': passed}
        if name == 'config':
            config = json.loads(self.files['settings.json'])
            variables = json.loads(self.files['deployment.json'])['environment']
            if 'APP_PORT' in variables:
                config['port'] = int(variables['APP_PORT'])
            return config
        if name == 'parse_csv':
            text = bytes.fromhex(self.data['blobs'][a['path']]).decode(a.get('encoding', 'utf-8'))
            lines = text.splitlines()[a.get('skip_lines', 0):]
            delimiter = a.get('delimiter', ',')
            if delimiter == '\\t':
                delimiter = '\t'
            return {'rows': list(csv.DictReader(io.StringIO('\n'.join(lines)), delimiter=delimiter))[:50]}
        if name == 'render_report':
            self.data['report'] = copy.deepcopy(a)
            return {'saved': 'report.json', 'report': a}
        if name == 'experience':
            op = a['op']
            if op == 'get':
                return copy.deepcopy(self.entries[a['id']])
            if op == 'search':
                tokens = set(re.findall(r'\w+', a.get('query', '').lower()))
                ranked = []
                for key, v in self.entries.items():
                    text = (v.get('title', '') + ' ' + v['content']).lower()
                    score = sum(t in text for t in tokens)
                    if score or not tokens:
                        ranked.append((score, key, v))
                return {'matches': [{'id': k, **v} for _, k, v in sorted(ranked, key=lambda x: (-x[0], x[1]))[:3]], 'index': 'synchronous current-version lexical search', 'total_entries': len(self.entries)}
            if op == 'put':
                key = a['id']
                candidate = copy.deepcopy(self.entries)
                candidate[key] = {'title': a.get('title', ''), 'content': a['content'], 'version': candidate.get(key, {}).get('version', 0) + 1}
                chars = sum(len(v['content']) + len(v['title']) for v in candidate.values())
                if chars > MEMORY_BUDGET:
                    raise ValueError(f'Memory budget exceeded: {chars}/{MEMORY_BUDGET} characters. Existing store unchanged.')
                self.entries = candidate
                return {'saved': key, 'version': candidate[key]['version'], 'characters': chars}
            if op == 'delete':
                del self.entries[a['id']]
                return {'deleted': a['id']}
        raise ValueError('Unsupported tool operation')

    def final_state(self):
        out = {k: self.data[k] for k in ('profile', 'tested', 'report') if k in self.data}
        if 'settings.json' in self.files:
            out['config'] = self._call('config', {})
        return out


def grade(text, check, state):
    # Only exact JSON answer fields are accepted; no extracting arbitrary numbers.
    parsed = None
    for match in re.finditer(r'\{', text or ''):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[match.start():])
            if isinstance(obj, dict) and 'answer' in obj:
                parsed = obj
        except ValueError:
            pass
    answer = None if parsed is None else parsed['answer']
    expected = check['answer']
    answer_ok = isinstance(answer, (int, float)) and abs(answer - expected) <= max(1e-6, abs(expected) * 1e-5) if isinstance(expected, (int, float)) else answer == expected
    state_ok = True
    for k, v in check.get('state', {}).items():
        if k == 'tested_contains':
            state_ok &= v in state.get('tested', [])
        elif k == 'report':
            # render_report saves a specification, not preformatted text: raw numeric
            # values are valid if formatting with the specified precision is correct.
            actual = state.get(k, {})
            state_ok &= all(actual.get(field) == v[field] for field in ('language', 'layout', 'decimals'))
            try:
                state_ok &= round(actual['value'], v['decimals']) == v['value']
            except (KeyError, TypeError):
                state_ok = False
        else:
            state_ok &= state.get(k) == v
    return {'answer': answer, 'expected': expected, 'answer_ok': bool(answer_ok), 'state_ok': bool(state_ok), 'success': bool(answer_ok and state_ok)}
