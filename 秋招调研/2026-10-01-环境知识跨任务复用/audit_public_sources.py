"""Read-only public-source inventory. No model calls or environment installation.

Run with Python 3.11+. Downloads only public metadata and explicitly selected files.
Raw material stays in ignored .cache; the audit records URLs, revisions and SHA256.
Re-running resolves current HEAD, so preserve the committed audit for this snapshot.
"""
import concurrent.futures
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache'
REPOS = [
    'xiaowu0162/LongMemEval-V2', 'StonyBrookNLP/appworld',
    'TheAgentCompany/TheAgentCompany', 'KnowledgeXLab/MUSE',
    'ServiceNow/WorkArena', 'eth-sri/agentbench',
    'Mercor-Intelligence/archipelago', 'import-myself/DeltaMem',
    'caixd-220529/LifelongAgentBench', 'ZexueHe/MemoryArena',
    'web-arena-x/webarena',
]
DATASETS = [
    'xiaowu0162/longmemeval-v2', 'mercor/apex-agents',
    'mercor/apex-agents-v1.1', 'ServiceNow/WorkArena-Instances',
    'eth-sri/agentbench',
]


def get(url):
    req = Request(url, headers={'User-Agent': 'environment-memory-research/1.0'})
    with urlopen(req, timeout=40) as response:
        return response.read()


def cached(url, name):
    data = get(url)
    path = CACHE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, {'url': url, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def repo_info(repo):
    head = json.loads(get(f'https://api.github.com/repos/{repo}/commits/HEAD'))
    sha = head['sha']
    raw, tree_record = cached(f'https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1', repo + '/tree.json')
    tree = json.loads(raw)
    paths = [x['path'] for x in tree['tree'] if x['type'] == 'blob']
    files = []
    for path in paths:
        if path.lower() in ('readme.md', 'license', 'license.md', 'pyproject.toml'):
            _, record = cached(f'https://raw.githubusercontent.com/{repo}/{sha}/{path}', repo + '/' + path)
            files.append(record)
    return {'repo': repo, 'commit': sha, 'commit_date': head['commit']['committer']['date'],
            'tree_truncated': tree.get('truncated'), 'file_count': len(paths),
            'tree': tree_record, 'files': files}


def dataset_info(repo):
    raw, record = cached(f'https://huggingface.co/api/datasets/{repo}', 'hf/' + repo + '/metadata.json')
    data = json.loads(raw)
    return {'repo': repo, 'revision': data.get('sha'), 'gated': data.get('gated'),
            'private': data.get('private'), 'license': data.get('cardData', {}).get('license'),
            'file_count': len(data.get('siblings', [])),
            'file_samples': [x['rfilename'] for x in data.get('siblings', [])[:10]], 'metadata': record}


def main():
    CACHE.mkdir(exist_ok=True)
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'model_calls': 0,
              'environment_runs': 0, 'repositories': [], 'datasets': [], 'errors': []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        jobs = {pool.submit(repo_info, x): ('repositories', x) for x in REPOS}
        jobs.update({pool.submit(dataset_info, x): ('datasets', x) for x in DATASETS})
        for future in concurrent.futures.as_completed(jobs):
            kind, name = jobs[future]
            try:
                item = future.result()
                result[kind].append(item)
                print(name, item.get('commit', item.get('revision')), flush=True)
            except Exception as exc:
                result['errors'].append({'source': name, 'error': str(exc)})
                print(name, type(exc).__name__, str(exc), flush=True)
    for kind in ('repositories', 'datasets'):
        result[kind].sort(key=lambda x: x['repo'])
    (ROOT / '公开来源核查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
