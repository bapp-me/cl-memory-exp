"""Separate unassigned provider exposure from corroborated main-agent input."""
from datetime import datetime,timezone
from prepare import ROOT,read,save,sha
from analysis_provider import PRIVATE
from full_analysis import canonical


def main():
    audit=read(ROOT/'records/long-line-exposure-role-audit.json');index=read(ROOT/'records/full-judge-packet-index.json')
    live={read(p)['unit_id'] for p in (PRIVATE/'requests').glob('*.attempt.json') if read(p)['phase']=='started'}
    changed=[]
    for row in audit['tasks']:
        if not row['unconfirmed_lines']:continue
        unit=row['unit_id'];entries=[e for e in index if e['unit_id']==unit and e['kind']=='task_review']
        assert not any(e['packet_id'] in live for e in entries),'Do not change active inputs'
        evidence=read(PRIVATE/'main-exposure-corroboration'/(unit+'.json'))
        for entry in entries:
            path=PRIVATE/'packets'/(entry['packet_id']+'.json');packet=read(path)
            if packet['scope'].get('exposure_actor_contract')=='main_call_id_corroboration_v1':continue
            old_sha=sha(path);save(PRIVATE/'packet-history/actor-attribution'/(entry['packet_id']+'.json'),packet)
            for doc in list(packet['documents']):
                if doc['id'].startswith('exposed_memory_lines@'):
                    doc['kind']='provider_exposure_actor_unconfirmed'
                    doc['path']='Pre-submission provider inputs; only the separately supplied confirmed_main_memory_lines subset is corroborated as main-session exposure'
                    text='\n'.join(evidence['confirmed'])
                    if text:packet['documents'].append({'id':'confirmed_main_memory_lines@0','kind':'visible_memory',
                        'path':'Exact input spans in requests whose emitted tool call IDs occur in the saved main session',
                        'text':text,'character_start':0,'character_end':len(text)})
            packet['scope'].update(exposure_actor_contract='main_call_id_corroboration_v1',
                visible_memory_evidence=bool(evidence['confirmed']),
                actor_attribution_rule='Do not treat provider_exposure_actor_unconfirmed documents as main-agent-visible memory. Only visible_memory documents qualify for current-task relevance/applicability/reuse. File availability and unassigned actor exposure do not establish main-agent receipt.')
            save(path,packet);entry.update(bytes=len(canonical(packet).encode()),evidence_documents=len(packet['documents']),source_characters=sum(len(d['text']) for d in packet['documents']))
            assert entry['bytes']<190000
            changed.append({'packet_id':entry['packet_id'],'before_sha256':old_sha,'after_sha256':sha(path)})
    save(ROOT/'records/full-judge-packet-index.json',index)
    p=ROOT/'records/judge-exposure-actor-correction.json';prior=read(p) if p.exists() else {'revisions':[]}
    prior['revisions'].extend(changed);prior.update(as_of=datetime.now(timezone.utc).isoformat(),model_calls=0,
        original_experiment_changed=False,issue='Two Hermes Codebase tasks contain prior-memory lines in pre-submission requests whose main actor cannot all be corroborated; corrected judge inputs retain uncertainty rather than asserting solver receipt.')
    save(p,prior);print({'modified_packets':len(changed),'affected_tasks':2})


if __name__=='__main__':main()
