"""Check traceability of the root reviewer's bounded semantic annotations.

No model judge, whole-memory score or keyword-based semantic pass. Assertions
validate the quoted evidence; the semantic judgments remain explicitly authored
by the reviewing Codex agent and are not human gold labels.
"""
from datetime import datetime, timezone
import hashlib
import json

from database_followup_d0 import PRIVATE, PUBLIC, ROOT, ref
from database_followup_claude import sources, MEMORY
from native_evidence import archive, validate, usage_for, validate_attempt_accounting, memory_snapshot
from prepare import read, save, sha
from protocol import digest


def first_request(out):
    meta=min(out.glob('requests/*.attempt.json'),key=lambda p:read(p)['timestamp'])
    return read(meta.with_name(meta.name.replace('.attempt.json','.request.json')))


def evidence(index, offset, part, needle):
    path=ROOT/'trajectories/claude_code/database'/f'task-{index:03d}.json'
    value=read(path)
    item=value['tools'][offset]
    text=item['action']['content'] if part=='action' else item['observation']
    assert needle in text,(index,offset,part,needle)
    return {**ref(path),'task_index':index,'tool_offset':offset,'part':part,'quote':needle}


def main():
    phase=read(PUBLIC/'d2-claim-review.json')
    assert phase['status'] in {'awaiting_semantic_review','completed'}
    assert len(phase['results'])==8 and all(j['status']=='completed' for j in phase['results'])
    annotations=read(PUBLIC/'d2-claim-annotations.json')
    assert annotations['reviewer']['human_gold'] is False
    keyed={j['job_id']:j for j in phase['results']}
    assert set(keyed)==set(annotations['jobs'])
    lock=read(PUBLIC/'d2-runtime-lock.json')
    assert phase['lock_sha256']==sha(PUBLIC/'d2-runtime-lock.json')
    assert all(sha(PRIVATE/'runtime-source-d2'/n)==h for n,h in lock['source_files'].items())
    native_build=ROOT/'.local/native-runtime-builds'/lock['native_runtime_hash']
    inventory={p.name:sha(p) for p in sorted(native_build.glob('*.py'))}
    assert inventory and hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()==lock['native_runtime_hash']
    continuation=PUBLIC/'d2-continuation-runtime-lock.json'
    if continuation.exists():
        assert phase['continuation_lock_sha256']==sha(continuation)
        latest=read(continuation)
        assert all(sha(PRIVATE/'runtime-source-d2-continuation'/n)==h for n,h in latest['source_files'].items())
        build=ROOT/'.local/native-runtime-builds'/latest['native_runtime_hash']
        inventory={p.name:sha(p) for p in sorted(build.glob('*.py'))}
        assert hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()==latest['native_runtime_hash']
    pairs={};sessions=[];all_attempts=[]
    for job in phase['results']:
        name=job['job_id'];out=PRIVATE/name
        assert sha(ROOT/job['native_state']['path'])==job['native_state']['sha256']
        files=archive(out/'native-state.tar.gz')
        validate(files,name,'claude',job['session_id'])
        attempts=usage_for(out);validate_attempt_accounting(out,attempts)
        assert attempts==job['attempts'];all_attempts.extend(attempts)
        sessions.append(job['session_id'])
        material=read(out/'input-materials.json')
        legal=sources(job['index'])
        for index,projection in legal.items():
            mounted=json.loads(files[f'work/database/followup-sources/task-{index:03d}.json'])
            assert mounted==projection
            source=material['sources'][index]
            assert source['legal_projection_sha256']==digest(projection)
            assert source['sha256']==sha(ROOT/source['path'])
        mounted_sources=[p for p in files if p.startswith('work/database/followup-sources/task-')]
        assert len(mounted_sources)==job['index']+1
        for p in out.glob('requests/*.request.json'):
            request=read(p)
            assert request['model']=='glm-5.3-flash' and request['max_tokens']==65536
            assert request['output_config']['effort']=='high'
        for p in out.glob('requests/*.attempt.json'):
            meta=read(p)
            assert meta['provider']=='aixoras' and meta['endpoint']=='https://api.aixoras.com/v1/messages'
        annotation=annotations['jobs'][name]
        categories=set()
        claims=[]
        for claim in annotation['claims']:
            path=MEMORY+claim['memory_file'] if claim['memory_file'] else None
            if path:
                assert claim['quote'] in files[path].decode('utf8'),(name,claim['quote'])
            else:
                assert claim['status']=='no_materialized_update'
                assert read(out/'memory-diff.json')=={}
                assert memory_snapshot(archive(ROOT/job['pre_state']['path']),'claude')==memory_snapshot(files,'claude')
            categories.add(claim['check'])
            supports=[]
            for source in claim.get('sources',[]):
                assert source['index']<=job['index']
                supports.append(evidence(source['index'],source['offset'],source['part'],source['quote']))
            claims.append({**claim,'sources':supports,'after_memory_path':path,
                'after_memory_sha256':hashlib.sha256(files[path]).hexdigest() if path else None})
        assert categories==set(read(ROOT/'config/database-followup.plan.json')['D2']['claim_checks'])
        job['semantic_review']={'reviewer':annotations['reviewer'],'claims':claims,
            'bounded_gate_pass':annotation['bounded_gate_pass'],
            'decision_reason':annotation['decision_reason'],
            'whole_memory_score':None,'missing_sources_are_not_automatically_false':True}
        job['cost_basis']='unique native Anthropic gateway attempts; native duplicate usage not added again'
        job['materialized_memory_changed']=bool(read(out/'memory-diff.json'))
        if annotation.get('output_anomaly'):
            native=read(out/'native-completion.json')['result']['result']
            unit=annotation['output_anomaly']['repeated_unit']
            assert native and len(native)%len(unit)==0 and native==unit*(len(native)//len(unit))
            job['output_anomaly']={**annotation['output_anomaly'],'repeats':len(native)//len(unit),
                'characters':len(native),'native_completion':ref(out/'native-completion.json'),
                'interpretation':'Native end_turn/completed is lifecycle evidence; no materialized memory update. Cause is unknown; no quality replay.'}
        pairs.setdefault((job['index'],job['repeat']),{})[job['arm']]=job
    assert len(set(sessions))==8
    assert len({a['attempt_id'] for a in all_attempts})==len(all_attempts)
    fairness=[]
    extra=read(ROOT/'config/database-followup.plan.json')['D2']['extra_instruction']
    for (index,repeat),pair in pairs.items():
        a,b=[PRIVATE/pair[arm]['job_id'] for arm in ['W0','W1']]
        ca,cb=[read(p/'input.json') for p in [a,b]]
        exclude={'gateway','gateway_token','session_id','prompt','maintenance_transport_resume','maintenance_resume_prompt'}
        assert {k:v for k,v in ca.items() if k not in exclude}=={k:v for k,v in cb.items() if k not in exclude}
        assert cb['prompt']==ca['prompt']+'\n\n'+extra
        ma,mb=[read(p/'input-materials.json') for p in [a,b]]
        assert all(ma[k]==mb[k] for k in ['pre_state','sources','current_record_sha256','common_prompt_sha256','source_cutoff'])
        pa,pb=[first_request(p) for p in [a,b]]
        from database_followup_results import string_values
        assert any(ca['prompt'] in s for s in string_values(pa['messages']))
        assert any(cb['prompt'] in s for s in string_values(pb['messages']))
        assert all(pa[k]==pb[k] for k in ['system','tools','model','max_tokens','thinking','context_management','output_config','stream'])
        fairness.append({'index':index,'repeat':repeat,'same_original_before':True,
            'same_legal_source_projection_and_access':True,'same_native_tools_system_and_budgets':True,
            'only_prompt_difference': 'exact preregistered generic constraint',
            'request_metadata_difference':'independent native session identifiers',
            'same_session_infrastructure_recovered_jobs':[j['job_id'] for j in pair.values() if j.get('same_session_infrastructure_recovery')]})
    eligible=all(j['semantic_review']['bounded_gate_pass'] for j in phase['results'] if j['arm']=='W1')
    phase.update(status='completed',D3_eligible=eligible,D3_gate='open' if eligible else 'closed_failed_bounded_claim_qualification',
        reviewed_at=datetime.now(timezone.utc).isoformat(),reviewer=annotations['reviewer'],fairness=fairness,
        unique_provider_attempts=len(all_attempts),same_method_price_family_count=1,
        decision='run_preregistered_D3' if eligible else 'stop_D3_no_all_repeat_qualified_writer_signal',
        gate_robustness='Independent disqualifiers already include Q25 W1 repeat 1 uncomputed/USD and unsubmitted/rejection errors and Q23 W1 repeat 2 no materialized update, even if the minor Q7/Q8 provenance typo is ignored.',
        no_new_business_queries=True)
    save(PUBLIC/'d2-claim-review.json',phase)
    if not eligible:
        save(PUBLIC/'d3-downstream-results.json',{'phase':'D3','status':'skipped','native_jobs':0,'results':[],
            'official_scores':None,'reason':'At least one W1 artifact failed a preregistered bounded claim check.',
            'failed_W1_jobs':[j['job_id'] for j in phase['results'] if j['arm']=='W1' and not j['semantic_review']['bounded_gate_pass']],
            'model_calls':0,'skipped_is_not_zero_score':True})
    print(json.dumps({'D2':'completed','attempts':len(all_attempts),'D3_eligible':eligible}))


if __name__=='__main__':main()
