"""Freeze 324 full-coverage review packets and six calibration cases; no API calls."""
import re
from common import *


def main():
    final = read(OBS / 'records/section7.1-final.json')
    assets = read(OBS / '.cache/agentcl-codeeval.json')
    rows = final['results']
    pairs = {(p['method'], p['target_index']): p for p in final['paired_source_target_rows']}
    lookup = {(r['method'], r['benchmark'], r['index']): r for r in rows}
    source_manifest, manifest = {}, []
    pilot = {('episodic_retrieval',48),('episodic_retrieval',49),('bounded_icl',60),
             ('mem0',50),('awm',53),('ace',52)}

    def tracked(path):
        if path.exists():
            source_manifest[path.relative_to(REPO).as_posix()] = sha(path)
            return read(path)
        return None

    for row in rows:
        if not row['scorable'] or (row['benchmark']=='codeeval' and not row['task_id'].startswith('new:')):
            continue
        folder = REPO / row['source_path']
        pi = tracked(folder / 'pi-result.json')
        inj = tracked(folder / 'injected.json')
        pair = pairs.get((row['method'],row['index'])) if row['benchmark']=='codeeval' else None
        sections=[]

        def add(name, value):
            if value is None:
                return
            text = value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)
            # Remove identifying run names, preserving within-stream sequence and native item IDs.
            text = re.sub(r'(?:section7-[\w-]+|full-codeeval-glm-[\w_]+|noncode-babyai-glm-[\w_]+)\.task-', 'stream.task-',text)
            if name.endswith('operations'):
                text = re.sub(r'"method": "[^"]+",?\n', '',text)
            sections.append({'id':name,'text':text,'truncated':False})

        add('target_prompt',assets[row['index']]['problem'] if pair else next(m['content'] for m in pi['messages'] if m['role']=='user'))
        add('target_visible',visible(pi['messages']))
        add('target_submission',(folder/'submission.py').read_text(encoding='utf-8') if (folder/'submission.py').exists() else {'submitted':row['submitted']})
        if (folder/'submission.py').exists(): source_manifest[(folder/'submission.py').relative_to(REPO).as_posix()]=sha(folder/'submission.py')
        add('offline_target_evaluation',tracked(folder/'evaluator.json'))
        if pair:
            add('offline_target_reference',{'reference_solution':assets[row['index']]['solution'],'tests':assets[row['index']]['test_code']})
        for i,item in enumerate(inj):
            # Unescape episode text, so evidence is easy to quote while content is lossless.
            add(f'injection/{i}',item['text'])
        add('injection_metadata',[{k:v for k,v in x.items() if k!='text'} for x in inj])
        ret=tracked(folder/'retrieval.json')
        add('retrieval',ret)
        mechanical={k:row.get(k) for k in ['correct','scorable','submitted','terminal_state','response_timed_out','context_exceeded','solver_error','memory_error','tools_by_name','working_tool_calls','submit_calls','known_usage_subtotal','unknown_usage_http_attempts']}
        mechanical['injected_count']=len(inj)
        mechanical['injected_text_utf8_bytes']=sum(len(x['text'].encode()) for x in inj)
        mechanical['memory_policy']='disabled' if row['method']=='no_memory' else 'enabled'
        if pair:
            mechanical['source_pair']={k:v for k,v in pair.items() if k in ['source_correct','source_scorable','distance','source_provenance_retained','source_provenance_injected','source_provenance_in_observable_retrieval_candidates','raw_source_episode_retained_in_method_state']}
            srcrow=lookup[(row['method'],'codeeval',pair['source_index'])]
            src=REPO/srcrow['source_path']
            add('source_prompt',assets[pair['source_index']]['problem'])
            add('source_visible',visible(tracked(src/'pi-result.json')['messages']))
            add('offline_source_evaluation',tracked(src/'evaluator.json'))
            add('source_update_operations',tracked(src/'native-operations.json'))
            aux=[]
            for q in sorted((src/'auxiliary').glob('*/aux-result.json')):
                z=tracked(q); aux.append({'role':q.parent.name,'text':z.get('text'),'error':z.get('error')})
            add('source_auxiliary_visible',aux)
            before=tracked(folder/'memory-before.json')
            after=tracked(src/'memory-after.json')
            if isinstance(before,dict):
                # Full workflow/playbook could be large; present complete relevant provenance records,
                # and all injected content, never pretend this is the complete library.
                source_attempt=next((k for vals in before.get('provenance',{}).values() for k in vals if f'.task-{pair["source_index"]:03d}.' in k),None)
                ids=[k for k,v in before.get('provenance',{}).items() if source_attempt and source_attempt in v]
                add('source_provenance_at_target',{'source_index':pair['source_index'],'memory_ids':ids,'warning':'source ID coverage is not content fidelity; entire unselected library is not presented'})
            add('source_state_summary',{'before_target_hash':digest(before),'after_source_hash':digest(after),'full_unselected_state_presented':False})
        add('mechanical',mechanical)
        add('target_update_operations',tracked(folder/'native-operations.json'))
        packet={'schema':'section7.2-review-v1','case_id':case_id(row),'benchmark':row['benchmark'],
                'evidence_level_ceiling':'D1','evidence':sections,
                'limitations':['No controlled intervention.','Unselected complete memory library not included; do not infer absence from this packet.',
                               'Private reasoning removed; visible actions and final artifacts retained.',
                               'Current target post-task updates cannot explain prior target behavior.']}
        save(ROOT/'packets'/f'{packet["case_id"]}.json',packet)
        manifest.append({'case_id':packet['case_id'],'method':row['method'],'benchmark':row['benchmark'],'index':row['index'],
                         'task_id':row['task_id'],'correct':row['correct'],'source_path':row['source_path'],
                         'pilot':row['benchmark']=='codeeval' and (row['method'],row['index']) in pilot,
                         'packet_sha256':sha(ROOT/'packets'/f'{packet["case_id"]}.json'),'bytes':(ROOT/'packets'/f'{packet["case_id"]}.json').stat().st_size})
    assert len(manifest)==324 and sum(x['pilot'] for x in manifest)==6
    # Preselect independent audit sample before labels exist: six non-pilot cases per method,
    # balanced by success/failure, plus all original sixteen priority failures.
    audit=[]
    for method in METHODS:
        for correct in [True,False]:
            candidates=[x for x in manifest if x['method']==method and x['correct']==correct and not x['pilot']]
            audit.extend(x['case_id'] for x in sorted(candidates,key=lambda x:digest(['audit-v1',x['case_id']]))[:3])
    priority=[case_id(lookup[('episodic_retrieval','codeeval',p['target_index'])]) for p in pairs.values()
              if p['method']=='episodic_retrieval' and p['target_scorable'] and p['source_correct'] and p['source_provenance_injected'] and not p['target_correct']]
    assert len(priority)==16
    save(ROOT/'records/manifest.json',{'cases':manifest,'pilot_ids':[x['case_id'] for x in manifest if x['pilot']],
         'audit_sample_ids':audit,'priority_16_ids':priority,'audit_selection':'SHA256 audit-v1, 3 success + 3 failure per method, excluding pilot, frozen before labels'})
    source_manifest[(OBS/'records/section7.1-final.json').relative_to(REPO).as_posix()]=sha(OBS/'records/section7.1-final.json')
    source_manifest[(OBS/'.cache/agentcl-codeeval.json').relative_to(REPO).as_posix()]=sha(OBS/'.cache/agentcl-codeeval.json')
    save(ROOT/'records/source-hashes.json',source_manifest)
    print(json.dumps({'cases':len(manifest),'pilot':sum(x['pilot'] for x in manifest),'bytes':sum(x['bytes'] for x in manifest),'max_bytes':max(x['bytes'] for x in manifest),'source_files':len(source_manifest)}))


if __name__=='__main__':main()
