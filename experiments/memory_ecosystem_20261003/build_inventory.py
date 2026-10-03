"""Capture checked repository identities and hashes; no agent/model execution."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache'
CLONES = {
    'pi-hermes-memory': ('chandra447/pi-hermes-memory', ['README.md', 'package.json', 'src/index.ts', 'src/config.ts', 'src/constants.ts', 'src/handlers/background-review.ts', 'src/handlers/review-memory-ops.ts', 'src/handlers/session-flush.ts', 'tests/run-all.sh', 'scripts/benchmark-memory-startup.mjs']),
    'pi-hindsight': ('abix5/pi-hindsight', ['README.md', 'package.json', 'src/index.ts', 'src/model.ts', 'src/memorize.ts', 'src/hindsight.ts']),
    'pi-memctx': ('weauratech/pi-memctx', ['README.md', 'package.json', 'benchmark/README.md', 'benchmark/setup.sh', 'benchmark/run.sh']),
    'pi-memory-honcho': ('acsezen/pi-memory-honcho', ['README.md', 'package.json']),
    'pi-honcho-official-listed': ('agneym/pi-honcho-memory', ['README.md', 'package.json', 'extensions/index.ts', 'extensions/memory.ts', 'extensions/config.ts']),
}


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True, encoding='utf-8').strip()


def file_row(path, relative, url):
    return {'path': relative, 'url': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size, 'lines': len(path.read_text(encoding='utf-8-sig').splitlines())}


def main():
    repos = []
    for directory, (repo, names) in CLONES.items():
        folder = CACHE / directory
        revision = git(folder, 'rev-parse', 'HEAD')
        assert not git(folder, 'status', '--porcelain')
        pkg = json.loads((folder / 'package.json').read_text())
        repos.append({'repo': repo, 'cache_directory': directory, 'revision': revision,
                      'commit_date': git(folder, 'show', '-s', '--format=%cI'),
                      'package': pkg['name'], 'source_version': pkg['version'], 'license': pkg.get('license'),
                      'peerDependencies': pkg.get('peerDependencies', {}), 'dependencies': pkg.get('dependencies', {}),
                      'pi_manifest': pkg.get('pi'),
                      'files': [file_row(folder / p, p, f'https://github.com/{repo}/blob/{revision}/{p}') for p in names]})
    for path in sorted(CACHE.glob('*/source.json')):
        value = json.loads(path.read_text())
        for row in value['files']:
            assert row['sha256'] == hashlib.sha256((path.parent / row['path']).read_bytes()).hexdigest()
        repos.append(value)
    hermes = ROOT.parent / 'section7_s0_audit_20261003/.cache/hermes-source'
    rev = git(hermes, 'rev-parse', 'HEAD')
    names = ['agent/memory_provider.py', 'agent/memory_manager.py', 'plugins/memory/__init__.py',
             'plugins/memory/mem0/__init__.py', 'website/docs/user-guide/features/memory-providers.md']
    names += [f'plugins/memory/{p}/README.md' for p in ['mem0', 'holographic', 'openviking', 'byterover', 'retaindb']]
    repos.append({'repo': 'NousResearch/hermes-agent', 'revision': rev, 'source': 'prior audit checkout, unchanged',
                  'files': [file_row(hermes / p, p, f'https://github.com/NousResearch/hermes-agent/blob/{rev}/{p}') for p in names]})
    result = {'schema': 'memory-ecosystem-inventory-v1', 'access_date': '2026-10-03', 'timezone': 'Asia/Hong_Kong',
              'scope': 'Read-only public source and documentation research; no installation or execution of extensions',
              'model_calls': 0, 'packages_installed': 0, 'benchmarks_run': 0, 'repositories': repos,
              'source_files_captured': sum(len(r['files']) for r in repos),
              'limits': ['Source snapshot is not runtime compatibility validation', 'README/benchmark claims are not locally reproduced',
                         'Package version on branch and published npm metadata are tracked separately', 'No exhaustive ecosystem claim']}
    (ROOT / 'records/source-inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'repositories': len(repos), 'source_files': result['source_files_captured'], 'model_calls': 0}))


if __name__ == '__main__':
    main()
