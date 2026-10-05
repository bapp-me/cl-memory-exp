"""Conditional D3: use every qualified D2 artifact once, no selection/replay."""
import json
import subprocess
import sys
import threading
from datetime import datetime,timezone

from prepare import ROOT,read,save,sha
from database_followup_d0 import PRIVATE,PUBLIC,ref
from database_followup_d1 import job,pump
from database_followup_claude import helpers
import native_client
from native_client import freeze_runtime


def main():
    review=read(PUBLIC/'d2-claim-review.json')
    if review['status']!='completed' or not review.get('D3_eligible'):
        raise RuntimeError('D3 requires source-based D2 qualification, not stylistic caution')
    if read(PUBLIC/'d3-downstream-results.json').get('native_jobs',0):
        raise RuntimeError('D3 already started; no automatic quality replay')
    assert len(review['results'])==8
    native_client.BROKER_KIND='default'
    runtime=freeze_runtime()
    lock={'schema_version':'database-followup.runtime-lock.v1','phase':'D3','at':datetime.now(timezone.utc).isoformat(),
        'authorization':'User requested completing the Database follow-up and Claude; qualified conditional stage applies',
        'D2_review':ref(PUBLIC/'d2-claim-review.json'),'max_solver_jobs':8,
        'model':'glm-5.3-flash','provider':'aixoras','endpoint':'https://api.aixoras.com/v1/messages',
        'framework':'Claude Code 2.1.289','context_tokens':262144,'max_output_tokens':65536,
        'compaction_target':196608,'main_effort':'high','query_budget':15,'quality_retry':False,
        'job_concurrency':1,'all_role_http_concurrency':1,'intermediate_tasks_and_memory':'omitted equally',
        'target_trajectory_feedback_and_references':'isolated evaluator only','native_runtime_hash':runtime,
        'source_files':{n:sha(ROOT/n) for n in ['database_followup_downstream.py','database_followup_d1.py',
            'database_followup_claude.py','native_gateway.py','database_adapter.py']},
        'use_all_D2_outputs_once':True,'selection':'no best-artifact selection',
        'interpretation':'local branches, not a full online stream replay','monetary_charge':None}
    save(PUBLIC/'d3-runtime-lock.json',lock)
    frozen=PRIVATE/'runtime-source-d3';frozen.mkdir(exist_ok=True)
    for name,h in lock['source_files'].items():
        assert sha(ROOT/name)==h;(frozen/name).write_bytes((ROOT/name).read_bytes())
    processes=[];stop=threading.Event();rows=[]
    try:
        helpers(processes);threading.Thread(target=pump,args=(stop,),daemon=True).start()
        for producer in review['results']:
            writer=producer['index'];target={22:24,24:26}[writer]
            initial=ROOT/producer['native_state']['path']
            assert sha(initial)==producer['native_state']['sha256']
            result=job(target,producer['arm'],producer['repeat'],runtime,lock,
                framework='claude',phase='D3',candidate=initial)
            result['writer_event_index']=writer;result['producer_job_id']=producer['job_id']
            rows.append(result);save(PRIVATE/'d3-progress.json',{'jobs':rows})
            print(json.dumps({k:result.get(k) for k in ['job_id','status','official_correct','answer','queries','reason']}),flush=True)
            if result['status']!='completed':break
    finally:
        stop.set()
        for process in reversed(processes):
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()
        save(PUBLIC/'d3-downstream-results.json',{'phase':'D3','status':'completed' if len(rows)==8 and
            all(r['status']=='completed' for r in rows) else 'blocked','native_jobs':len(rows),'results':rows,
            'lock_sha256':sha(PUBLIC/'d3-runtime-lock.json'),'intermediate_tasks_executed':False})


if __name__=='__main__':main()
