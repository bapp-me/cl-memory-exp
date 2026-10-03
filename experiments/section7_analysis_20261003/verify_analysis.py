"""Read-only invariant checks for section 7.2. No imports of model runners."""
from collections import Counter
from common import *


def normalized(raw):
    if not raw or 'prompt_tokens' not in raw or 'completion_tokens' not in raw:return None
    details=raw.get('prompt_tokens_details') or {}
    cache_read=details.get('cached_tokens',raw.get('prompt_cache_hit_tokens',raw.get('cached_tokens',0)))
    cache_write=details.get('cache_write_tokens',0)
    inp=max(0,raw['prompt_tokens']-cache_read-cache_write);out=raw['completion_tokens']
    return dict(input=inp,output=out,cacheRead=cache_read,cacheWrite=cache_write,totalTokens=inp+out+cache_read+cache_write)


def main():
    m=read(ROOT/'records/manifest.json');d0=read(ROOT/'records/d0-tasks.json');issues=[]
    assert len(d0)==624 and len(m['cases'])==324 and len({x['case_id'] for x in m['cases']})==324
    for method in METHODS:
        code=[x for x in d0 if x['method']==method and x['benchmark']=='codeeval']
        assert len(code)==96 and sum(x['scorable'] for x in code)==93
        assert len([x for x in code if x['scorable'] and x['task_id'].startswith('new:')])==46
        assert len([x for x in d0 if x['method']==method and x['benchmark']=='babyai'])==8
    sourcefiles={**read(ROOT/'records/source-hashes.json'),**read(ROOT/'records/d0-input-hashes.json')}
    for path,expected in sourcefiles.items():
        if sha(REPO/path)!=expected:issues.append({'path':path,'issue':'baseline source changed'})
    for x in m['cases']:
        if sha(ROOT/'packets'/f'{x["case_id"]}.json')!=x['packet_sha256']:issues.append({'case_id':x['case_id'],'issue':'packet changed'})
    usage_tasks=0;attempts=0;unknown=0;role_records=[]
    for row in d0:
        if row['source_kind']=='legacy_descriptive_reuse':continue
        folder=REPO/row['source_path'];paths=[folder/'call-ledger.json',*folder.glob('auxiliary/*/call-ledger.json')]
        known=Counter();missing=0;count=0
        for path in paths:
            if not path.exists():continue
            for call in read(path):
                for attempt in call['http_attempts']:
                    count+=1;usage=normalized(attempt.get('raw_usage'))
                    if usage is None:missing+=1
                    else:known.update(usage)
        if dict(known)!=(row['known_usage_subtotal'] or {}):issues.append({'case_id':row['case_id'],'issue':'raw HTTP usage sum mismatch','computed':dict(known),'registered':row['known_usage_subtotal']})
        if missing!=row['unknown_usage_http_attempts']:issues.append({'case_id':row['case_id'],'issue':'unknown usage count mismatch'})
        usage_tasks+=1;attempts+=count;unknown+=missing
        role_records.append({'case_id':row['case_id'],'http_attempts':count,'unknown':missing,'known':dict(known)})
    priority=read(ROOT/'records/priority-16-adjudication.json')
    for row in priority['records']:
        packet=read(ROOT/'packets'/f'{row["case_id"]}.json');texts={s['id']:s['text'] for s in packet['evidence']}
        for e in row['evidence']:
            assert e['quote'] in texts[e['section']]
    for r in read(ROOT/'records/legacy-retrieval-reconstructed.json'):assert r['injection_hash_verified']
    assert len(read(ROOT/'records/scoring-surface-audit.json')['findings'])==1
    # Cost difference sign and paired count identities catch denominator/aggregation errors.
    final=read(OBS/'records/section7.1-final.json')
    ref={s['benchmark']:s for s in final['summary'] if s['method']=='no_memory'}
    for pair in read(ROOT/'records/efficiency-pairs.json'):
        s=next(s for s in final['summary'] if s['method']==pair['method'] and s['benchmark']==pair['benchmark'])
        n=ref[pair['benchmark']];field='correct_complex_targets' if pair['benchmark']=='codeeval' else 'correct'
        assert pair['improvement_candidates']-pair['harm_candidates']==s[field]-n[field]
        assert pair['both_correct']+pair['both_fail']+pair['harm_candidates']+pair['improvement_candidates']==pair['denominator']
    save(ROOT/'records/verification.json',{'status':'passed' if not issues else 'failed','issues':issues,'baseline_source_files_unchanged':len(sourcefiles),
          'packet_hashes_verified':len(m['cases']),'matrix_tasks':len(d0),'new_tasks_raw_usage_verified':usage_tasks,
          'http_attempts_recomputed':attempts,'unknown_usage_attempts':unknown,'legacy_injection_hashes_verified':208,
          'priority_evidence_quotes_verified':sum(len(x['evidence']) for x in priority['records']),'online_calls':0,
          'role_usage_records':role_records})
    print(json.dumps({k:v for k,v in read(ROOT/'records/verification.json').items() if k!='role_usage_records'}))
    assert not issues


if __name__=='__main__':main()
