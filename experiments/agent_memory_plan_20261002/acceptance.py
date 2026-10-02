"""Pre-model checks for isolation, data grading, feedback and source solutions."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from core import ROOT, CACHE, Database, grade_code, sandbox, save, memory_context,reference_module

def main():
    work=ROOT/'.runtime/sandbox-canary';work.mkdir(parents=True,exist_ok=True)
    code='''import os,socket,json
checks={"host_repo_hidden":not os.path.exists('/mnt/d/campus_re'),"host_home_hidden":not os.path.exists('/home/fucak'),"proc_hidden":not os.path.exists('/proc'),"no_external_interfaces":socket.if_nameindex()==[(1,'lo')],"no_secret_environment":not any('KEY' in k or 'TOKEN' in k for k in os.environ)}
try:
 open('/usr/isolation_write_probe','w').write('x')
 checks['system_readonly']=False
except OSError: checks['system_readonly']=True
import numpy,pandas,scipy,matplotlib,seaborn,sklearn,statsmodels,faker,holidays
checks['imports']=True
print(json.dumps(checks))
assert all(checks.values())
'''
    (work/'probe.py').write_text(code,encoding='utf-8')
    isolation=sandbox(work,['/usr/bin/python3','/work/probe.py'])
    report={'isolation':isolation,'reference_checks':[],'database_checks':[]}
    save(ROOT/'records/acceptance.json',report)
    if isolation['returncode']!=0:raise RuntimeError(isolation)
    db=Database()
    for i in [0,19,20,39]:
        db.start(i)
        q=db.row
        value=db._conn.execute(q['sql']).fetchone()[0]
        match=db._evaluate_answer(str(value),q)
        wrong=db.tool('ANSWER',{'answer':'__INTENTIONALLY_WRONG__'})
        report['database_checks'].append({'index':i,'question_id':q['question_id'],'reference_sql_matches_answer':match,'wrong_rejected':not db.score()['correct'],'safe_feedback':wrong})
        assert match and not db.score()['correct']
    db.start(0)
    for i in range(15):db.tool('QUERY',{'sql':'SELECT 1'})
    overflow=db.tool('QUERY',{'sql':'SELECT 1'})
    assert overflow['submitted'] and db.score()['reward']==0
    report['query_budget_check']=True
    history=[{'sequence':0,'text':'prior task canary'}]
    assert memory_context(history,'no_memory','canary')==[]
    assert memory_context(history,'episodic_retrieval','canary')==history
    report['memory_checks']=True
    rows=json.loads((CACHE/'agentcl-codeeval.json').read_text(encoding='utf-8'))
    chosen=json.loads((ROOT/'records/agentcl-selection.json').read_text(encoding='utf-8'))['ordered_task_ids']
    selected={(x['category'],x['id']) for x in chosen}
    chosen_rows=rows if '--full' in sys.argv else [r for r in rows if (r['category'],r['id']) in selected]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(grade_code,row,reference_module(row)):row for row in chosen_rows}
        for future in as_completed(jobs):
            row=jobs[future];result=future.result()
            entry={'id':row['id'],'category':row['category'],**result}
            report['reference_checks'].append(entry)
            save(ROOT/'records/acceptance.json',report)
            print(json.dumps({k:entry.get(k) for k in ['id','category','correct','tests_run','returncode']}),flush=True)
    valid=[x for x in report['reference_checks'] if x.get('scorable',True)]
    report['all_reference_passed']=all(x['correct'] for x in report['reference_checks'])
    report['scorable_reference_count']=len(valid)
    report['all_scorable_reference_passed']=all(x['correct'] for x in valid)
    first=next(r for r in rows if (r['category'],r['id']) in selected)
    negative=grade_code(first,'raise RuntimeError("intentionally invalid submission")')
    report['negative_control_rejected']=not negative['correct']
    save(ROOT/'records/acceptance.json',report)

if __name__=='__main__':main()
