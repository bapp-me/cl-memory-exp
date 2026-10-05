"""One-shot supervisor for the five authorized remaining R1 streams.

No new repetitions or business-task replay. Only known, verified maintenance
failures are resumed. Unknown faults are reported for the operator to diagnose.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from prepare import ROOT,read,save,sha
from native_evidence import archive
from native_progress import RUNS


def classify(directory):
    boundary=read(directory/'boundary.json');pending=boundary.get('pending')
    if not pending:return None,'No pending submitted maintenance'
    out=directory/f"task-{pending['index']:03d}"
    if not (out/'submission.json').exists():return None,'Business has not been frozen; do not replay'
    candidates=[out/name for name in ['recovery-timeout-state.tar.gz','recovered-native-state.tar.gz','timeout-state.tar.gz','native-state.tar.gz'] if (out/name).exists()]
    if not candidates:return None,'No settled recovery snapshot'
    source=max(candidates,key=lambda p:p.stat().st_mtime_ns);files=archive(source);prefix=f'tasks/{out.name}/'
    method=read(directory/'manifest.json')['namespace'].split('/')[0]
    if method=='codex_memory_ready':
        key=prefix+'failed-memory-jobs.json'
        if key not in files:return None,'No verified failed native job; inspect timeout or source watermark'
        jobs=[j for j in json.loads(files[key]) if j['status']=='error']
        if len(jobs)!=1 or jobs[0].get('retry_remaining',0)<=0:return None,'Native retry count exhausted or ambiguous failed jobs'
        job=jobs[0]
        metas=[read(p) for p in (out/'requests').glob('*.attempt.json')]
        if any(m['phase']=='started' for m in metas):return None,'Provider attempts still settling'
        latest=max(metas,key=lambda m:m['timestamp'])
        if latest.get('error') in {'TimeoutError','ConnectionResetError','RemoteDisconnected','URLError','ConnectionAbortedError'} or (latest.get('http_status') or 0)>=500:
            return '--retry-transport-maintenance',{'kind':'verified_transport','job_kind':job['kind'],'remaining':job['retry_remaining'],'attempt_id':latest['attempt_id'],'snapshot_sha256':sha(source)}
        parsing_error=any(x in (job.get('last_error') or '') for x in ['expected value','expected `,` or `}`','expected `:`','EOF while parsing','invalid escape','control character'])
        authorization=read(ROOT/'records/execution-authorization.json').get('native_maintenance_invalid_json_retry',{})
        if job['kind']=='memory_stage1' and job['job_key']==pending['session_id'] and parsing_error and authorization.get('approved'):
            return '--retry-native-maintenance',{'kind':'authorized_native_json_retry','remaining':job['retry_remaining'],'snapshot_sha256':sha(source)}
        return None,'Native failure is outside the approved automatic recovery cases'
    if method=='hermes_memory_ready':
        from importlib.util import spec_from_file_location,module_from_spec
        spec=spec_from_file_location('hermes_completion_supervisor',ROOT/'native-runtime/hermes_completion.py');module=module_from_spec(spec);spec.loader.exec_module(module)
        keys=[prefix+x for x in ['jobs.json','conversations.json','main-result.json']]
        if not all(k in files for k in keys):return None,'Missing native lifecycle evidence'
        jobs,calls,result=[json.loads(files[k]) for k in keys]
        if result.get('failed') or not result.get('completed'):return None,'Native main turn incomplete'
        if not all(j['status']=='returned' and j.get('native_result') not in {None,'error'} for j in jobs):return None,'Unsettled or failed native review needs diagnosis'
        import hashlib
        final_hash=hashlib.sha256(json.dumps(result['messages'],sort_keys=True,default=str).encode()).hexdigest()
        try:_,missing=module.validate_calls(jobs,calls,final_hash,allow_missing=True)
        except RuntimeError as exc:return None,str(exc)
        if missing:return '',{'kind':'superseded_writer_missing_final_source','missing_scopes':missing,'snapshot_sha256':sha(source)}
    return None,'Failure is outside the verified recovery cases'


def main():
    logdir=ROOT/'.local/native-supervisor';logdir.mkdir(exist_ok=True)
    state_path=ROOT/'records/native-supervisor-status.json'
    history=read(state_path).get('recoveries',[]) if state_path.exists() else []
    handled={(x['run_id'],x['recovery']['snapshot_sha256']) for x in history};children={};last=None
    while True:
        attention=[];progress=[]
        for run in RUNS:
            d=ROOT/'private-runs'/run;status=read(d/'stream-status.json')
            results=read(d/'results.json') if (d/'results.json').exists() else []
            progress.append({'run_id':run,'completed':len(results),'status':status['status']})
            if status['status']!='paused_error' or run in children and children[run].poll() is None:continue
            signature=(run,(d/'stream-status.json').stat().st_mtime_ns)
            if signature in handled:continue
            flag,evidence=classify(d)
            if evidence=='Provider attempts still settling':continue
            handled.add(signature)
            if flag is None:
                attention.append({'run_id':run,'reason':evidence});continue
            # A repeated identical snapshot has not made native retry progress.
            fingerprint=(run,evidence['snapshot_sha256'])
            if fingerprint in handled:
                attention.append({'run_id':run,'reason':'Same snapshot already retried; no further automatic action'});continue
            handled.add(fingerprint)
            method,_,environment=read(d/'manifest.json')['namespace'].split('/')
            command=[sys.executable,str(ROOT/'run_native.py'),'--framework',method.removesuffix('_memory_ready'),
                '--environment',environment,'--mode','formal','--run-id',run,'--resume']+([flag] if flag else [])
            entry={'run_id':run,'at':datetime.now(timezone.utc).isoformat(),'recovery':evidence}
            with (logdir/(run+'.log')).open('a',encoding='utf8') as output:
                children[run]=subprocess.Popen(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
            history.append(entry);print(json.dumps({'resumed':entry}),flush=True)
        previous=read(state_path) if state_path.exists() else {}
        unresolved={x['run_id']:x for x in previous.get('attention',[]) if next((p['status'] for p in progress if p['run_id']==x['run_id']),None)=='paused_error'}
        unresolved.update({x['run_id']:x for x in attention})
        value={'as_of':datetime.now(timezone.utc).isoformat(),'kind':'one_shot_current_R1_only','progress':progress,'attention':list(unresolved.values()),'recoveries':history}
        save(state_path,value)
        compact=json.dumps({'progress':progress,'attention':list(unresolved.values())},sort_keys=True)
        if compact!=last:print(compact,flush=True);last=compact
        if all(p['status']=='completed' for p in progress):break
        time.sleep(5)


if __name__=='__main__':main()
