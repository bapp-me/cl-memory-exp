"""Validate selected judgements against exact sent input and frozen sources."""
from collections import Counter
from datetime import datetime,timezone
import json
from prepare import ROOT,read,save,sha
from analysis_provider import PRIVATE,MODEL
from judge_full_analysis import validate,wire_packet


def main():
    entries=read(ROOT/'records/full-judge-packet-index.json');errors=[];selected=[];pending=[]
    expected_repeat=set(read(ROOT/'records/full-judge-repeat-progress-dispatch.json')['packets'])
    for repeat in [False,True]:
        for e in entries:
            ident=e['packet_id']
            if repeat and ident not in expected_repeat:continue
            path=PRIVATE/('judge-repeat' if repeat else 'judge')/(ident+'.json')
            if not path.exists() or read(path)['status']!='valid':pending.append({'packet_id':ident,'repeat':repeat});continue
            r=read(path);packet_file=PRIVATE/'packets'/(ident+'.json');p=read(packet_file)
            try:
                assert r['packet_sha256']==sha(packet_file),'Evidence hash mismatch'
                validate(r['judgement'],p)
                attempt=r.get('selected_attempt_id',r['attempt_ids'][-1]);request=read(PRIVATE/'requests'/(attempt+'.request.json'));meta=read(PRIVATE/'requests'/(attempt+'.attempt.json'))
                expected=wire_packet(p)
                if repeat:expected['documents']=list(reversed(expected['documents']))
                assert json.loads(request['input'])==expected,'Selected attempt input differs from current evidence'
                assert meta['http_status']==200 and meta['returned_model']==MODEL and meta['response_status']=='completed','Selected response not a completed requested-model result'
                assert request['model']==MODEL and request['max_output_tokens']<=65536,'Wrong requested model/budget'
                assert meta['phase']!='started','Selected attempt not settled'
                selected.append({'packet_id':ident,'repeat':repeat,'selected_attempt_id':attempt,'packet_sha256':r['packet_sha256'],
                    'actual_input_sha256':__import__('hashlib').sha256(request['input'].encode()).hexdigest(),
                    'requested_output_limit':request['max_output_tokens'],'rubric_contract':r.get('response_contract','historical_or_reconciled'),
                    'citation_normalizations':len(r.get('citation_span_normalizations',[])),
                    'json_syntax_normalizations':r.get('json_syntax_normalizations',[])})
            except (AssertionError,ValueError,KeyError,TypeError) as exc:errors.append({'packet_id':ident,'repeat':repeat,'error':str(exc)})
    manifest=read(PRIVATE/'frozen-evidence.json');changed=[r['path'] for r in manifest if sha(ROOT/r['path'])!=r['sha256']]
    calls=[read(p) for p in (PRIVATE/'requests').glob('*.attempt.json')];active=[a['attempt_id'] for a in calls if a['phase']=='started']
    selected_count=sum(not r['repeat'] for r in selected);repeat_count=sum(r['repeat'] for r in selected)
    complete=not errors and not changed and not pending and not active and selected_count==510 and repeat_count==26
    report={'as_of':datetime.now(timezone.utc).isoformat(),'status':'complete' if complete else 'in_progress',
        'primary_packets_validated':selected_count,'repeat_packets_validated':repeat_count,
        'selected':selected,'validation_errors':errors,'pending':pending,'active_attempts':active,
        'original_frozen_files_verified':len(manifest),'original_changed_files':changed,
        'requested_output_limits':dict(Counter(r['requested_output_limit'] for r in selected)),
        'new_attempts':len(calls),'unknown_usage_attempts':sum(not a.get('usage') for a in calls),
        'original_task_reruns_added':0,'evaluated_memory_writeback':False,
        'note':'Mechanically validated evidence provenance and settlement, not a guarantee of semantic truth or causal effect.'}
    save(ROOT/'records/full-analysis-closure-audit.json',report)
    print({k:report[k] for k in ['status','primary_packets_validated','repeat_packets_validated','validation_errors','original_frozen_files_verified','original_changed_files']})


if __name__=='__main__':main()
