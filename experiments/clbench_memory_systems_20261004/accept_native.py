"""Accept the current native wire, fresh-session, and durable-memory contract."""
import argparse
from datetime import datetime,timezone
from prepare import ROOT,read,save,sha
from native_evidence import archive,validate,usage_for,validate_attempt_accounting


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--framework',choices=['claude','hermes','codex'],required=True)
    p.add_argument('--environment',choices=['database_exploration','codebase_adaptation'],required=True)
    p.add_argument('--run-id',required=True)
    args=p.parse_args();d=ROOT/'private-runs'/args.run_id;method=args.framework+'_memory_ready'
    manifest=read(d/'manifest.json');rows=read(d/'results.json')
    assert manifest['namespace']==f'{method}/r1/{args.environment}'
    assert read(d/'stream-status.json')['status']=='prefix_completed'
    assert len(rows)>=2 and len({r['session_id'] for r in rows})==len(rows)
    inspected=[];new_wire=0;new_solver=False
    for row in rows[-2:]:
        out=d/f"task-{row['index']:03d}"
        recovered=row.get('recovered_maintenance',False)
        cfg=read(out/('recovery-input.json' if recovered else 'input.json'))
        assert cfg['output_limit']==65536 and cfg['output_ceiling']==65536 and not cfg['automatic_output_growth']
        snapshot=out/('recovered-native-state.tar.gz' if recovered else 'native-state.tar.gz')
        files=archive(snapshot)
        validate(files,out.name,args.framework,row['session_id'])
        assert read(out/'barrier.json')['durable']
        validate_attempt_accounting(out,usage_for(out))
        since=read(out/'recovery-provenance.json')['recovery_started_at'] if recovered else None
        wire=[]
        for request_path in (out/'requests').glob('*.request.json'):
            meta=read(request_path.with_name(request_path.name.replace('.request.json','.attempt.json')))
            if since and meta['timestamp']<since:continue
            request=read(request_path)
            assert request['model']=='glm-5.3-flash'
            assert request.get('max_output_tokens',request.get('max_tokens'))==65536
            if args.framework=='claude':assert request['output_config']['effort']=='high'
            wire.append(meta['attempt_id'])
        assert wire;new_wire+=len(wire);new_solver|=not recovered
        if row['index']:
            assert read(out/'memory-before.json')==read(d/f"task-{row['index']-1:03d}"/'memory-after.json')
        if args.framework=='hermes':
            effective=__import__('json').loads(files[f'tasks/{out.name}/effective-config.json'])
            assert effective['context_length']==262144 and effective['compression_threshold']==196608
        elif args.framework=='codex':
            config=files['home/.codex/config.toml'].decode()
            assert 'model_context_window = 262144' in config and 'model_auto_compact_token_limit = 196608' in config
        inspected.append({'index':row['index'],'session_id':row['session_id'],'new_wire_attempts':len(wire),
            'maintenance_recovery':recovered,'snapshot_sha256':sha(snapshot)})
    assert new_solver,'At least one current-budget solving session must be observed'
    environment_short='code' if args.environment=='codebase_adaptation' else 'database'
    receipt={'status':'READY','framework':args.framework,'environment':args.environment,'canary':args.run_id,
        'at':datetime.now(timezone.utc).isoformat(),'context':262144,'output_limit':65536,'compression_trigger':196608,
        'new_wire_attempts':new_wire,'inspected':inspected,'model_calls_for_audit':0,
        'business_scoring':'Unmodified official task and grader; native final JSON uses locked official extraction/validation; no semantic repair call.',
        'limitations':['R1 complete-system comparison only','Native auxiliary role correlation may be incomplete',
            'Old completed results retain their original output budgets','Remote provider latency components are not separately observable']}
    name=f'records/{args.framework}-{environment_short}-64k-acceptance.json'
    save(ROOT/name,receipt)
    compatibility=read(ROOT/'records/compatibility.json')
    compatibility[method][args.environment]={'status':'READY','evidence':[name],
        'canary_prefix_reuse_allowed':not any(r.get('recovered_maintenance') for r in rows),
        'limitations':receipt['limitations']}
    save(ROOT/'records/compatibility.json',compatibility)
    print({'framework':args.framework,'environment':args.environment,'status':'READY','new_wire_attempts':new_wire})


if __name__=='__main__':main()
