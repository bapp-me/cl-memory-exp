"""Freeze public SQLite data, recompute gold, and test unit counterfactuals."""
from __future__ import annotations
import hashlib
import json
import shutil
import sqlite3
import time
from urllib.request import Request, urlopen
from lab_common import ROOT, save_json

PIN = '5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26'
REPO = 'continual-learning-bench/database-exploration'
CACHE = ROOT / '.cache/clbench'


def fetch_json(url):
    with urlopen(Request(url, headers={'User-Agent': 'memory-direction-pilot/1.0'}), timeout=40) as r:
        return json.load(r)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = fetch_json('https://huggingface.co/api/datasets/' + REPO)
    revision = meta['sha']
    tree = fetch_json(f'https://huggingface.co/api/datasets/{REPO}/tree/{revision}')
    item = next(x for x in tree if x.get('path') == 'products.db')
    expected = item['lfs']['oid']
    path = CACHE / 'products.db'
    url = f'https://huggingface.co/datasets/{REPO}/resolve/{revision}/products.db'
    if not path.exists():
        if shutil.disk_usage(CACHE).free < item['size'] * 2:
            raise RuntimeError('Not enough disk space for bounded download')
        temp = path.with_suffix('.db.part')
        started = time.monotonic()
        with urlopen(url, timeout=60) as response, temp.open('wb') as out:
            total = 0
            while chunk := response.read(4 * 1024 * 1024):
                out.write(chunk)
                total += len(chunk)
                if total % (32 * 1024 * 1024) == 0:
                    print(json.dumps({'downloaded_mib': total // 1048576, 'seconds': round(time.monotonic()-started,1)}), flush=True)
        temp.replace(path)
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    assert digest == expected, 'Downloaded SQLite hash differs from pinned LFS hash'
    question_url = f'https://raw.githubusercontent.com/pgasawa/continual-learning-bench/{PIN}/data/database_exploration/questions.json'
    questions = fetch_json(question_url)
    save_json(CACHE / 'questions.json', questions)
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    con.execute('PRAGMA query_only=ON')
    gold = []
    for q in questions:
        start = time.monotonic()
        value = con.execute(q['sql']).fetchone()[0]
        gold.append({'question_id': q['question_id'], 'published_answer': q['answer'],
                     'recomputed_answer': value, 'exact_match': value == q['answer'],
                     'seconds': round(time.monotonic()-start,3)})
    by_id = {q['question_id']:q for q in questions}
    cf_sql = by_id[2]['sql'].replace('i.prc > 50', 'i.prc > 5000')
    cf = con.execute(cf_sql).fetchone()[0]
    # Independently rearranged computations for the selected source and targets.
    independent = {
        2: "SELECT ROUND(SUM(f.rtg)*1.0/COUNT(f.rtg),2) FROM fdbk_g1 f WHERE f.ref_id IN (SELECT ref_id FROM items_g1 WHERE prc>50)",
        11: "SELECT ROUND(100.0*SUM(CASE WHEN rtg=1 THEN 1 ELSE 0 END)/COUNT(*),2) FROM fdbk_g2 WHERE LENGTH(body)>500 AND ref_id IN (SELECT ref_id FROM items_g2 WHERE prc>0 AND prc<=4000)",
        12: "SELECT COUNT(*) FROM (SELECT ref_id FROM fdbk_g2 WHERE ref_id IN (SELECT ref_id FROM items_g2 WHERE prc>5000) GROUP BY ref_id HAVING COUNT(*)>=5 AND SUM(rtg)*1.0/COUNT(rtg)<3)",
    }
    cross = [{'question_id': k, 'sql': sql, 'value': con.execute(sql).fetchone()[0]} for k,sql in independent.items()]
    schema = con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    record = {'data_repo':REPO, 'revision':revision, 'download_url':url, 'bytes':path.stat().st_size,
              'sha256':digest, 'task_source_commit':PIN, 'question_url':question_url,
              'gold_checks':gold, 'selected_independent_checks':cross,
              'q2_wrong_unit_sql':cf_sql, 'q2_wrong_unit_value':cf,
              'schema':schema, 'model_calls':0,
              'limits':['Gold recomputation checks data consistency, not all question semantics.',
                        'A wrong-unit SQL result is a counterfactual diagnostic, not an observed model failure.']}
    save_json(ROOT / 'results/clbench-data-audit.json', record)
    print(json.dumps({'sha256':digest, 'gold_matches':sum(x['exact_match'] for x in gold),
                      'gold_count':len(gold), 'independent_checks':cross, 'q2_wrong_unit_value':cf},ensure_ascii=True),flush=True)


if __name__ == '__main__':
    main()
