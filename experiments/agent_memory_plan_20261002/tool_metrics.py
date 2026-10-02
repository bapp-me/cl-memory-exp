"""Observable tool failures/repetitions; do not infer semantic invalidity or recovery."""
import json
from collections import Counter
from core import ROOT,save

def main():
    records=[]
    for p in sorted((ROOT/'runs').glob('**/pi-result.json')):
        execution=p.with_name('execution.json')
        if not execution.exists():continue
        data=json.loads(p.read_text(encoding='utf-8'))
        counts=Counter(); signatures=Counter()
        for message in data['messages']:
            if message['role']=='assistant':
                for c in message.get('content',[]):
                    if c.get('type')=='toolCall':
                        signatures[(c['name'],json.dumps(c.get('arguments'),sort_keys=True,ensure_ascii=False))]+=1
            if message['role']!='toolResult':continue
            counts['tool_results']+=1
            if message.get('isError'):counts['explicit_tool_error_flags']+=1
            for c in message.get('content',[]):
                if c.get('type')!='text':continue
                try:value=json.loads(c['text'])
                except (ValueError,TypeError):continue
                if not isinstance(value,dict):continue
                if value.get('error'):counts['explicit_error_payloads']+=1
                if isinstance(value.get('returncode'),int) and value['returncode']!=0:
                    counts['nonzero_code_tool_exits']+=1
                    if value['returncode']==124:counts['code_tool_wall_timeouts']+=1
        counts['exact_repeated_tool_signatures']=sum(n-1 for n in signatures.values() if n>1)
        records.append({'task_path':str(p.parent.relative_to(ROOT)),**dict(counts)})
    totals={}
    for item in records:
        run=item['task_path'].split('\\')[1] if '\\' in item['task_path'] else item['task_path'].split('/')[1]
        if run not in totals:totals[run]=Counter()
        totals[run].update({k:v for k,v in item.items() if k!='task_path'})
    report={'per_task':records,'by_run':{k:dict(v) for k,v in totals.items()},'limits':['Error flags and payload counts may overlap; do not add them as independent failures.','Exact repeated calls may be justified after environment changes; not a count of wasted actions.','Nonzero sandbox exit can be agent-written code failure, not necessarily infrastructure failure.','No semantic recovery or invalid-action labels inferred from these counters.']}
    save(ROOT/'records/tool-metrics.json',report)
    print(json.dumps({'tasks':len(records),'runs':len(totals)}))

if __name__=='__main__':main()
