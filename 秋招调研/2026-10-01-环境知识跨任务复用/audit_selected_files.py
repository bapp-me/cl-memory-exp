"""Inspect selected public files at revisions frozen in the inventory.

This does not run agents, benchmark code, or model endpoints. All downloads are
read-only; gated HF resources are probed anonymously without accepting terms.
"""
import concurrent.futures
import json
from urllib.parse import quote
from audit_public_sources import ROOT, cached

SELECTED = {
    'web-arena-x/webarena': ['config_files/test.raw.json', 'evaluation_harness/evaluators.py', 'environment_docker/README.md', 'resources/README.md'],
    'xiaowu0162/LongMemEval-V2': [
        'memory_modules/codex.py', 'memory_modules/agentrunbook_c.py',
        'memory_modules/agentrunbook_online_learning.py',
        'memory_modules/assets/agentrunbook_online_learning/CONSOLIDATE_STRATEGY.md',
        'evaluation/qa_eval_metrics.py', 'tests/test_query_privacy.py'],
    'StonyBrookNLP/appworld': ['guides/evaluating_terminal_agents.md', 'src/appworld/serve/_mcp.py', 'src/appworld/environment.py'],
    'KnowledgeXLab/MUSE': ['memory/procedural_memory.json', 'memory/strategic_memory.json', 'memory/tool_memory.json', 'config.yaml', 'memory_manager.py'],
    'TheAgentCompany/TheAgentCompany': ['docs/EVALUATION.md', 'workspaces/base_image/reset.sh',
        'workspaces/tasks/pm-update-plane-issue-from-gitlab-status/task.md',
        'workspaces/tasks/pm-update-plane-issue-from-gitlab-status/evaluator.py',
        'workspaces/tasks/pm-update-plane-issue-from-gitlab-status/populate_data.py',
        'workspaces/tasks/pm-update-gitlab-issue-from-plane-status/task.md'],
    'eth-sri/agentbench': ['src/configs/generator_constants.py', 'src/configs/model_constants.py', 'final_scripts/README.md'],
}
HF_SELECTED = {
    'xiaowu0162/longmemeval-v2': ['README.md', 'DATA_CARD.md', 'SCHEMA.md', 'questions.jsonl', 'haystacks/lme_v2_small.json'],
    'mercor/apex-agents-v1.1': ['README.md', 'manifest.json', 'registry.json'],
}


def main():
    inventory = json.loads((ROOT / '公开来源核查.json').read_text(encoding='utf-8'))
    tasks = []
    for kind, selection in [('repositories', SELECTED), ('datasets', HF_SELECTED)]:
        by_name = {x['repo']: x for x in inventory[kind]}
        for repo, paths in selection.items():
            revision = by_name[repo].get('commit', by_name[repo].get('revision'))
            for path in paths:
                url = (f'https://raw.githubusercontent.com/{repo}/{revision}/' if kind == 'repositories'
                       else f'https://huggingface.co/datasets/{repo}/resolve/{revision}/') + quote(path)
                tasks.append((url, ('' if kind == 'repositories' else 'hf/') + repo + '/' + path))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        jobs = {pool.submit(cached, url, name): (url, name) for url, name in tasks}
        for future in concurrent.futures.as_completed(jobs):
            url, name = jobs[future]
            try:
                _, rec = future.result()
                rec['cache_path'] = name
                results.append(rec)
                print(name, rec['bytes'], flush=True)
            except Exception as exc:
                results.append({'url': url, 'error': str(exc)})
                print(name, type(exc).__name__, str(exc), flush=True)
    results.sort(key=lambda x: x['url'])
    (ROOT / '选定文件核查.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
