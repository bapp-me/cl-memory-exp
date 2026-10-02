"""Run the verified, pre-registered two-task calibration dependency pair."""
import concurrent.futures
import json
import subprocess
import sys
from core import ROOT

def job(model,method):
    name=f'calibration-codeeval-{model}-{method}'
    folder=ROOT/'runs'/name;folder.mkdir(parents=True,exist_ok=True)
    with (folder/'controller.log').open('a',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,str(ROOT/'run_stream.py'),'--provider',model,'--benchmark','codeeval','--phase','calibration','--method',method,'--run-id',name],stdout=log,stderr=subprocess.STDOUT)
    print(f'{name}: exit {result.returncode}',flush=True)
    return result.returncode

if __name__=='__main__':
    checks=json.loads((ROOT/'records/acceptance.json').read_text(encoding='utf-8'))
    pair=[r for r in checks['reference_checks'] if r['id']=='BigCodeBench/868']
    assert len(pair)==2 and all(r['correct'] for r in pair)
    assert checks['negative_control_rejected'] and checks['isolation']['returncode']==0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(job,m,k) for m in ['deepseek','glm'] for k in ['no_memory','bounded_icl']]
        codes=[f.result() for f in futures]
    raise SystemExit(0 if all(x==0 for x in codes) else 1)
