"""Hash-verified published SQLite assets; no answers or raw data in public logs."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
from urllib.request import urlopen
from prepare import ROOT, UPSTREAM, fetch, read, save, sha


def main():
    record_path = ROOT / 'records/database-assets.json'
    if record_path.exists():
        lock = read(record_path)
    else:
        repo = 'continual-learning-bench/database-exploration'
        revision = fetch('https://huggingface.co/api/datasets/' + repo)['sha']
        tree = fetch(f'https://huggingface.co/api/datasets/{repo}/tree/{revision}')
        lock = {'repository': repo, 'revision': revision, 'assets': [
            {'name': x['path'], 'bytes': x['size'], 'sha256': x['lfs']['oid']}
            for x in tree if x['path'] in {'products.db', 'products_drifted.db'}]}
        save(record_path, lock)
    def obtain(item):
        destination = UPSTREAM / 'data/database_exploration' / item['name']
        if destination.exists() and sha(destination) == item['sha256']:
            return {**item, 'verified': True}
        old = Path('D:/campus_re/experiments/memory_direction_20261002/.cache/clbench') / item['name']
        temp = destination.with_suffix('.download')
        if old.exists() and sha(old) == item['sha256']:
            shutil.copyfile(old, temp)
        else:
            url = f'https://huggingface.co/datasets/{lock["repository"]}/resolve/{lock["revision"]}/{item["name"]}'
            with urlopen(url, timeout=60) as response, temp.open('wb') as stream:
                shutil.copyfileobj(response, stream, 4 * 1024 * 1024)
        if sha(temp) != item['sha256']:
            raise RuntimeError('Published database asset hash mismatch')
        temp.replace(destination)
        return {**item, 'verified': True}
    with ThreadPoolExecutor(max_workers=2) as pool:
        lock['assets'] = list(pool.map(obtain, lock['assets']))
    save(record_path, lock)
    print({'assets_verified': len(lock['assets']), 'model_calls': 0})


if __name__ == '__main__': main()
