"""Four independent calibration streams; every stream remains sequential."""
import concurrent.futures
import subprocess
import sys
from core import ROOT

def job(model,method):
    name=f'calibration-database-{model}-{method}'
    out=ROOT/'runs'/name
    out.mkdir(parents=True,exist_ok=True)
    with (out/'controller.log').open('a',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,str(ROOT/'run_stream.py'),'--provider',model,'--benchmark','database',
                               '--phase','calibration','--method',method,'--run-id',name],stdout=log,stderr=subprocess.STDOUT)
    print(f'{name}: exit {result.returncode}',flush=True)
    return result.returncode

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(job,m,k) for m in ['deepseek','glm'] for k in ['no_memory','bounded_icl']]
        codes=[f.result() for f in futures]
    raise SystemExit(0 if all(c==0 for c in codes) else 1)
