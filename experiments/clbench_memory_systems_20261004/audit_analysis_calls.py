"""Public, content-free accounting of every new provider attempt."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from statistics import median
from prepare import ROOT,read,save
from analysis_provider import PRIVATE


def percentile(values,p):
    if not values:return None
    ordered=sorted(values);return ordered[min(len(ordered)-1,int((len(ordered)-1)*p))]


def main():
    calls=[read(p) for p in (PRIVATE/'requests').glob('*.attempt.json')];now=datetime.now(timezone.utc).timestamp()
    ledger=[];events=[];by_unit=defaultdict(list)
    for a in calls:
        usage=a.get('usage') or {};start=datetime.fromisoformat(a['timestamp']).timestamp();end=start+a['seconds'] if a.get('seconds') is not None else now
        row={k:a.get(k) for k in ['attempt_id','unit_id','role','provider','requested_model','returned_model','timestamp','phase','http_status','response_status','seconds','first_byte_seconds']}
        row.update(input_tokens=usage.get('input_tokens'),output_tokens=usage.get('output_tokens'),total_tokens=usage.get('total_tokens'),
            cached_input_tokens=(usage.get('input_tokens_details') or {}).get('cached_tokens'),
            reasoning_output_tokens=(usage.get('output_tokens_details') or {}).get('reasoning_tokens'))
        row['reported_total_minus_input_output']=usage['total_tokens']-usage['input_tokens']-usage['output_tokens'] if all(usage.get(k) is not None for k in ['total_tokens','input_tokens','output_tokens']) else None
        ledger.append(row);events.extend([(start,1),(end,-1)]);by_unit[a['unit_id'],a['role']].append((start,end,a['attempt_id']))
    active=0;peak=0
    for _,delta in sorted(events):active+=delta;peak=max(peak,active)
    overlaps=[]
    for (unit,role),items in by_unit.items():
        items.sort()
        for i,(start,end,ident) in enumerate(items):
            for begin,finish,other in items[i+1:]:
                if begin>=end:break
                if min(end,finish)-begin>.01:overlaps.append({'unit_id':unit,'role':role,'attempt_ids':[ident,other],'overlap_seconds':round(min(end,finish)-begin,3)})
    finished=[a for a in calls if a.get('seconds') is not None]
    def counts(field):return dict(Counter(str(a.get(field)) for a in calls))
    report={'as_of':datetime.now(timezone.utc).isoformat(),'attempts':len(calls),'active_attempts':sum(a['phase']=='started' for a in calls),
        'phase_counts':counts('phase'),'role_counts':counts('role'),'http_counts':counts('http_status'),
        'response_status_counts':counts('response_status'),'returned_model_counts':counts('returned_model'),
        'observed_client_peak':peak,'same_unit_same_role_overlaps':overlaps,
        'settled_latency_seconds':{'median':median([a['seconds'] for a in finished]) if finished else None,
            'p90':percentile([a['seconds'] for a in finished],.9),'max':max((a['seconds'] for a in finished),default=None)},
        'usage_field_known_sums':{k:sum(a[k] or 0 for a in ledger) for k in ['input_tokens','output_tokens','total_tokens','cached_input_tokens','reasoning_output_tokens']},
        'usage_field_unknown_counts':{k:sum(a[k] is None for a in ledger) for k in ['input_tokens','output_tokens','total_tokens','cached_input_tokens','reasoning_output_tokens']},
        'arithmetic_discrepancy_count':sum(a['reported_total_minus_input_output'] not in [None,0] for a in ledger),
        'arithmetic_discrepancy_sum':sum(a['reported_total_minus_input_output'] or 0 for a in ledger),
        'actual_money_paid':None,'source':'Local per-attempt response metadata, not provider billing records',
        'notes':['All failed, empty, superseded, quality-rejected and repeated assessments retain their attempts.',
                 'Unknown usage is not zero. Raw usage fields are kept independently; nested fields are not added to totals.',
                 'Client interval peak is an observed overlap, not provider maximum capacity. Same-unit primary vs reliability repeat is intentional and separately labeled.']}
    save(ROOT/'records/analysis-attempt-ledger.json',sorted(ledger,key=lambda r:r['timestamp']))
    save(ROOT/'records/analysis-call-audit.json',report)
    print({k:report[k] for k in ['attempts','active_attempts','observed_client_peak','http_counts','arithmetic_discrepancy_count']});print('same-role-overlaps',len(overlaps))


if __name__=='__main__':main()
