"""Descriptive results only: paired tasks are not independent replications."""
import json
from datetime import datetime,timezone
from core import ROOT,save

def aggregate(records):
    valid=[r for r in records if r.get('scorable') and r.get('correct') is not None]
    return {'executed':len(records),'scorable':len(valid),'correct':sum(r['correct'] is True for r in valid),
            'accuracy':sum(r['correct'] is True for r in valid)/len(valid) if valid else None,
            'submitted':sum(r.get('submitted',False) for r in records),
            'seconds':round(sum(r.get('seconds',0) for r in records),3),
            'tokens':sum(r.get('usage',{}).get('totalTokens',0) for r in records),
            'tool_calls':sum(r.get('tool_calls',0) for r in records),
            'queries':sum(r.get('queries',0) for r in records),
            'mean_native_reward':sum(r['reward'] for r in valid if 'reward' in r)/len(valid) if valid and 'reward' in valid[0] else None}

def main():
    runs=[]
    for p in sorted((ROOT/'runs').glob('*/summary.json')):
        records=json.loads(p.read_text(encoding='utf-8'))
        entry={'run':p.parent.name,'all':aggregate(records)}
        if 'codeeval' in p.parent.name:
            entry['complex_targets']=aggregate([r for r in records if str(r['task_id']).startswith('new:')])
            entry['source_tasks']=aggregate([r for r in records if str(r['task_id']).startswith('raw:')])
        if 'database' in p.parent.name:
            entry['pre_migration']=aggregate([r for r in records if r['index']<20])
            entry['post_migration']=aggregate([r for r in records if r['index']>=20])
        runs.append(entry)
    diagnostics=[]
    for p in sorted((ROOT/'runs').glob('diagnostic-*/*/card.json')):
        card=json.loads(p.read_text(encoding='utf-8'))
        available=card['selection']['available'] and all(k in card['branches'] for k in ['normal','related','irrelevant'])
        diagnostics.append({'benchmark':card['benchmark'],'target_index':card['target_index'],'three_branch_complete':available,
                            'selection':card['selection'],'snapshot_unchanged':card.get('snapshot_unchanged'),
                            'normal_correct':card['branches']['normal']['source_result']['correct'],
                            'related_correct':card['branches'].get('related',{}).get('score',{}).get('correct'),
                            'irrelevant_correct':card['branches'].get('irrelevant',{}).get('score',{}).get('correct'),
                            'card':str(p.relative_to(ROOT))})
    report={'at':datetime.now(timezone.utc).isoformat(),'runs':runs,'diagnostics':diagnostics,
            'limits':['One independent repetition per condition; no repeat-stability or significance claim.',
                      'Code primary target results are separate from source tasks and exclude pre-registered scorer defects.',
                      'Database correctness and native cost-sensitive reward are separate.',
                      'No independent-task evaluation; no GG claim. Pilot first pass does not establish long-term retention.',
                      'Full no-memory execution switched after 33 completed tasks to 8 independent workers; latency is confounded by concurrency and cannot rank methods.',
                      'Readonly is a 12-target memory-only subset under user-revised scope, not the complete native second pass.']}
    save(ROOT/'records/results-summary.json',report)
    print(json.dumps({'streams':len(runs),'executions':sum(r['all']['executed'] for r in runs),'diagnostic_targets':len(diagnostics)}))

if __name__=='__main__':main()
