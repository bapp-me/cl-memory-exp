"""Six independent streams, each internally sequential; no replicate reruns."""
import concurrent.futures
import subprocess
import sys
from core import ROOT

def job(benchmark,method):
    name=f'pilot-{benchmark}-glm-{method}'
    out=ROOT/'runs'/name;out.mkdir(parents=True,exist_ok=True)
    with (out/'controller.log').open('a',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,str(ROOT/'run_stream.py'),'--provider','glm','--benchmark',benchmark,'--phase','pilot','--method',method,'--run-id',name],stdout=log,stderr=subprocess.STDOUT)
    print(f'{name}: exit {result.returncode}',flush=True)
    return result.returncode

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(job,b,m) for b in ['database','codeeval'] for m in ['no_memory','bounded_icl','episodic_retrieval']]
        codes=[f.result() for f in futures]
    raise SystemExit(0 if all(x==0 for x in codes) else 1)
