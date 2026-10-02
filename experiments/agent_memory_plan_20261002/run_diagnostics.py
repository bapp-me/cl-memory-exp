"""Run two independent benchmark diagnostic batches after complete pilot."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
from core import ROOT

def job(benchmark):
    name=f'diagnostic-{benchmark}-glm'
    folder=ROOT/'runs'/name;folder.mkdir(parents=True,exist_ok=True)
    with (folder/'controller.log').open('a',encoding='utf-8') as log:
        p=subprocess.run([sys.executable,str(ROOT/'diagnostic_fragments.py'),'--provider','glm','--benchmark',benchmark],stdout=log,stderr=subprocess.STDOUT)
    print(f'{name}: exit {p.returncode}',flush=True)
    return p.returncode

if __name__=='__main__':
    for b,total in [('database',40),('codeeval',24)]:
        for method in ['no_memory','bounded_icl','episodic_retrieval']:
            rows=json.loads((ROOT/'runs'/f'pilot-{b}-glm-{method}'/'summary.json').read_text(encoding='utf-8'))
            assert len(rows)==total
    frozen=json.loads((ROOT/'records/diagnostic-freeze-v2.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((ROOT/'diagnostic_fragments.py').read_bytes()).hexdigest()==frozen['selector_sha256']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        codes=list(pool.map(job,['database','codeeval']))
    raise SystemExit(0 if all(c==0 for c in codes) else 1)
