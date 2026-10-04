"""Database admission from native capability, task, lifecycle and wire evidence."""
import argparse
from prepare import ROOT,read,save
from native_evidence import archive,validate,usage_for

p=argparse.ArgumentParser(); p.add_argument('--framework',choices=['claude','hermes'],required=True)
p.add_argument('--run-id',required=True); args=p.parse_args()
method=args.framework+'_memory_ready'; d=ROOT/'private-runs'/args.run_id
assert read(ROOT/'records/native-broker-fixture.json')['status']=='passed'
assert read(ROOT/'records/database-fixtures.json')['status']=='passed'
assert read(d/'stream-status.json')['status']=='prefix_completed'
rows=read(d/'results.json'); assert len(rows)==2 and len({r['session_id'] for r in rows})==2
for row in rows:
    out=d/f"task-{row['index']:03d}"
    validate(archive(out/'native-state.tar.gz'),out.name,args.framework,row['session_id'])
    assert read(out/'barrier.json')['durable']
    attempts=usage_for(out)
    assert attempts and all(a['phase']=='finished' and a['http_status']==200 and a['usage'] and a['returned_model']=='glm-5.3-flash' for a in attempts)
    for path in (out/'requests').glob('*.request.json'):
        request=read(path); assert request['model']=='glm-5.3-flash'
        if args.framework=='claude': assert request['output_config']['effort']=='high'
        # Hermes auxiliary effort follows native defaults, floored to provider low
        # only when its unsupported none setting would be rejected.
    if row['index']:
        assert read(out/'memory-before.json')==read(d/'task-000/memory-after.json')
compat=read(ROOT/'records/compatibility.json')
compat[method]['database_exploration']={'status':'READY','canary_prefix_reused':False,
    'evidence':[d.relative_to(ROOT).as_posix(),f'records/{args.framework}-live-capability.json',
        'records/native-broker-fixture.json',f'records/protocol-{"anthropic" if args.framework=="claude" else "chat"}-window.json'],
    'observability':'all provider attempts captured; native role correlation may be incomplete',
    'limitations':['Complete-system R1 comparison only','Framework USD estimates are not actual GLM billing',
        '256k native configuration and actual small-task wire usage verified; compression behavior is framework-specific',
        'Formal stream starts cold after transport fixes; no old canary memory reuse']}
save(ROOT/'records/compatibility.json',compat)
save(ROOT/f'records/{args.framework}-database-acceptance.json',{'status':'READY','canary':args.run_id,
    'canary_prefix_reused':False,'context':262144,'initial_output':16384,
    'native_output_growth_rule':'provider output length plus reported output usage reaching the cap; same-session continuation',
    'memory_barrier':'explicit covered native review' if args.framework=='hermes' else 'completed native foreground turn and all reported subagents settled'})
print({'framework':args.framework,'database_READY':True})
