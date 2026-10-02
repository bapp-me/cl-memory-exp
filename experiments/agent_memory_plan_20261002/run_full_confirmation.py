"""Section 6.9 only after an explicit evidence-based benchmark decision."""
import concurrent.futures
import json
import subprocess
import sys
from core import ROOT

def launch(command,name):
    folder=ROOT/'runs'/name;folder.mkdir(parents=True,exist_ok=True)
    with (folder/'controller.log').open('a',encoding='utf-8') as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    print(f'{name}: exit {result.returncode}',flush=True)
    if result.returncode:raise RuntimeError(name+' did not complete')

def job(method):
    first=f'full-codeeval-glm-{method}'
    if method=='no_memory':
        launch([sys.executable,str(ROOT/'run_no_memory_parallel.py')],first)
    else:
        launch([sys.executable,str(ROOT/'run_stream.py'),'--provider','glm','--benchmark','codeeval','--phase','full','--method',method,'--run-id',first],first)

def noncode(method):
    name=f'noncode-babyai-glm-{method}'
    launch([sys.executable,str(ROOT/'run_babyai.py'),'--provider','glm','--method',method],name)

if __name__=='__main__':
    if (ROOT/'.runtime/PAUSE_FULL_CONFIRMATION').exists():
        raise SystemExit('Confirmation paused pending scope clarification; no calls dispatched.')
    decision=json.loads((ROOT/'records/benchmark-decision.json').read_text(encoding='utf-8'))
    assert decision['development_benchmark']=='AgentCL'
    memory=decision['confirmation_memory_method']
    assert memory in ['bounded_icl','episodic_retrieval']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fn,m) for fn in [job,noncode] for m in ['no_memory',memory]]
        for f in futures:f.result()
