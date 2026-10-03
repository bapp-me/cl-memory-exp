"""Read public source files at pinned commits; never install or run a provider."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def get(url):
    with urlopen(Request(url, headers={'User-Agent': 'memory-ecosystem-source-audit'}), timeout=45) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('repo')
    parser.add_argument('--paths', nargs='*', default=[])
    parser.add_argument('--discover', action='store_true')
    args = parser.parse_args()
    assert args.repo in ['mem0ai/mem0', 'plastic-labs/honcho', 'vectorize-io/hindsight', 'earendil-works/pi']
    folder = ROOT / '.cache' / args.repo.replace('/', '__')
    folder.mkdir(parents=True, exist_ok=True)
    meta_file = folder / 'source.json'
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
    else:
        revision = subprocess.check_output(['git', '-c', 'http.sslBackend=openssl', 'ls-remote',
                     f'https://github.com/{args.repo}.git', 'HEAD'], text=True).split()[0]
        meta = {'repo': args.repo, 'revision': revision, 'accessed': '2026-10-03', 'files': []}
    if args.discover:
        tree = json.loads(get(f'https://api.github.com/repos/{args.repo}/git/trees/{meta["revision"]}?recursive=1'))
        (folder / 'tree.json').write_text(json.dumps(tree), encoding='utf-8')
        names = [r['path'] for r in tree['tree'] if r['type'] == 'blob']
        selected = [p for p in names if ('pi-' in p or '/pi/' in p or '/pi.' in p or 'hermes' in p or
                                       'benchmark' in p.lower() or 'longmem' in p.lower())]
        print(json.dumps({'repo': args.repo, 'revision': meta['revision'], 'tree_truncated': tree.get('truncated'),
                          'candidate_paths': selected[:140]}, ensure_ascii=False))
    for name in args.paths:
        destination = (folder / name).resolve()
        assert destination.is_relative_to(folder.resolve())
        url = f'https://raw.githubusercontent.com/{args.repo}/{meta["revision"]}/{name}'
        try:
            body = get(url)
        except Exception as exc:
            print(json.dumps({'path': name, 'error': str(exc)}))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        row = {'path': name, 'url': url, 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
        meta['files'] = [r for r in meta['files'] if r['path'] != name] + [row]
        print(json.dumps({'repo': args.repo, 'file': name, 'bytes': len(body)}))
    meta_file.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
