"""Current durable results and token-price estimates, including failed attempts."""
import json
from datetime import datetime,timezone
from core import ROOT,save

def main():
    entries=[]
    for p in sorted((ROOT/'runs').glob('**/execution.json')):
        d=json.loads(p.read_text(encoding='utf-8'))
        name=p.relative_to(ROOT/'runs').parts[0]
        provider='deepseek' if 'deepseek' in name else 'glm'
        u=d['usage']
        if provider=='deepseek':
            low=(u['input']*.15+u['cacheRead']*.003+u['output']*.6)/1e6
            high=low*2
        else:low=high=(u['input']*.15+u['cacheRead']*.03+u['output']*.5)/1e6
        committed=p.with_name('commit.json')
        score=json.loads(committed.read_text(encoding='utf-8'))['result'] if committed.exists() else None
        entries.append({'run':name,'task_path':str(p.parent.relative_to(ROOT)),
                        'provider':provider,'usage':u,'seconds':d['seconds'],'committed':committed.exists(),
                        'error':d['error'],'correct':score['correct'] if score else None,
                        'usd_estimate_min':low,'usd_estimate_max':high})
    probes=json.loads((ROOT/'records/model-connectivity.json').read_text(encoding='utf-8'))
    probe_costs=[]
    for probe in probes:
        u=probe.get('data',{}).get('usage',{})
        cached=u.get('prompt_tokens_details',{}).get('cached_tokens',u.get('prompt_cache_hit_tokens',0))
        uncached=u.get('prompt_tokens',0)-cached
        if probe['provider']=='deepseek':
            low=(uncached*.15+cached*.003+u.get('completion_tokens',0)*.6)/1e6;high=low*2
        else:low=high=(uncached*.15+cached*.03+u.get('completion_tokens',0)*.5)/1e6
        probe_costs.append({'provider':probe['provider'],'usage':u,'usd_min':low,'usd_max':high})
    report={'at':datetime.now(timezone.utc).isoformat(),'entries':entries,'connectivity_probes':probe_costs,
            'completed_pi_tasks':len(entries),'committed_stream_tasks':sum(x['committed'] for x in entries),
            'usd_estimate_min':sum(x['usd_estimate_min'] for x in entries)+sum(x['usd_min'] for x in probe_costs),
            'usd_estimate_max':sum(x['usd_estimate_max'] for x in entries)+sum(x['usd_max'] for x in probe_costs),
            'limits':['Includes completed connectivity probes; excludes currently streaming requests.',
                      'Failed requests without returned usage have unknown cost, not zero.',
                      'DeepSeek range uses official off-peak/peak prices; GLM official token rates; not an invoice.'],
            'price_sources':['https://api-docs.deepseek.com/quick_start/pricing/','https://docs.z.ai/guides/overview/pricing']}
    save(ROOT/'records/run-index.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='entries'},ensure_ascii=True))

if __name__=='__main__':main()
