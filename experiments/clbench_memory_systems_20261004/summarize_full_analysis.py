"""Aggregate validated judge output without treating missing labels as zero."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json
from statistics import median
from prepare import ROOT,read,save,sha
from analysis_provider import PRIVATE,packet_path
from judge_full_analysis import METRICS,validate


def labels(values):
    counts=Counter(v['status'] for v in values)
    scores=[v['score'] for v in values if v['status']=='assessed']
    if 0 in scores: label='observed_issue'
    elif 1 in scores:label='observed_mixed'
    elif 2 in scores:label='positive_evidence_observed'
    elif counts['unknown']:label='unknown'
    elif counts['not_applicable']:label='not_applicable'
    else:label='not_judged'
    return {'label':label,'packet_status_counts':dict(counts),'assessed_scores':dict(Counter(scores)),
            'interpretation':'Presence of a label in assessed evidence fragments; not a whole-task quality score or causal effect'}


def main():
    entries=read(ROOT/'records/full-judge-packet-index.json')
    mechanical=read(ROOT/'records/full-mechanical-task-metrics.json')
    packets_by_task=defaultdict(list);candidate_labels=defaultdict(lambda:defaultdict(list));valid={};failed=[];pending=[]
    finding_counts=Counter();normalizations=0
    for e in entries:
        path=PRIVATE/'judge'/(e['packet_id']+'.json')
        if not path.exists():pending.append(e['packet_id']);continue
        record=read(path);packet=read(packet_path(e['packet_id']))
        if record['packet_sha256']!=sha(packet_path(e['packet_id'])):pending.append(e['packet_id']);continue
        if record['status']!='valid':failed.append({'packet_id':e['packet_id'],'error':record['validation_error']});continue
        try:validate(record['judgement'],packet)
        except ValueError as exc:
            failed.append({'packet_id':e['packet_id'],'error':str(exc),'previous_contract':record.get('response_contract')});continue
        valid[e['packet_id']]=record
        normalizations+=len(record.get('citation_span_normalizations',[]))
        if e['kind']=='task_review':
            packets_by_task[e['unit_id']].append(record)
            finding_counts.update(f['category'] for f in record['judgement'].get('findings',[]))
        else:
            for c in record['judgement']['candidates']:candidate_labels[e['unit_id']][c['candidate_id']].append(c)
    tasks=[];groups=defaultdict(list)
    for row in mechanical:
        records=packets_by_task[row['unit_id']]
        expected=[e for e in entries if e['unit_id']==row['unit_id'] and e['kind']=='task_review']
        value={'unit_id':row['unit_id'],'method':row['method'],'environment':row['environment'],'index':row['index'],
               'valid_packets':len(records),'expected_packets':len(expected),'evidence_packets_complete':len(records)==len(expected),
               'metrics':{m:labels([r['judgement']['metrics'][m] for r in records]) for m in METRICS},
               'finding_categories':dict(Counter(f['category'] for r in records for f in r['judgement'].get('findings',[])))}
        tasks.append(value);groups[row['method'],row['environment']].append((row,value))
    summary=[]
    for (method,env),values in groups.items():
        rows=[r for r,_ in values];judgements=[j for _,j in values]
        roles=defaultdict(lambda:Counter())
        for r in rows:
            for role,value in r['cost_roles'].items():roles[role].update(value)
        summary.append({'method':method,'environment':env,'tasks':len(rows),
            'memory_byte_basis':'canonicalized_persisted_state_payload' if method.startswith('pi_') else 'native_file_payload',
            'before_memory_bytes_max':max(r['before']['physical_bytes'] for r in rows),
            'before_memory_bytes_median':median(r['before']['physical_bytes'] for r in rows),
            'last_after_memory_categories':next((r['after']['categories'] for r in reversed(rows) if r['after'] is not None),None),
            'content_changed_tasks':sum(r['updates']['content_changed_files']>0 for r in rows),
            'exact_repeated_business_actions':sum(r['exact_repeated_actions'] for r in rows),
            'exact_repeated_tool_argument_calls':sum(r['exact_repeated_whole_tool_records'] for r in rows),
            'long_line_exposure_tasks':sum(r['long_memory_lines_exposed']>0 for r in rows),
            'compaction_markers_observed':sum(r['compaction_events_observed'] for r in rows),
            'cost_roles':{k:dict(v) for k,v in roles.items()},
            'all_task_packets_valid':sum(j['evidence_packets_complete'] for j in judgements),
            'semantic_metric_counts':{m:dict(Counter(j['metrics'][m]['label'] for j in judgements)) for m in METRICS}})
    retrieval=[]
    for unit,values in candidate_labels.items():
        e=next(e for e in entries if e['unit_id']==unit and e['kind']=='candidate_relevance')
        packet=read(packet_path(e['packet_id']));scope=packet['scope']
        expected_packets=[e for e in entries if e['unit_id']==unit and e['kind']=='candidate_relevance']
        complete_packets=all(e['packet_id'] in valid for e in expected_packets)
        selected={f'candidate:{i}' for i in scope['selected_indices']};expected={f'candidate:{i}' for i in scope['candidate_indices']}
        merged={}
        for ident in expected:
            scores=[c['score'] for c in values.get(ident,[]) if c['status']=='assessed']
            unknown=any(c['status']!='assessed' for c in values.get(ident,[])) or not values.get(ident)
            merged[ident]=max(scores) if scores and max(scores)>0 else 0 if scores and not unknown and complete_packets else None
        complete=complete_packets and all(v is not None for v in merged.values())
        thresholds={}
        for threshold in [1,2]:
            positive={k for k,v in merged.items() if v is not None and v>=threshold}
            hit=len(selected & positive)
            thresholds[str(threshold)]={'known_positive_candidates':len(positive),'known_selected_positive':hit,
                'precision':hit/len(selected) if complete and selected else None,
                'recall':hit/len(positive) if complete and positive else None}
        retrieval.append({'unit_id':unit,'all_candidate_packets_valid':complete_packets,'all_candidate_labels_known':complete,
                          'candidate_count':len(expected),'selected_count':len(selected),'unknown_candidates':sum(v is None for v in merged.values()),
                          'candidate_labels':merged,'thresholds':thresholds,
                          'reference':'GLM judged relevance of own prior episodes; not human ground truth or causal usefulness'})
    calls=[read(p) for p in (PRIVATE/'requests').glob('*.attempt.json')]
    usage_fields=['input_tokens','output_tokens','total_tokens']
    totals={f:sum((a.get('usage') or {}).get(f) or 0 for a in calls) for f in usage_fields}
    discrepancies=[a['attempt_id'] for a in calls if a.get('usage') and all(k in a['usage'] for k in usage_fields)
                   and a['usage']['input_tokens']+a['usage']['output_tokens']!=a['usage']['total_tokens']]
    repeat=[];invalid_repeats=[]
    for p in (PRIVATE/'judge-repeat').glob('*.json'):
        r=read(p);primary=valid.get(r['packet_id'])
        if not primary or r['status']!='valid':continue
        packet=read(packet_path(r['packet_id']))
        try:validate(r['judgement'],packet)
        except ValueError as exc:
            invalid_repeats.append({'packet_id':r['packet_id'],'error':str(exc)});continue
        if r['kind']=='task_review':
            for m in METRICS:
                a=primary['judgement']['metrics'][m];b=r['judgement']['metrics'][m]
                repeat.append({'packet_id':r['packet_id'],'metric':m,'first_status':a['status'],'first_score':a['score'],
                               'repeat_status':b['status'],'repeat_score':b['score'],'agreement':(a['status'],a['score'])==(b['status'],b['score'])})
        else:
            first={c['candidate_id']:c for c in primary['judgement']['candidates']}
            for b in r['judgement']['candidates']:
                a=first[b['candidate_id']]
                repeat.append({'packet_id':r['packet_id'],'metric':'candidate_relevance','candidate_id':b['candidate_id'],
                               'first_status':a['status'],'first_score':a['score'],'repeat_status':b['status'],'repeat_score':b['score'],
                               'agreement':(a['status'],a['score'])==(b['status'],b['score'])})
    source=read(PRIVATE/'frozen-evidence.json')
    changed=[s['path'] for s in source if sha(ROOT/s['path'])!=s['sha256']]
    assert not changed,'Analysis modified a frozen source'
    both_assessed=[r for r in repeat if r['first_status']==r['repeat_status']=='assessed']
    either_assessed=[r for r in repeat if 'assessed' in (r['first_status'],r['repeat_status'])]
    report={'as_of':datetime.now(timezone.utc).isoformat(),'status':'complete' if not pending and not failed else 'in_progress',
        'expected_packets':len(entries),'valid_packets':len(valid),'failed_packets':failed,'pending_packets':pending,
        'citation_span_normalizations':normalizations,'groups':summary,'finding_category_packet_counts':dict(finding_counts),
        'new_provider_calls':{'attempts':len(calls),'phase_counts':dict(Counter(a['phase'] for a in calls)),
            'unknown_usage_attempts':sum(not a.get('usage') for a in calls),'raw_reported_usage_totals':totals,
            'usage_arithmetic_discrepancies':discrepancies,'actual_dollar_cost':None,
            'note':'Aixoras usage fields preserved independently; old Z.AI prices not applied.'},
        'reliability':{'comparisons':len(repeat),'exact_agreements':sum(r['agreement'] for r in repeat),
            'exact_agreement_rate':sum(r['agreement'] for r in repeat)/len(repeat) if repeat else None,
            'both_assessed_comparisons':len(both_assessed),
            'both_assessed_score_agreement':sum(r['agreement'] for r in both_assessed)/len(both_assessed) if both_assessed else None,
            'either_assessed_comparisons':len(either_assessed),
            'either_assessed_status_score_agreement':sum(r['agreement'] for r in either_assessed)/len(either_assessed) if either_assessed else None,
            'neither_assessed_comparisons':len(repeat)-len(either_assessed),
            'valid_repeat_packets':len({r['packet_id'] for r in repeat}),
            'invalid_repeat_packets':invalid_repeats,
            'note':'Same-model repeat with reversed evidence-document order, not independent human accuracy.'},
        'frozen_evidence':{'files_verified':len(source),'changed_files':changed},
        'causal_effect':'unverified_by_user_choice',
        'limitations':['Semantic labels are D1 interpretations, not causal effects or human gold.',
            'Task labels summarize observed packet evidence; positive_evidence_observed does not prove uniformly good whole-task memory.',
            'Unknown and N/A are separate from zero; incomplete candidate labels yield no precision/recall.',
            'Complete-system and mixed-schedule baseline limitations remain unchanged.']}
    save(ROOT/'records/full-analysis-summary.json',report)
    save(ROOT/'records/full-semantic-task-labels.json',tasks)
    save(ROOT/'records/full-retrieval-relevance.json',retrieval)
    save(ROOT/'records/full-judge-reliability.json',repeat)
    print(json.dumps({'status':report['status'],'valid':len(valid),'expected':len(entries),'failed':len(failed),'pending':len(pending),
                      'new_calls':len(calls),'source_files_unchanged':len(source)},ensure_ascii=False))


if __name__=='__main__':main()
