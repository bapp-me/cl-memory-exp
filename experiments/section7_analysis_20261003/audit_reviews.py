"""Coverage, quote integrity and descriptive D1 summaries; raw outputs untouched."""
from collections import Counter
from common import *
from review import validate,ENUMS


def get_review(case):
    phase='pilot2' if case['pilot'] else 'formal'
    p=ROOT/'reviews'/phase/'deepseek'/f'{case["case_id"]}.json'
    balance=ROOT/'reviews/formal_balance_retry/deepseek'/f'{case["case_id"]}.json'
    if balance.exists():p=balance
    repaired=ROOT/'reviews/syntax-repaired/deepseek'/f'{case["case_id"]}.json'
    if repaired.exists():p=repaired
    return read(p) if p.exists() else None


def main():
    manifest=read(ROOT/'records/manifest.json');results=[]
    for case in manifest['cases']:
        cid=case['case_id'];packet=read(ROOT/'packets'/f'{cid}.json');obj=get_review(case)
        if obj is None:
            results.append({**case,'review_available':False,'unknown':True});continue
        errors=validate(obj,packet);text={s['id']:s['text'] for s in packet['evidence']}
        def valid_evidence(claim):
            ev=claim.get('evidence',[])
            return bool(ev) and all(e.get('quote') and e.get('quote') in text.get(e.get('section'),'') for e in ev)
        semantic={k:obj.get('semantic',{}).get(k) or {'value':'unknown','evidence':[]} for k in ENUMS}
        strict={k:v.get('value','unknown') if v.get('value') in ['unknown','not_applicable'] or valid_evidence(v) else 'unknown' for k,v in semantic.items()}
        labels=[l['tag'] for l in obj['labels']];grounded=[l['tag'] for l in obj['labels'] if valid_evidence(l)]
        results.append({**case,'review_available':True,'validation_errors':errors,'strict_valid':not errors,
                        'reported_result_status':obj['result_status'],'status_agrees_with_fixed_score':obj['result_status']==('success' if case['correct'] else 'scorable_failure'),
                        'semantic_raw':{k:v.get('value','unknown') for k,v in semantic.items()},'semantic_quote_checked':strict,
                        'labels_raw':labels,'labels_with_matching_quotes':grounded,'primary_raw':obj['primary_hypothesis'],
                        'confidence':obj['confidence'],'causal_claim':obj['causal_claim'],
                        'interpretation':'Quote substring matching is not verification that the inference is supported.'})
    summaries=[]
    for method in METHODS:
        for benchmark in ['codeeval','babyai']:
            xs=[x for x in results if x['method']==method and x['benchmark']==benchmark];available=[x for x in xs if x['review_available']]
            summaries.append({'method':method,'benchmark':benchmark,'applicable_tasks':len(xs),'reviewed':len(available),'no_parseable_output':len(xs)-len(available),
                              'strict_valid':sum(x['strict_valid'] for x in available),
                              'status_disagreements':sum(not x['status_agrees_with_fixed_score'] for x in available),
                              'semantic_raw_counts':{k:dict(Counter(x['semantic_raw'][k] for x in available)) for k in ENUMS},
                              'semantic_quote_checked_counts':{k:dict(Counter(x['semantic_quote_checked'][k] for x in available)) for k in ENUMS},
                              'label_counts_raw':dict(Counter(l for x in available for l in set(x['labels_raw']))),
                              'label_counts_quote_checked':dict(Counter(l for x in available for l in set(x['labels_with_matching_quotes']))),
                              'primary_counts':dict(Counter(x['primary_raw'] for x in available)),
                              'failure_reviewed':sum(not x['correct'] for x in available),'success_reviewed':sum(x['correct'] for x in available)})
    save(ROOT/'records/review-audit.json',{'cases':results,'summaries':summaries,'complete':all(x['review_available'] for x in results),
         'strict_valid_total':sum(x.get('strict_valid',False) for x in results),'human_truth':False,
         'warning':'Raw and quote-checked D1 label frequencies are not causal failure rates or human-validated truth. Unmatched evidence converted to unknown only in derived semantic_quote_checked counts.'})
    costs=[]
    for p in sorted((ROOT/'api').glob('*/*/*/terminal.json')):
        x=read(p);costs.append({k:x.get(k) for k in ['provider','phase','case_id','model_returned','status','http_status','seconds','usage','http_attempts','error']})
    save(ROOT/'records/review-costs.json',{'http_attempts':len(costs),'known_total_tokens':sum((x['usage'] or {}).get('total_tokens',0) for x in costs),
         'known_prompt_tokens_including_cache':sum((x['usage'] or {}).get('prompt_tokens',0) for x in costs),
         'known_completion_tokens_including_reasoning':sum((x['usage'] or {}).get('completion_tokens',0) for x in costs),
         'known_cache_hit_tokens_subset_of_prompt':sum(((x['usage'] or {}).get('prompt_tokens_details') or {}).get('cached_tokens',(x['usage'] or {}).get('prompt_cache_hit_tokens',0)) for x in costs),
         'unknown_usage_requests':sum(x['usage'] is None for x in costs),'by_phase':[{ 'phase':ph,'provider':pr,'requests':len(xs),'known_tokens':sum((x['usage'] or {}).get('total_tokens',0) for x in xs),'unknown_usage':sum(x['usage'] is None for x in xs),'sum_seconds':sum(x['seconds'] for x in xs)} for ph,pr in sorted({(x['phase'],x['provider']) for x in costs}) for xs in [[x for x in costs if (x['phase'],x['provider'])==(ph,pr)]]],
         'requests':costs,'money':None,'money_reason':'No verified invoice; usage and cache counters retained separately from baseline','gpt_reference_usage':'not exposed by subagent tool; unavailable, not zero'})
    print(json.dumps({'reviewed':sum(x['review_available'] for x in results),'expected':324,'strict_valid':sum(x.get('strict_valid',False) for x in results),'http_requests':len(costs)},ensure_ascii=False))


if __name__=='__main__':main()
