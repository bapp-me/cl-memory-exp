"""Replay completed task commits and prove no additional provider requests."""
import hashlib
import subprocess
import sys
from core import ROOT,save

def hashes(root):
    paths=list(root.glob('*/transport.jsonl'))+[root/'final-memory.json',root/'summary.json']
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

if __name__=='__main__':
    name='calibration-database-glm-bounded_icl'
    root=ROOT/'runs'/name
    before=hashes(root)
    result=subprocess.run([sys.executable,str(ROOT/'run_stream.py'),'--provider','glm','--benchmark','database','--phase','calibration','--method','bounded_icl','--run-id',name],capture_output=True)
    after=hashes(root)
    report={'run':name,'returncode':result.returncode,'provider_logs_memory_summary_unchanged':before==after,
            'files_checked':len(before),'extra_model_calls':0 if before==after and result.returncode==0 else None}
    save(ROOT/'records/resume-check.json',report)
    print(report)
    assert result.returncode==0 and before==after
