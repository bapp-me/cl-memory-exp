"""Small, auditable text-memory probes; no paid judge calls."""
import json
import re
from lab_common import ROOT,save_json
from analyze_runs import extract_answer

longmem={'stars':('0f05491a','120'),'tutor':('dfde3500','Wednesday'),'coffee':('6071bd76','less water; 6 to 5 ounces')}
mab=json.loads((ROOT/'results/mab-selection.json').read_text(encoding='utf-8'))
sh_probe=json.loads((ROOT/'results/mab-sh-probe.json').read_text(encoding='utf-8')) if (ROOT/'results/mab-sh-probe.json').exists() else None
rows=[]
for directory in sorted((ROOT/'results/runs').iterdir()):
    if not directory.name.startswith(('lm-','mab-')) or not (directory/'summary.json').exists():continue
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'));result=summary.get('result',{})
    inp=json.loads((directory/'input.json').read_text(encoding='utf-8'))
    final=result.get('final_response','');answer=extract_answer(final)
    text=str(answer['answer']) if answer else final
    condition='write' if inp['write_memory'] else 'oracle full input' if 'oracle' in directory.name else 'curated + native history' if inp['mode']=='native' else 'native history only'
    correct=None;gold=None
    if '-query-' in directory.name:
        if 'stars' in directory.name:gold='120';correct=bool(re.search(r'\b120\b',text))
        elif 'tutor' in directory.name:gold='Wednesday';correct='wednesday' in text.lower()
        elif 'coffee' in directory.name:gold='less water; 6 to 5 ounces';correct='less' in text.lower() and bool(re.search(r'\b5\b',text)) and bool(re.search(r'\b6\b',text))
    if match:=re.search(r'mab-\w+-q(\d+)-',directory.name):
        gold=mab['cases'][int(match.group(1))]['answers']
        correct=text.strip().casefold() in [x.casefold() for x in gold]
    if '-sh50-' in directory.name and sh_probe:
        gold=sh_probe['answers'];correct=text.strip().casefold() in [x.casefold() for x in gold]
    if not result.get('completed'):correct=None
    counts={'input_uncached':0,'input_cached':0,'output_tokens':0};incomplete=0;requests=0
    ledger=directory/'http/ledger.jsonl'
    for line in ledger.read_text(encoding='utf-8').splitlines() if ledger.exists() else []:
        item=json.loads(line)
        if item['status']!=200:continue
        requests+=1;merged={}
        for u in item['usage_events']:merged.update(u)
        incomplete+=int(len(item['usage_events'])<2)
        for name,key in [('input_uncached','input_tokens'),('input_cached','cache_read_input_tokens'),('output_tokens','output_tokens')]:counts[name]+=merged.get(key,0)
    calls=[]
    for message in result.get('messages',[]):
        for call in message.get('tool_calls',[]) or []:
            fn=call.get('function',{})
            if fn.get('name')=='tool_call':
                try:
                    for child in json.loads(fn.get('arguments','{}')).get('calls',[]):calls.append(child if isinstance(child,dict) else {'malformed':child})
                except ValueError:pass
            else:calls.append({'name':fn.get('name'),'arguments':fn.get('arguments')})
    peak=(counts['input_uncached']*.3+counts['input_cached']*.006+counts['output_tokens']*1.2)/1e6
    rows.append({'run_id':directory.name,'provider':inp['provider'],'condition':condition,'completed':bool(result.get('completed')),
        'archive_files':inp.get('archive_files',False),'effort':inp.get('provider_adapter',{}).get('effort','high'),
        'correct':correct,'answer':answer['answer'] if answer else None,'gold':gold,'seconds':summary['seconds'],
        'history_search_call_attempts':sum(c.get('name')=='session_search' for c in calls),'memory_calls':sum(c.get('name')=='memory' for c in calls),
        'malformed_tool_call_entries':sum('name' not in c for c in calls),
        'tool_calls':calls,'usage':counts,'http_requests':requests,'incomplete_usage_requests':incomplete,
        'cost_usd_range':[round(peak/2,6),round(peak,6)] if inp['provider']=='deepseek' else None,
        'memory_chars':sum(len(p.read_text(encoding='utf-8')) for p in (directory/'memory_after').glob('*.md'))})
save_json(ROOT/'results/text-memory-scoreboard.json',{'runs':rows,
    'limits':['Small selected probes, not official benchmark scores.','LongMemEval 3 answers manually reviewed; keyword checks are only convenient assertions, not a general judge.',
        'Oracle full input differs from retrieval conditions; compare token costs and capability ceilings, not only accuracy.',
        'Initial LongMemEval history import treated naive timestamps as UTC, shifting Hermes display by 8 hours. Tested answer ordering unaffected; corrected in later runner.']})
for r in rows:print(json.dumps({k:r[k] for k in ['run_id','completed','correct','seconds','history_search_call_attempts','memory_chars','usage','cost_usd_range']}))
