"""Section 7.0.1 inventory. Pure offline code; never imports a model runner."""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LEGACY = REPO / 'experiments/agent_memory_plan_20261002'
RUNS = {
    'full-codeeval-glm-no_memory': ('no_memory', 'codeeval', 96),
    'full-codeeval-glm-episodic_retrieval': ('episodic_retrieval', 'codeeval', 96),
    'noncode-babyai-glm-no_memory': ('no_memory', 'babyai', 8),
    'noncode-babyai-glm-episodic_retrieval': ('episodic_retrieval', 'babyai', 8),
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def relative(path):
    return path.relative_to(REPO).as_posix()


def frozen_helpers():
    source = LEGACY / 'core.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in {'digest', 'memory_context'}]
    assert len(nodes) == 2
    namespace = {'json': json, 'hashlib': hashlib, 're': re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['digest'], namespace['memory_context']


def prompt_from(result):
    user = next(m for m in result['messages'] if m['role'] == 'user')
    content = user['content']
    return content if isinstance(content, str) else ''.join(c.get('text', '') for c in content)


def main():
    digest, select = frozen_helpers()
    archive_record = read(LEGACY / 'records/raw-archive.json')
    archive = LEGACY / archive_record['path'].replace('\\', '/')
    with archive.open('rb') as stream:
        archive_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    with tarfile.open(archive, 'r:gz') as stream:
        archive_members = len(stream.getmembers())
    errors = []
    if archive_hash != archive_record['sha256'] or archive_members != archive_record['files']:
        errors.append({'archive': 'Digest or member-count mismatch'})
    rows = []
    stats = defaultdict(Counter)
    for run_id, (method, benchmark, expected) in RUNS.items():
        run = LEGACY / 'runs' / run_id
        folders = sorted(p for p in run.iterdir() if p.is_dir() and p.name.isdecimal())
        if len(folders) != expected:
            errors.append({'run_id': run_id, 'expected_tasks': expected, 'actual_tasks': len(folders)})
        previous = None
        for folder in folders:
            fields = {}
            parsed = {}
            files = []
            checks = {}

            def field(name, status, paths=(), reason=None):
                fields[name] = {'status': status, 'sources': [relative(p) for p in paths], 'reason': reason}
                stats[name][status] += 1

            def load(name, required=True):
                path = folder / name
                value = parsed.get(name)
                if value is None and required:
                    errors.append({'run_id': run_id, 'task': folder.name, 'file': name, 'error': 'Missing or invalid'})
                return value

            # Inventory nested retry evidence too; preserve missing/invalid separately.
            for path in sorted(folder.rglob('*')):
                if not path.is_file():
                    continue
                item = {'path': relative(path), 'bytes': path.stat().st_size, 'parseable': None}
                if path.suffix in {'.json', '.jsonl'}:
                    try:
                        value = (read(path) if path.suffix == '.json' else
                                 [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()])
                        item['parseable'] = True
                        if path.parent == folder:
                            parsed[path.name] = value
                    except (ValueError, UnicodeError) as exc:
                        item.update(parseable=False, error=str(exc))
                        errors.append({'run_id': run_id, 'task': folder.name, 'file': relative(path), 'error': str(exc)})
                files.append(item)
            for name in ['execution.json', 'pi-result.json', 'events.jsonl', 'requests.jsonl',
                         'transport.jsonl', 'memory-before.json', 'injected.json', 'memory-after.json', 'commit.json']:
                field(name, 'present' if name in parsed else 'unavailable',
                      [folder / name] if name in parsed else [], 'Parsed persisted file' if name in parsed else 'Missing or invalid')
                load(name)
            execution = load('execution.json')
            result = load('pi-result.json')
            commit = load('commit.json')
            before = load('memory-before.json')
            after = load('memory-after.json')
            injected = load('injected.json')
            if any(x is None for x in [execution, result, commit, before, after, injected]):
                rows.append({'run_id': run_id, 'task_directory': relative(folder), 'fields': fields, 'files': files, 'checks': checks})
                continue
            task_id = commit['result'].get('task_id')
            field('run_task_attempt_identity', 'reconstructable', [folder / 'commit.json'],
                  'Run/path identity and task ID exist; original explicit attempt_id is absent')
            field('terminal_state', 'present', [folder / 'execution.json', folder / 'commit.json'])
            score_available = all(k in commit['result'] for k in ['correct', 'scorable'])
            field('external_score', 'present' if score_available else 'unavailable', [folder / 'commit.json'])
            field('actual_request_payload', 'unavailable', [folder / 'requests.jsonl'], 'Summary only; actual serialized input is not archived')
            field('request_http_attempt_mapping', 'unavailable', [folder / 'requests.jsonl', folder / 'transport.jsonl'], 'No shared call/attempt ID')
            field('complete_generation_latency', 'unavailable', [folder / 'transport.jsonl'], 'Transport duration ends at response headers, not streaming completion')
            field('auxiliary_role_calls', 'not_applicable', reason='These frozen simple methods have no model writer, reflector, curator or embedding')
            field('readonly_state_hash', 'not_applicable', reason='First-pass online streams only; readonly fixtures are a later acceptance step')
            assistants = [m for m in result['messages'] if m['role'] == 'assistant']
            usage_fields = ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens']
            usage_complete = bool(assistants) and all(isinstance(m.get('usage'), dict) and
                                all(k in m['usage'] for k in usage_fields) for m in assistants)
            usage_sum = ({k: sum(m['usage'][k] for m in assistants) for k in usage_fields} if usage_complete else None)
            checks['message_usage_matches_execution'] = (usage_sum == execution['usage'] if usage_sum is not None else None)
            field('returned_message_usage', 'present' if usage_complete else 'unavailable', [folder / 'pi-result.json'],
                  'Only covers usage objects retained by Pi; raw provider/failed-HTTP usage is not proven')
            field('failed_http_usage_and_monetary_cost', 'unavailable', [folder / 'transport.jsonl'], 'No per-attempt usage or verified price manifest; unknown is not zero cost')
            checks['before_hash'] = digest(before) == commit['before_hash'] == execution['memory_hash']
            checks['after_hash'] = digest(after) == commit['after_hash']
            checks['injected_hash'] = digest(injected) == execution['injected_hash']
            checks['state_chain'] = previous is None or digest(before) == previous
            checks['injected_only_from_before'] = all(e in before for e in injected)
            previous = digest(after)
            prompt = prompt_from(result)
            query = set(re.findall(r'\w+', prompt.lower()))
            ranked = []
            if method == 'episodic_retrieval':
                for index, episode in enumerate(before):
                    words = set(re.findall(r'\w+', episode['text'].lower()))
                    ranked.append((len(query & words) / (len(query | words) or 1), index))
                ranked.sort(reverse=True)
                picked = sorted([i for _, i in ranked[:3]], key=lambda i: before[i]['sequence'])
            else:
                picked = []
            packed = list(picked)
            dropped = []
            while packed and len(json.dumps([before[i] for i in packed], ensure_ascii=False).encode()) > 48000:
                dropped.append(packed.pop(0))
            checks['frozen_selection_reproduced'] = digest(select(before, method, prompt)) == digest(injected)
            checks['candidate_reconstruction_matches'] = digest([before[i] for i in packed]) == digest(injected)
            field('retrieval_candidates_and_packing', 'reconstructable' if checks['candidate_reconstruction_matches'] else 'unavailable',
                  [LEGACY / 'core.py', folder / 'memory-before.json', folder / 'pi-result.json', folder / 'injected.json'],
                  'Reconstruction checked against archived injection; no new model request')
            if method == 'no_memory':
                checks['empty_history_channels'] = before == after == injected == []
            else:
                checks['single_episode_append'] = after[:-1] == before and len(after) == len(before) + 1
                checks['episode_top_level_schema'] = set(json.loads(after[-1]['text'])) == {'task', 'trajectory'} if after else False
            field('write_state_change', 'reconstructable', [folder / 'memory-before.json', folder / 'memory-after.json', folder / 'commit.json'])
            if benchmark == 'codeeval':
                status = load('submission-status.json')
                field('submission_audit', 'present' if status is not None else 'unavailable', [folder / 'submission-status.json'])
                artifact = folder / 'submission.py'
                if execution['submitted']:
                    field('submitted_artifact', 'present' if artifact.exists() else 'unavailable', [artifact] if artifact.exists() else [])
                    checks['submitted_artifact_hash'] = bool(status and artifact.exists() and
                        hashlib.sha256(artifact.read_bytes()).hexdigest() == status.get('sha256'))
                else:
                    field('submitted_artifact', 'not_applicable', [folder / 'submission-status.json'], 'Agent did not submit')
                checks['submission_status_matches'] = bool(status is not None and status['submitted'] == execution['submitted'])
                field('evaluator_log', 'present' if 'evaluator.json' in parsed else 'not_applicable' if not commit['result']['scorable'] else 'unavailable',
                      [folder / 'evaluator.json'] if 'evaluator.json' in parsed else [], 'External score remains in commit.json')
            else:
                field('submission_audit', 'reconstructable', [folder / 'pi-result.json', folder / 'commit.json'],
                      'Native terminal observation and external done/progress/action count; no standalone submission audit file')
                field('submitted_artifact', 'not_applicable', reason='Navigation task has no code/file submission')
                field('evaluator_log', 'not_applicable', reason='Native done/progress scoring is persisted in commit.result')
            for name, passed in checks.items():
                if passed is False:
                    errors.append({'run_id': run_id, 'task_id': task_id, 'check': name})
            rows.append({'run_id': run_id, 'task_id': task_id, 'task_directory': relative(folder),
                         'method': method, 'fields': fields, 'files': files, 'checks': checks,
                         'reconstructed_retrieval': {'candidates': [{'history_index': i, 'score': s, 'rank': rank + 1}
                                                   for rank, (s, i) in enumerate(ranked)],
                                                   'selected_indices': picked, 'budget_dropped_indices': dropped,
                                                   'injected_indices': packed, 'injected_hash': digest(injected)},
                         'retained_message_usage': usage_sum})
    report = {
        'inventory_version': 'section7.0.1-v1', 'model_calls': 0, 'tasks_checked': len(rows),
        'scope': 'Four legacy first-pass flows proposed for descriptive reuse; not new-recorder acceptance',
        'archive': {'path': relative(archive), 'expected_sha256': archive_record['sha256'],
                    'actual_sha256': archive_hash, 'members': archive_members},
        'frozen_core_sha256': hashlib.sha256((LEGACY / 'core.py').read_bytes()).hexdigest(),
        'availability_counts': {k: dict(v) for k, v in sorted(stats.items())},
        'integrity_errors': errors, 'integrity_passed': not errors,
        'reuse_decision': 'Provisional descriptive evidence only; payload-level equivalence and new recorder acceptance remain unproven',
        'limitations': ['Does not prove provider-side state isolation or absence of all semantic answer leakage.',
                       'Returned Pi usage objects are not a verified provider invoice or a complete failed-request ledger.',
                       'Integrity success does not satisfy all section 7.0 release criteria.'],
        'tasks': rows,
    }
    path = ROOT / 'records/legacy-availability.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['model_calls', 'tasks_checked', 'integrity_passed', 'integrity_errors', 'availability_counts']}))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
