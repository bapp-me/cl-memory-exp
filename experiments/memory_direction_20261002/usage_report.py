"""Aggregate provider usage, including debug attempts and incomplete runs."""
import json
import gzip
from lab_common import ROOT, save_json


def main():
    totals={p:{'input_uncached':0,'input_cached':0,'output_tokens':0,'metered_requests':0,'incomplete_usage_requests':0} for p in ['glm','deepseek']}
    details=[]
    missing_output_upper={'glm':0,'deepseek':0}
    for run in sorted((ROOT/'results/runs').iterdir()):
        inp=json.loads((run/'input.json').read_text(encoding='utf-8'));p=inp['provider']
        ledger=run/'http/ledger.jsonl'
        if ledger.exists():
            records=[json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines()]
            for row in records:
                merged={}
                for event in row['usage_events']:merged.update(event)
                if row['status']!=200:continue
                complete=len(row['usage_events'])>=2
                counts={'input_uncached':merged.get('input_tokens',0),
                        'input_cached':merged.get('cache_read_input_tokens',0),
                        'output_tokens':merged.get('output_tokens',0)}
                for key,value in counts.items():totals[p][key]+=value
                if not complete:
                    request=run/'http'/f"{row['request']:03d}-request.json"
                    if request.exists():payload=json.loads(request.read_text(encoding='utf-8'))
                    elif request.with_suffix('.json.gz').exists():payload=json.loads(gzip.decompress(request.with_suffix('.json.gz').read_bytes()))
                    else:payload={}
                    cap=payload.get('effective_payload',{}).get('max_tokens')
                    if isinstance(cap,int):missing_output_upper[p]+=max(0,cap-counts['output_tokens'])
                totals[p]['metered_requests']+=int(complete)
                totals[p]['incomplete_usage_requests']+=int(not complete)
                details.append({'run':run.name,'request':row['request'],'provider':p,'usage_complete':complete,**counts})
        elif (run/'summary.json').exists():
            s=json.loads((run/'summary.json').read_text(encoding='utf-8'));u=s.get('result',{}).get('usage',{})
            for key,field in [('input_uncached','input_tokens'),('input_cached','cache_read_input_tokens'),('output_tokens','output_tokens')]:totals[p][key]+=u.get(field,0)
            if u:details.append({'run':run.name,'provider':p,'native_usage_without_request_capture':u})
    for row in json.loads((ROOT/'results/api-smoke.json').read_text(encoding='utf-8')):
        u=row.get('data',{}).get('usage',{});p=row['provider']
        if not u:continue
        cache=u.get('prompt_tokens_details',{}).get('cached_tokens',0)
        totals[p]['input_uncached']+=u.get('prompt_tokens',0)-cache
        totals[p]['input_cached']+=cache
        totals[p]['output_tokens']+=u.get('completion_tokens',0)
        totals[p]['metered_requests']+=1
    d=totals['deepseek'];peak=(d['input_uncached']*.3+d['input_cached']*.006+d['output_tokens']*1.2)/1_000_000
    report={'providers':totals,'deepseek_metered_cost_usd_range':[round(peak/2,6),round(peak,6)],
            'missing_output_token_upper_bound_from_request_caps':missing_output_upper,
            'deepseek_cost_usd_range_including_max_missing_output':[round(peak/2,6),round(peak+missing_output_upper['deepseek']*1.2/1e6,6)],
            'glm_cost_usd':None,'pricing_source':'https://api-docs.deepseek.com/quick_start/pricing/',
            'note':'Includes debug runs and known metering from interrupted runs. Incomplete response usage may omit output; estimates are not invoices. Claude native costBasis=unknown is not used.',
            'requests':details}
    save_json(ROOT/'results/usage-report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='requests'}))


if __name__=='__main__':main()
