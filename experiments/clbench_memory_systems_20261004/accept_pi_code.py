"""Promote only unchanged, fully audited v4 code prefixes; no duplicate solving."""
import argparse
from prepare import ROOT, read, save, sha
from protocol import digest, namespace

p=argparse.ArgumentParser(); p.add_argument('--method',choices=['pi_none','pi_notepad','pi_jaccard'],required=True)
a=p.parse_args(); method=a.method
run_id='candidate-code-'+method.replace('_','-')+'-v4'; d=ROOT/'private-runs'/run_id
assert read(ROOT/'records/codebase-failure-fixture.json')['status']=='passed'
assert read(ROOT/'records/codebase-fixtures.json')['status']=='passed'
assert read(d/'stream-status.json')['status']=='prefix_completed'
rows=read(d/'results.json'); assert len(rows)==2
ns=namespace(method,1,'codebase_adaptation')
files=['pi_session.mjs','protocol.py','run_pi_database.py','codebase_adapter.py','docker_dispatch.py']
config=digest({'files':{f:sha(ROOT/f) for f in files},'plan':sha(ROOT/'config/experiment.json'),'namespace':ns})
assert read(d/'manifest.json')['config_hash']==config
assert len({r['session_id'] for r in rows})==2
for index,row in enumerate(rows):
    out=d/f'task-{index:03d}'
    assert read(out/'barrier.json')['status']=='not_applicable'
    assert all(x['usage'] and x['returned_model']=='glm-5.3-flash' for x in row['attempts'])
    for request in (out/'requests').glob('*.request.json'):
        payload=read(request)
        # Pi records the actual payload directly, including compaction requests.
        assert payload['model']=='glm-5.3-flash'
        assert payload['reasoning_effort']=='high'
    if index: assert read(out/'memory-before.json')==read(d/f'task-{index-1:03d}'/'memory-after.json')
if method=='pi_notepad':
    # Writing is optional in the pinned official Notepad contract. An empty
    # model-selected result is not an adapter failure or a reason to force prose.
    for request in d.glob('task-*/requests/*.request.json'):
        properties=read(request)['tools'][0]['function']['parameters']['properties']
        assert 'notepad_update' in properties
if method=='pi_jaccard':
    assert len(read(d/'memory.json')['history'])==2
    assert len(read(d/'task-001/retrieval.json')['selected_source_ids'])==1
compat=read(ROOT/'records/compatibility.json')
compat[method]['codebase_adaptation']={'status':'READY','canary_prefix_reused':True,
    'evidence':['records/codebase-fixtures.json','records/codebase-failure-fixture.json',d.relative_to(ROOT).as_posix()],
    'limitations':['R1 complete-system result, not pure memory causality','test_patch visible as explicitly authorized']}
save(ROOT/'records/compatibility.json',compat)
manifest=read(d/'manifest.json'); manifest.update(mode='formal',canary_prefix_reused=True,accepted_prefix_instances=2)
save(d/'manifest.json',manifest)
save(ROOT/f'records/{method}-code-acceptance.json',{'status':'READY','run_id':run_id,'config_hash':config,
    'accepted_prefix_instances':2,'resume_from':2,'prefix_resubmitted':False,
    'notepad_characters':len(read(d/'memory.json')['notepad']) if method=='pi_notepad' else None})
print({'method':method,'code_READY':True,'reused_prefix':2})
