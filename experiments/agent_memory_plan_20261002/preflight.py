"""Read-only preflight: public metadata and local runtime, no model calls or secrets."""
from __future__ import annotations
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'agent-memory-plan-preflight'}), timeout=45) as r:
        return json.load(r)

def main():
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'model_calls': 0,
              'python': sys.version, 'executables': {n: shutil.which(n) for n in ['node', 'npm', 'docker', 'wsl', 'uv']},
              'sources': {}, 'errors': []}
    for name, url in {
        'agentcl': 'https://huggingface.co/api/datasets/osunlp/AgentCL',
        'clbench': 'https://api.github.com/repos/pgasawa/continual-learning-bench/commits/main',
        'pi': 'https://api.github.com/repos/earendil-works/pi/commits/main',
    }.items():
        try:
            data = fetch(url)
            report['sources'][name] = {'url': url, 'revision': data['sha']}
            if name == 'agentcl':
                report['sources'][name]['files'] = [f['rfilename'] for f in data.get('siblings', [])]
            if name == 'clbench':
                tree = fetch(f"https://api.github.com/repos/pgasawa/continual-learning-bench/git/trees/{data['sha']}?recursive=1")
                report['sources'][name]['database_exploration_files'] = [f['path'] for f in tree['tree'] if 'database_exploration' in f['path']]
        except Exception as e:
            report['errors'].append({'source': name, 'error': str(e)})
    pi = ROOT.parent / 'memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-agent-core'
    if pi.exists():
        package = json.loads((pi / 'package.json').read_text(encoding='utf-8'))
        report['local_pi'] = {'path': str(pi), 'version': package['version'],
                              'agent_js_sha256': hashlib.sha256((pi / 'dist/agent.js').read_bytes()).hexdigest()}
    report['credential_store_exists'] = (ROOT.parent / 'memory_direction_20261002/.private/credentials.json').is_file()
    out = ROOT / 'records/preflight.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))

if __name__ == '__main__':
    main()
