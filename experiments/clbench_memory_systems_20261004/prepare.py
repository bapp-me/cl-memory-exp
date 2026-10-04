"""Resolve public upstreams and inventory the frozen contract; no model calls.

Private source/data stays in .local. This does not mark an arm READY.
"""
from __future__ import annotations

import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / '.local/upstream/clbench'
REPOS = {'codex': 'openai/codex', 'claude_code': 'anthropics/claude-code',
         'pi_coding_agent': 'earendil-works/pi', 'hermes': 'NousResearch/hermes-agent'}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temp.replace(path)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'clbench-memory-study/1.0'}), timeout=30) as response:
        return json.load(response)


def release(pair):
    name, repo = pair
    data = fetch(f'https://api.github.com/repos/{repo}/releases/latest')
    tag = data['tag_name']
    commit = fetch(f'https://api.github.com/repos/{repo}/commits/{tag}')['sha']
    return name, {'repository': repo, 'version': tag, 'commit': commit,
                  'published_at': data['published_at'], 'url': data['html_url']}


def main():
    revision = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != '5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26':
        raise RuntimeError('Upstream changed; review schedule and protocol before freezing')
    public_release_path = ROOT / 'records/upstream-lock.json'
    if public_release_path.exists():
        releases = read(public_release_path)['frameworks']
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            releases = dict(pool.map(release, REPOS.items()))
    files = ['pyproject.toml', 'uv.lock', 'src/interface.py', 'src/usage.py',
             'src/tasks/schedules.py', 'src/tasks/variants.py',
             'src/tasks/database_exploration/task.py', 'src/tasks/database_exploration/prompts.py',
             'src/tasks/database_exploration/schedules/default.json',
             'src/tasks/database_exploration/variants/schema_drift.json',
             'src/tasks/codebase_adaptation/task.py', 'src/tasks/codebase_adaptation/evaluator.py',
             'src/tasks/codebase_adaptation/generic_runtime.py',
             'src/tasks/codebase_adaptation/schedules/default.json',
             'src/tasks/codebase_adaptation/variants/tablib.json',
             'src/tasks/codebase_adaptation/variants/tenacity.json',
             'src/systems/icl_notepad/system.py', 'src/systems/icl_notepad/prompts.py',
             'src/systems/codex/system.py', 'src/systems/claude/system.py',
             'data/database_exploration/questions.json',
             'data/database_exploration/questions_post_drift.json',
             'data/codebase_adaptation/final-dataset.jsonl']
    hashes = {f: sha(UPSTREAM / f) for f in files if (UPSTREAM / f).is_file()}
    pre = read(UPSTREAM / 'data/database_exploration/questions.json')
    post = read(UPSTREAM / 'data/database_exploration/questions_post_drift.json')
    # Execute the unmodified, side-effect-free official order function only.
    source = ast.parse((UPSTREAM / 'src/tasks/database_exploration/task.py').read_text(encoding='utf-8'))
    node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == '_build_schema_drift_question_sequence')
    namespace = {'random': __import__('random'), 'Any': __import__('typing').Any}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<official-order>', 'exec'), namespace)
    questions = namespace[node.name](pre_questions=pre, post_questions=post, pre_drift_count=20,
                                     post_drift_count=20, seed=42, run_index=0)
    schedule = read(UPSTREAM / 'src/tasks/codebase_adaptation/schedules/default.json')
    code_ids = [i for stage in schedule['stages'] for i in stage['schedule']['instance_ids']]
    dataset = [json.loads(line) for line in (UPSTREAM / 'data/codebase_adaptation/final-dataset.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    by_id = {row['instance_id']: row for row in dataset}
    # Only public identifiers and base commits. Hidden labels/patches remain in .local.
    task_manifest = {
        'clbench_commit': revision, 'repetition': 1, 'official_run_index': 0,
        'database_exploration': [{'index': i, 'instance_id': str(q['question_id']),
                                 'stage': 'pre' if i < 20 else 'post'} for i, q in enumerate(questions)],
        'codebase_adaptation': [{'index': i, 'instance_id': key, 'project_key': by_id[key]['repo'],
                                 'base_commit': by_id[key]['base_commit']} for i, key in enumerate(code_ids)],
        'order_policy': 'official_database_seed42_run0_and_explicit_codebase_stage_ids',
        'order_note': 'one paired canonical stream, no outer runner permutation or extra repeats',
    }
    save(ROOT / 'records/task-manifest.json', task_manifest)
    record = {
        'resolved_at': datetime.now(timezone.utc).isoformat(), 'frameworks': releases,
        'clbench_commit': revision, 'source_hashes': hashes,
        'task_manifest_sha256': sha(ROOT / 'records/task-manifest.json'),
        'counts': {'database': len(questions), 'codebase': len(code_ids),
                   'codebase_projects': dict(Counter(by_id[i]['repo'] for i in code_ids))},
        'business_limits': {'database_queries_per_question': 15, 'database_response_timeout_seconds': 60,
                            'database_sql_timeout_seconds': 10, 'codebase_steps_per_issue': 40},
        'limits_note': 'Codebase checks >=40 before execution; preserve this exact upstream behavior.',
        'framework_global_model_attempt_limit': None, 'model_calls': 0,
        'acceptance': 'PENDING_RUNTIME_FIXTURES_AND_ONLINE_CANARIES',
    }
    save(public_release_path, record)
    print(json.dumps({'release_versions': {k: v['version'] for k, v in releases.items()},
                      'counts': record['counts'], 'model_calls': 0}))


if __name__ == '__main__':
    main()
