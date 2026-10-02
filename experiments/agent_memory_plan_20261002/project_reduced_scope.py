"""Read-only empirical budget projection; no model calls or selection activation."""
from pathlib import Path
import json
import statistics

ROOT = Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

methods = ['no_memory', 'episodic_retrieval']
full = {m: read(ROOT/f'runs/full-codeeval-glm-{m}/summary.json') for m in methods}
pilot = {m: read(ROOT/f'runs/pilot-codeeval-glm-{m}/summary.json') for m in methods}
means = {m: {kind: statistics.mean(x['usage']['totalTokens'] for x in (full[m] if kind == 'raw' else pilot[m]) if x['task_id'].startswith(kind+':')) for kind in ['raw', 'new']} for m in methods}
sunk = sum(x['usage']['totalTokens'] for a in full.values() for x in a)
rows = read(ROOT/'.cache/agentcl-codeeval.json')
prefix_ids = {x['id'] for x in rows[:34]}
eligible = [i for i,x in enumerate(rows) if x['category']=='new' and x['id'] in prefix_ids]
issues = {(x['category'],x['id']) for x in read(ROOT/'records/scorer-issues.json')['issues']}
options = []
for n, probes in [(12,8),(16,8),(24,12),(48,12)]:
    sources = 48 if n == 48 else 34
    selected = list(range(48,96)) if n == 48 else [eligible[round(j*(len(eligible)-1)/(n-1))] for j in range(n)]
    valid = sum((rows[i]['category'],rows[i]['id']) not in issues for i in selected)
    remaining = sum((sources-len(full[m]))*means[m]['raw'] + n*means[m]['new'] for m in methods)
    readonly = probes*means['episodic_retrieval']['new']
    options.append({'tasks_per_method':sources+n,'source_tasks':sources,'target_tasks':n,'valid_targets':valid,'target_indices':selected,'readonly_memory_probes':probes,'remaining_first_pass_executions':2*(sources+n)-sum(map(len,full.values())),'additional_executions_with_probes':2*(sources+n)-sum(map(len,full.values()))+probes,'remaining_first_pass_tokens':round(remaining),'readonly_tokens':round(readonly),'additional_tokens':round(remaining+readonly),'additional_tokens_sensitivity_0_7_to_1_5':[round((remaining+readonly)*.7),round((remaining+readonly)*1.5)],'eventual_tokens_including_sunk':round(sunk+remaining+readonly),'one_target_percentage_points':round(100/valid,2),'rough_standard_error_ratio_vs_full':round((46/valid)**.5,2)})
out={'status':'proposal_only_not_activated','sunk_full_stream_tokens':sunk,'completed_tasks':{m:len(full[m]) for m in methods},'empirical_mean_tokens':means,'estimation':'Full-prefix raw means plus pilot complex-target means. Readonly uses pilot retrieval target mean as proxy, not observed readonly measurement. Sensitivity multipliers 0.7/1.5 are judgment scenarios, not confidence intervals; extremes can exceed them. All input/output/cache-read usage included. Excludes BabyAI, earlier calibration/pilot/diagnostic sunk costs and infrastructure retries. Standard-error ratio is only sqrt sample-size heuristic, not calibrated power for dependent paired tasks.','selection':'Within targets whose own paired source is in first 34 raw tasks, evenly spaced by original index; no correctness-based selection. Preserve all 34 source tasks and selected target order; defective selected tasks execute but are excluded from scoring. Other cross-task dependencies are not proven absent. This changes native stream and exposure history.','options':options}
(ROOT/'records/reduced-scope-projection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
