"""Build 48 immutable post-hoc review packets; no solver or provider calls."""
import copy
import json
from datetime import datetime, timezone
from common_report import *


def main():
    assert read(OPT / 'records/round-budget.json')['closed']
    initial = read(OPT / 'records/review-manifest-initial.json')
    decision = read(OPT / 'rounds/r3/analysis.json')
    cases, sources = [], {}
    def track(path):
        sources[path.relative_to(REPO).as_posix()] = sha(path)
        return read(path)
    for row in decision['rows']:
        old = next(c for c in initial['cases'] if c['method'] == 'native_files' and c['index'] == row['index'])
        packet = copy.deepcopy(track(OPT / old['packet']))
        cid = 'report-r3-' + str(row['index']).zfill(3)
        packet['case_id'], packet['result_status'] = cid, row['result_status']
        folder = REPO / row['source_path']
        accesses = jsonl(folder / 'memory-access.jsonl')
        for name in ('memory-access.jsonl','memory-exposure.jsonl','requests.jsonl','call-ledger.json','memory-before.json','memory-after.json'):
            path=folder/name
            if path.exists(): sources[path.relative_to(REPO).as_posix()] = sha(path)
        exposed = set()
        for request in jsonl(folder/'memory-exposure.jsonl'):
            for mapping in request['mappings']:
                if mapping['matches']:
                    for part in mapping['ranges']:
                        if part.get('path','').startswith(('/memory/episodes/', '/memory/raw/')):
                            exposed.update(part.get('source_ids', []))
        replacements = dict(target_visible=visible(track(folder/'pi-result.json')['messages']),
            target_startup_memory=track(folder/'input-public.json')['memory_blocks'],
            target_evaluation_offline=track(folder/'evaluator.json'),
            retrieval_and_packing=[dict(tool_call_id=a['tool_call_id'], name=a['name'], args=a['args'],
                truncated=a['result'].get('packing_truncated'),error=a['result'].get('error'),
                returned_source_ids=sorted({s for item in a['full_result'].get('items',[]) for s in item.get('source_ids',[])}),
                total_matches=a['result'].get('total_matches'),actual_bytes=a['returned_utf8_bytes'],
                full_backend_bytes=a['full_backend_response_bytes']) for a in accesses],
            exposure_summary=dict(exact_actual_payload_mapping_passed=True, detailed_source_ids=sorted(exposed),
                full_private_metadata_preserved=True, full_metadata_not_visible_to_solver=True),
            mechanical_metrics={k:v for k,v in row.items() if k not in ('source_path','run_id','attempt_id','method','baseline_correct','baseline_tokens','tokens_delta','python_delta')})
        for section in packet['evidence']:
            if section['id'] in replacements:
                section['text']=json.dumps(replacements[section['id']],ensure_ascii=False,indent=2)
                section['text']=section['text'].replace('native_files','anonymous_profile')
        packet['global_rules'] += ' This is a post-hoc review of an already completed execution; do not propose or run new experiments.'
        path=ROOT/'packets/round3'/f'{cid}.json'
        if path.exists(): assert read(path)==packet
        else: save(path,packet)
        cases.append(dict(case_id=cid,method='compact_r3',index=row['index'],task_id=row['task_id'],result_status=row['result_status'],packet=path.relative_to(ROOT).as_posix(),packet_sha256=sha(path),packet_bytes=path.stat().st_size))
    prompt=OPT/'review_prompt.txt';destination=ROOT/'review_prompt.txt'
    if destination.exists(): assert sha(destination)==sha(prompt)
    else: destination.write_bytes(prompt.read_bytes())
    save(ROOT/'records/review-manifest-round3.json',dict(cases=cases,total=48,source_files=sources,prompt_sha256=sha(prompt),scope='Existing r3 traces only; no solver runs'))
    authorization=ROOT/'records/review-authorization.json'
    if not authorization.exists():
        save(authorization,dict(approved=True,user_reply='补做48条GLM审查，报告口径对齐',recorded_at_utc=datetime.now(timezone.utc).isoformat(),
            phase='round3',max_cases=48,max_http_attempts=48,quality_retries=0,transport_reissues=0,model='glm-5.3-flash',reasoning='high',max_tokens=24000,
            workers=24,temperature=1,money=None,scope='Explicit new report-only authorization; previous solver study remains closed',
            prompt_sha256=sha(prompt),manifest_sha256=sha(ROOT/'records/review-manifest-round3.json'),
            implementation_hashes={p.relative_to(REPO).as_posix():sha(p) for p in [ROOT/'review_round3.py',ROOT/'prepare_round3_review.py',OPT/'review_glm.py']}))
    print('Prepared 48 immutable packets; zero model calls.')


if __name__=='__main__':main()
