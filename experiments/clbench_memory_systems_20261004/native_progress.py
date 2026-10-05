"""Compact read-only progress of the remaining native streams."""
from datetime import datetime,timezone
import json
import time
from prepare import ROOT,read
from native_gateway import gate

RUNS=['candidate-code-claude-64k-v2','candidate-code-hermes-64k-v2','candidate-code-codex-64k-v1',
      'formal-db-hermes-r1','formal-db-codex-r1']


def main():
    rows=[]
    pause_path=ROOT/'records/native-user-pause.json'
    pause=read(pause_path) if pause_path.exists() else {}
    paused=set(pause.get('run_ids',[])) if pause.get('status')=='paused_by_user' else set()
    for run in RUNS:
        directory=ROOT/'private-runs'/run
        if not directory.exists():continue
        results=read(directory/'results.json') if (directory/'results.json').exists() else []
        tasks=sorted(directory.glob('task-*'));task=tasks[-1] if tasks else None
        status=read(directory/'stream-status.json') if (directory/'stream-status.json').exists() else {}
        submission=task/'submission.json' if task else None
        row={'run':run,'completed':len(results),'correct':sum(r['correct'] for r in results),
            'status':'paused_by_user' if run in paused else status.get('status','running'),'current_index':int(task.name[5:]) if task else None,
            'current_submitted':bool(submission and submission.exists())}
        if row['current_submitted'] and task.name!=f'task-{len(results)-1:03d}':
            row['seconds_since_original_submission']=round(time.time()-submission.stat().st_mtime)
        rows.append(row)
    print(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'gate':gate('status',{}),'streams':rows}))


if __name__=='__main__':main()
