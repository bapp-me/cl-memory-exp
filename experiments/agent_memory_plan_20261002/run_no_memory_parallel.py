"""Resume independent no-memory tasks concurrently, retaining original task IDs."""
import concurrent.futures
import json
from core import ROOT, CodeTask, CODE_TOOLS, run_pi, grade_code, save, digest
from run_stream import rows_for

RUN = 'full-codeeval-glm-no_memory'

def one(index, row):
    folder = ROOT/'runs'/RUN/f'{index:03d}'
    if (folder/'commit.json').exists():
        commit = json.loads((folder/'commit.json').read_text(encoding='utf-8'))
        assert commit['before_hash'] == commit['after_hash'] == digest([])
        return commit['result']
    if (folder/'events.jsonl').exists():
        raise RuntimeError(f'Uncommitted attempt requires audit: {folder}')
    task = CodeTask(row, ROOT/'.runtime/workspaces'/RUN/f'{index:03d}')
    _, execution = run_pi('glm', row['problem'], [], 'no_memory', task, CODE_TOOLS, folder)
    if (execution['error'] or execution['stop_reason'] in ['error','aborted']) and not (execution['response_timed_out'] or execution['context_exceeded']):
        save(folder/'infrastructure-failure.json', execution)
        raise RuntimeError(f'Model/runtime failure: {folder}')
    score = grade_code(row, task.submission or '')
    save(folder/'evaluator.json', score)
    save(folder/'memory-after.json', [])
    result = {'index':index, 'task_id':row['category']+':'+row['id'], **execution,
              'correct':score['correct'], 'scorable':score['scorable'],
              'tests_run':score['tests_run'], 'checks_executed':score.get('checks_executed')}
    save(folder/'commit.json', {'before_hash':digest([]), 'after_hash':digest([]), 'result':result})
    return result

if __name__ == '__main__':
    root = ROOT/'runs'/RUN
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    rows = rows_for('full')
    assert manifest['method']=='no_memory' and not manifest['readonly']
    assert manifest['task_ids']==[r['category']+':'+r['id'] for r in rows]
    summary=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        pending={pool.submit(one,i,row):i for i,row in enumerate(rows)}
        try:
            for future in concurrent.futures.as_completed(pending):
                result=future.result();summary.append(result)
                save(root/'summary.json',sorted(summary,key=lambda x:x['index']))
                print(json.dumps({'completed':len(summary),'index':result['index'],'correct':result['correct']}),flush=True)
        except BaseException:
            for future in pending:future.cancel()
            raise
    save(root/'final-memory.json',[])
