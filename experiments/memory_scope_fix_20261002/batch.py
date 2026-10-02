"""Resumable, bounded model-run scheduler. Job lists are saved before execution."""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'memory_direction_20261002'


def execute(job):
    run_id = job['run_id']
    directory = ROOT / 'results/runs' / run_id
    if (directory / 'summary.json').exists():
        return {'run_id': run_id, 'status': 'already_finished'}
    if directory.exists():
        return {'run_id': run_id, 'status': 'incomplete_directory_not_restarted'}
    python = json.loads((OLD / 'installation-manifest.json').read_text())['hermes']['python_executable'] if job.get('agent') == 'hermes' else sys.executable
    cmd = [python, '-X', 'utf8', str(ROOT / 'run_task.py')]
    for k, v in job.items():
        if isinstance(v, bool):
            if v:
                cmd.append('--' + k.replace('_', '-'))
        else:
            cmd += ['--' + k.replace('_', '-'), str(v)]
    logs = ROOT / 'results/logs'
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / f'{run_id}.log').open('wb') as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, timeout=900)
    if (directory / 'summary.json').exists():
        s = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
        return {k: s[k] for k in ('run_id', 'quality', 'task_tools', 'memory_writes', 'seconds', 'error')}
    return {'run_id': run_id, 'status': 'process_failed', 'exit_code': proc.returncode}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('jobs')
    p.add_argument('--workers', type=int, default=2)
    a = p.parse_args()
    jobs = json.loads(Path(a.jobs).read_text(encoding='utf-8'))
    if not 1 <= a.workers <= 2:
        raise ValueError('At most two concurrent API experiments')
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for future in as_completed([pool.submit(execute, job) for job in jobs]):
            print(json.dumps(future.result(), ensure_ascii=True), flush=True)
