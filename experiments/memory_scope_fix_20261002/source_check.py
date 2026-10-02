"""Record reproducibility and optional official-source snapshots. Never reads credentials."""
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'memory_direction_20261002'


def main():
    sources = {
        'pi-agent-loop.ts': 'https://raw.githubusercontent.com/earendil-works/pi/a13d35a742c6ef8462812a28fbe1d8c8b7431c32/packages/agent/src/agent-loop.ts',
        'deepseek-pricing.html': 'https://api-docs.deepseek.com/quick_start/pricing',
        'deepseek-thinking.html': 'https://api-docs.deepseek.com/guides/thinking_mode',
        'deepseek-anthropic.html': 'https://api-docs.deepseek.com/guides/anthropic_api',
    }
    cache = ROOT / '.cache/sources'
    cache.mkdir(parents=True, exist_ok=True)
    records = []
    for name, url in sources.items():
        row = {'url': url, 'file': str((cache / name).relative_to(ROOT))}
        try:
            data = urlopen(Request(url, headers={'User-Agent': 'memory-scope-research/1.0'}), timeout=30).read()
            (cache / name).write_bytes(data)
            row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        except Exception as exc:
            row['error'] = str(exc)
        records.append(row)
    pi = ROOT / '.runtime/pi/node_modules/@earendil-works/pi-agent-core'
    files = {str(p.relative_to(pi)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (pi / 'dist').rglob('*.js')}
    manifest = {'python_controller': platform.python_version(), 'node': subprocess.check_output(['node', '--version'], text=True).strip(),
                'pi': {'package': '@earendil-works/pi-agent-core', 'version': '1.0.0', 'gitHead': 'a13d35a742c6ef8462812a28fbe1d8c8b7431c32', 'dist_file_sha256': files, 'lockfile': 'pi-package-lock.json', 'license': 'MIT'},
                'hermes': json.loads((OLD / 'installation-manifest.json').read_text())['hermes'], 'official_sources': records,
                'new_installs': 'pi agent-core and pi-ai only, 86 npm packages in local ignored .runtime; exact dependency tree in lockfile',
                'global_settings_changed': False}
    (ROOT / 'installation-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(records))


if __name__ == '__main__':
    main()
