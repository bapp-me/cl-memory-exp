"""Record immutable source evidence and static boundaries, without importing agents."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
REVISION = 'c8301ea6c9b797184df16a9c5dd462400b264ff4'
LEGACY_REVISION = '07ab19b0a399f33bd760852e0b0588d07efe8c22'

# Bounded evidence set. Other transitive modules exist; this is not a whole-repo audit.
UPSTREAM = {
    'run_agent.py': ['AIAgent', '_spawn_background_review', '_spawn_background_review_now'],
    'agent/agent_init.py': ['_init_memory', '_init_session_state', 'initialize_agent'],
    'agent/system_prompt.py': ['build_system_prompt_parts'],
    'agent/prompt_builder.py': ['build_skills_system_prompt'],
    'agent/turn_context.py': ['_tick_memory_nudge'],
    'agent/turn_iteration_prep.py': ['prepare_iteration'],
    'agent/turn_finalizer.py': [],
    'agent/background_review.py': ['build_cache_parity_fork', '_fork_init_kwargs', '_review_tool_whitelist', '_record_review_usage_to_parent'],
    'agent/review_idle_queue.py': ['ReviewIdleQueue', 'review_targets_managed_local'],
    'agent/context_compressor.py': ['ContextCompressor'],
    'agent/conversation_compression.py': [],
    'agent/memory_manager.py': ['MemoryManager'],
    'agent/memory_provider.py': ['MemoryProvider'],
    'agent/api_request_hooks.py': ['ApiRequestHooksMixin'],
    'agent/auxiliary_hooks.py': ['_AuxCallHooks'],
    'agent/aux_accounting.py': [],
    'agent/curator.py': ['maybe_run_curator'],
    'hermes_cli/cli_tui_runtime_mixin.py': [],
    'hermes_cli/config_defaults.py': [],
    'hermes_cli/plugins.py': [],
    'hermes_cli/auth_zai_kimi.py': [],
    'hermes_cli/profiles.py': [],
    'hermes_state.py': ['SessionDB'],
    'hermes_state_schema.py': [],
    'tools/memory_tool.py': ['memory_tool', '_background_delete_gate'],
    'tools/memory_tool_store.py': ['MemoryStore'],
    'tools/session_search_tool.py': ['session_search', '_resolve_profile_db', '_read_session'],
    'tools/skills_tool.py': ['skills_list', 'skill_view'],
    'tools/skill_manager_tool.py': ['skill_manage'],
    'tools/skill_provenance.py': [],
    'tools/skill_ledger.py': ['ledger_path', 'blobs_dir'],
    'agent/skill_utils.py': ['get_project_skills_dirs', 'get_external_skills_dirs'],
    'agent/skill_preprocessing.py': [],
    'tools/write_approval.py': ['evaluate_gate', 'stage_write'],
    'tools/registry.py': ['register'],
    'toolsets.py': [],
    'LICENSE': [], 'pyproject.toml': [], '.python-version': [], 'package.json': [], 'uv.lock': [],
    'tests/agent/test_background_review_toolset_restriction.py': [],
    'tests/agent/test_background_review_usage.py': [],
    'tests/tools/test_session_search.py': [],
    'tests/tools/test_write_approval.py': [],
}
LOCAL = [
    'experiments/memory_direction_20261002/run_hermes_task.py',
    'experiments/memory_direction_20261002/api_proxy.py',
    'experiments/memory_direction_20261002/native_archive_files.py',
    'experiments/memory_scope_fix_20261002/pi-package-lock.json',
    'experiments/section7_observability_20261002/engine.py',
    'experiments/section7_observability_20261002/broker.py',
    'experiments/section7_observability_20261002/pi_runner_v2.mjs',
    'experiments/section7_observability_20261002/recorder_v2.mjs',
    'experiments/section7_observability_20261002/aux_client.py',
    'experiments/section7_observability_20261002/records/confirmed-config-v1.json',
    'experiments/section7_observability_20261002/records/baseline-adaptations.json',
    'experiments/agent_memory_plan_20261002/records/scorer-issues.json',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True, encoding='utf-8').strip()


def record(path):
    return {'sha256': sha(path), 'bytes': path.stat().st_size,
            'lines': len(path.read_text(encoding='utf-8-sig').splitlines())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, default=ROOT / '.cache/hermes-source')
    ap.add_argument('--legacy-source', type=Path)
    args = ap.parse_args()
    source = args.source.resolve()
    assert git(source, 'rev-parse', 'HEAD') == REVISION
    assert not git(source, 'status', '--porcelain'), 'Upstream source modified'
    if args.legacy_source:
        assert git(args.legacy_source, 'rev-parse', 'HEAD') == LEGACY_REVISION
        assert not git(args.legacy_source, 'status', '--porcelain')
    rows = []
    for relative, names in UPSTREAM.items():
        path = source / relative
        row = {'path': relative, **record(path),
               'url': f'https://github.com/NousResearch/hermes-agent/blob/{REVISION}/{relative}'}
        if args.legacy_source and (old := args.legacy_source / relative).exists():
            row['legacy_sha256'] = sha(old)
            row['changed_since_legacy'] = sha(old) != row['sha256']
        if path.suffix == '.py':
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            row['symbols'] = [{'name': node.name, 'start': node.lineno, 'end': node.end_lineno}
                              for node in ast.walk(tree)
                              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names]
            row['direct_local_import_modules'] = sorted({node.module for node in ast.walk(tree)
                  if isinstance(node, ast.ImportFrom) and node.module and
                  ((source / (node.module.replace('.', '/') + '.py')).exists() or
                   (source / node.module.replace('.', '/') / '__init__.py').exists())})
        rows.append(row)
    bg = ast.parse((source / 'agent/background_review.py').read_text(encoding='utf-8'))
    interfaces = {}
    for node in bg.body:
        if isinstance(node, ast.FunctionDef) and node.name in {'build_cache_parity_fork', '_fork_init_kwargs'}:
            attrs = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
                     and isinstance(n.value, ast.Name) and n.value.id == 'agent'}
            attrs |= {n.args[1].value for n in ast.walk(node) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Name) and n.func.id == 'getattr'
                      and len(n.args) >= 2 and isinstance(n.args[0], ast.Name) and n.args[0].id == 'agent'
                      and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)}
            interfaces[node.name] = {'direct_parent_attributes': sorted(attrs), 'count': len(attrs)}
    pi = REPO / 'experiments/memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-agent-core'
    pi_package = json.loads((pi / 'package.json').read_text(encoding='utf-8'))
    pi_declarations = (pi / 'dist/agent.d.ts').read_text(encoding='utf-8')
    pi_hooks = ['transformContext', 'prepareRequest', 'beforeToolCall', 'afterToolCall',
                'finishTurn', 'prepareNextTurn', 'subscribe', 'waitForIdle']
    assert all(hook in pi_declarations for hook in pi_hooks)
    lock = json.loads((REPO / 'experiments/memory_scope_fix_20261002/pi-package-lock.json').read_text(encoding='utf-8'))
    project = tomllib.loads((source / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    result = {
        'schema': 's0-source-audit-v1', 'client_date': '2026-10-03', 'timezone': 'Asia/Hong_Kong',
        'repo_base_commit': git(REPO, 'rev-parse', 'HEAD'),
        'hermes': {'revision': REVISION, 'legacy_revision': LEGACY_REVISION, 'license': project['license'],
                   'upstream_commit_date': git(source, 'show', '-s', '--format=%cI'),
                   'declared_python': project['requires-python'],
                   'python_version_file': (source / '.python-version').read_text().strip(),
                   'declared_node': json.loads((source / 'package.json').read_text())['engines']['node'],
                   'dependencies': project['dependencies'], 'optional_dependency_groups': sorted(project.get('optional-dependencies', {})),
                   'working_tree_clean': True},
        'pi': {'name': pi_package['name'], 'version': pi_package['version'], 'license': pi_package['license'],
               'verified_interface_hooks': pi_hooks,
               'node': pi_package['engines']['node'], 'evaluated_version': 'installed and locked 1.0.0; not latest main',
               'upstream_head_observed_readonly': 'a276dabe57911253350bffb93cb7d7aff6a73261',
               'package_lock_entries': {k: v for k, v in lock['packages'].items() if '@earendil-works/' in k},
               'files': [{'path': 'dist/' + f, **record(pi / 'dist' / f)} for f in ['agent.js', 'agent.d.ts', 'agent-loop.js', 'types.d.ts']]},
        'source_files': rows, 'review_fork_coupling': interfaces,
        'existing_assets': [{'path': p, **record(REPO / p)} for p in LOCAL],
        'model_calls': 0, 'limitations': 'Bounded source audit; imports and references are not dynamic behavior or full dependency closure.',
    }
    target = ROOT / 'records/source-audit.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'files': len(rows), 'legacy_changed': sum(r.get('changed_since_legacy', False) for r in rows),
                      'coupling': interfaces, 'hermes': result['hermes']['revision']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
