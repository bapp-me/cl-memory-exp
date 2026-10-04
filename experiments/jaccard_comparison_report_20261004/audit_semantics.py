"""Raw GLM outputs, exact citation audits and lossless scalar extraction; no model calls."""
from collections import Counter,defaultdict
import re
import json
from common_report import *
from review_glm import validate,ENUMS,AGENTIC_ENUMS
from audit_reviews_opt import resolve

def main():
    manifest=read(ROOT/'records/review-manifest-round3.json');output=[];raw_rows=[]
    for case in manifest['cases']:
        folder=ROOT/'api/round3'/case['case_id']
        if (folder/'transport-retry-1/terminal.json').exists():folder=folder/'transport-retry-1'
        if not (folder/'terminal.json').exists():
            output.append(dict(**case,parsed=False,status='unfinished',fully_citation_grounded=False));continue
        terminal=read(folder/'terminal.json');packet=read(ROOT/case['packet']);assert sha(ROOT/case['packet'])==case['packet_sha256']
        text=(folder/'visible-output.txt').read_text(encoding='utf-8') if (folder/'visible-output.txt').exists() else ''
        fields={}
        for field,allowed in {**ENUMS,**AGENTIC_ENUMS}.items():
            matches=list(re.finditer(r'"'+re.escape(field)+r'"\s*:\s*\{\s*"value"\s*:\s*"([^"]*)"',text))
            if len(matches)==1:
                m=matches[0];fields[field]=dict(value=m.group(1),valid_enum=m.group(1) in allowed,raw_char_start=m.start(1),raw_char_end=m.end(1))
            else:fields[field]=dict(value=None,state='missing_or_ambiguous')
        if text:raw_rows.append(dict(case_id=case['case_id'],index=case['index'],fields=fields,source_file=(folder/'visible-output.txt').relative_to(ROOT).as_posix(),source_sha256=sha(folder/'visible-output.txt')))
        answer_path=ROOT/'reviews/round3'/f"{case['case_id']}.json"
        if not answer_path.exists():
            output.append(dict(**case,parsed=False,status=terminal['status'],error=terminal.get('error'),fully_citation_grounded=False));continue
        answer=read(answer_path);sections={s['id']:s['text'] for s in packet['evidence']};claims=[]
        for group in ('semantic','agentic_search'):
            claims.extend((group+'.'+field,c) for field,c in answer.get(group,{}).items())
        claims.extend(('labels.'+str(i),c) for i,c in enumerate(answer.get('labels',[])))
        grounded=[]
        for field,claim in claims:
            citations=[dict(citation=c,resolution=resolve(c,sections)) for c in claim.get('evidence',[])]
            okay=bool(citations) and all(c['resolution']['status']!='unresolved' for c in citations)
            if claim.get('value') in ('unknown','not_applicable') and not citations:okay=True
            grounded.append(dict(field=field,value=claim.get('value',claim.get('tag')),level=claim.get('level','D1'),citation_grounded=okay,citations=citations,reason=claim.get('reason')))
        errors=validate(answer,packet)
        output.append(dict(**case,parsed=True,status=terminal['status'],strict_schema_and_raw_quotes_passed=not errors,strict_errors=errors,
            fully_citation_grounded=bool(grounded) and all(c['citation_grounded'] for c in grounded),claims=grounded,
            raw_labels=[c.get('tag') for c in answer.get('labels',[])],
            grounded_labels=[c['value'] for c in grounded if c['field'].startswith('labels.') and c['citation_grounded'] and c['value'] in TAGS and c['level'] in ('D0','D1')],
            primary_hypothesis=answer.get('primary_hypothesis'),minimal_intervention=answer.get('minimal_intervention'),competing_explanations=answer.get('competing_explanations')))
    summary=dict(cases=48,parsed=sum(r['parsed'] for r in output),strict_valid=sum(r.get('strict_schema_and_raw_quotes_passed',False) for r in output),
        fully_citation_grounded=sum(r['fully_citation_grounded'] for r in output),
        grounded_label_counts=dict(Counter(t for r in output for t in r.get('grounded_labels',[]))),
        raw_four_field_coverage=sum(all(r['fields'][f].get('valid_enum',False) for f in ENUMS) for r in raw_rows),
        raw_seven_field_coverage=sum(all(v.get('valid_enum',False) for v in r['fields'].values()) for r in raw_rows),
        raw_scalar_distributions={f:dict(Counter(r['fields'][f].get('value') or 'missing_or_ambiguous' for r in raw_rows)) for f in {**ENUMS,**AGENTIC_ENUMS}})
    attempts=[read(p) for p in (ROOT/'api/round3').rglob('terminal.json')];used=[a['usage'] for a in attempts if a.get('usage') is not None]
    costs=dict(http_attempts=len(attempts),model_responses=sum(a.get('http_status')==200 for a in attempts),
        unknown_usage_attempts=sum(a.get('usage') is None for a in attempts),total_tokens=sum(u['total_tokens'] for u in used),
        prompt_tokens_including_cache=sum(u['prompt_tokens'] for u in used),output_tokens=sum(u['completion_tokens'] for u in used),
        cached_tokens=sum(u.get('prompt_tokens_details',{}).get('cached_tokens',0) for u in used),money=None)
    save(ROOT/'records/review-audit-round3.json',dict(summary=summary,costs=costs,rows=output,raw_fields=raw_rows,
        model_calls_during_audit=0,citation_grounding_is_not_semantic_validation=True,human_reviewed=False,
        input_caveat='exposure_summary.detailed_source_ids was empty because compact public ranges omit source IDs. This is missing metadata, not absence of source exposure. Source ranges are now joined from audited full_result to actually visible calls. Target_visible always contained actual solver-visible memory text. Do not accept absence conclusions based on that field alone.'))
    print(json.dumps(dict(summary=summary,costs=costs),ensure_ascii=False))

if __name__=='__main__':main()
