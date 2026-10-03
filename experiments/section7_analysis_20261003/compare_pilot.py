"""Operational golden agreement, never a claim of ground-truth accuracy."""
from collections import Counter
from common import *
from review import validate,ENUMS


def main():
    ids=read(ROOT/'records/manifest.json')['pilot_ids']; reports=[]
    gold={cid:read(ROOT/'reviews/golden'/f'{cid}.json') for cid in ids}
    gold_validation={cid:validate(gold[cid],read(ROOT/'packets'/f'{cid}.json')) for cid in ids}
    for phase in ['pilot','pilot2']:
        for provider in ['deepseek','glm']:
            records=[];tp=fp=fn=0;f1s=[];field_match=Counter();valid=0
            for cid in ids:
                terminal=ROOT/'api'/phase/provider/cid/'terminal.json'
                if not terminal.exists():continue
                t=read(terminal)
                p=ROOT/'reviews'/provider/f'{cid}.json' if phase=='pilot' else ROOT/'reviews'/phase/provider/f'{cid}.json'
                g=gold[cid];o=read(p) if p.exists() else None
                record={'case_id':cid,'status':t['status'],'seconds':t['seconds'],'usage':t.get('usage'),
                        'error':t.get('error'),'validation_errors':t.get('validation_errors'),
                        'gold_labels':[l['tag'] for l in g['labels']],'gold_primary':g['primary_hypothesis']}
                if o:
                    valid+=1
                    for key in ENUMS:
                        equal=o['semantic'][key]['value']==g['semantic'][key]['value'];field_match[key]+=equal
                    for key in ['result_status','primary_hypothesis']:
                        field_match[key]+=o[key]==g[key]
                    gs=set(l['tag'] for l in g['labels']);os=set(l['tag'] for l in o['labels'])
                    a,b,c=len(gs&os),len(os-gs),len(gs-os);tp+=a;fp+=b;fn+=c
                    f1=2*a/(2*a+b+c) if 2*a+b+c else 1;f1s.append(f1)
                    record.update(labels=sorted(os),primary=o['primary_hypothesis'],label_f1=f1,
                                  semantic={k:o['semantic'][k]['value'] for k in ENUMS},
                                  gold_semantic={k:g['semantic'][k]['value'] for k in ENUMS})
                else:
                    # Missing output is a missed reference label, not silently omitted.
                    fn+=len(set(l['tag'] for l in g['labels']));f1s.append(0)
                records.append(record)
            reports.append({'phase':phase,'provider':provider,'expected':6,'completed_requests':len(records),'parseable_reviews':valid,
                            'strict_valid_reviews':sum(x['status']=='valid' for x in records),
                            'field_matches_out_of_6':dict(field_match),
                            'semantic_match_fraction_all_24':sum(field_match[k] for k in ENUMS)/24,
                            'label_micro_f1_with_missing_as_empty':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                            'label_macro_f1_with_missing_as_zero':sum(f1s)/6,
                            'known_tokens':sum((x['usage'] or {}).get('total_tokens',0) for x in records),
                            'unknown_usage_requests':sum(x['usage'] is None for x in records),
                            'sum_request_seconds':sum(x['seconds'] for x in records),'records':records})
    save(ROOT/'records/pilot-comparison.json',{'reference':'gpt-6.1-sol xhigh, same six packets; operational golden, not human truth',
         'gold_validation':gold_validation,'reports':reports,'selection':'requires evidence adjudication; not automatically based on F1'})
    print(json.dumps({'gold_validation':gold_validation,'reports':[{k:v for k,v in r.items() if k!='records'} for r in reports]},ensure_ascii=False))


if __name__=='__main__':main()
