"""Recheck the concrete evidence used to select three project directions.

These assertions check observations, not universal efficacy or paper novelty.
"""
import hashlib
import json
import re
import sqlite3
from lab_common import ROOT,save_json
from analyze_runs import extract_answer,numeric_answer

def load(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def result(run):return load('results/runs/'+run+'/summary.json')['result']
def answer(run):
    r=result(run);obj=extract_answer(r.get('final_response',r.get('result','')))
    assert obj is not None,run
    return obj['answer']
def inputs(run):return load('results/runs/'+run+'/input.json')
def memory(run,when='memory_after'):
    p=ROOT/'results/runs'/run/when
    return '\n'.join(x.read_text(encoding='utf-8') for x in sorted(p.glob('*.md')))
def visibility(run,fact):
    r=result(run)
    tools=[str(m.get('content','')) for m in r.get('messages',[]) if m.get('role')=='tool']
    return sum(fact in s for s in tools)
def exact(run,expected):
    a=answer(run)
    assert str(a).casefold()==str(expected).casefold(),(run,a,expected)
    return {'run_id':run,'answer':a}

db=sqlite3.connect((ROOT/'.cache/clbench/products.db').resolve().as_uri()+'?mode=ro',uri=True)
prices=db.execute('SELECT COUNT(prc),COUNT(prc_usd),AVG(prc)/100.0,AVG(prc_usd) FROM items_g2').fetchone();db.close()
assert prices[:2]==(6570,6346) and abs(prices[2]-96.2334490106545)<1e-10
scope_runs=['v2-ds-b9-coverage-r1','v2-ds-b9-coverage-r2','v2-glm-b9-own-coverage-r1']
for run in scope_runs:assert abs(numeric_answer(answer(run))-prices[2])<.005
for folder in ['coverage-diagnostic','generic-caution','glm-coverage']:
    text='\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'fixtures'/folder).glob('*.md'))
    assert '96.23' not in text and '52.96' not in text

parent=load('fixtures/mab6k/history-2.json')['sessions']
facts={}
for s in parent:
    for line in re.findall(r'^\d+\. .+$',s['messages'][0]['content'],flags=re.M):facts[int(line.split('.',1)[0])]=(line,s['date'])
atomic=load('fixtures/mab6k/history-atomic-parentdates.json')['sessions']
assert len(facts)==len(atomic)==455
for s in atomic:
    line=s['messages'][0]['content'];serial=int(line.split('.',1)[0])
    assert facts[serial]==(line,s['date'])
assert 'midfielder sp assocFootball' in memory('mab-ds-write2-files-r1')
assert facts[325][0].endswith('association football.') and facts[416][0].endswith('sumo.')

retrieval=[]
for run,expected in [('mab-ds-q0-history-wide-r2','United Kingdom'),('mab-ds-q0-native-wide-r2','United Kingdom'),
                     ('mab-ds-q0-atomic-dates-r1','Belgium'),('mab-ds-q0-files-r2','Belgium'),
                     ('mab-ds-sh50-history-r1','Asia'),('mab-ds-sh50-files-r1','Oceania')]:
    retrieval.append(exact(run,expected))
assert visibility('mab-ds-q0-history-wide-r2',facts[146][0])==0
assert visibility('mab-ds-sh50-history-r1',facts[234][0])==0

writers={'high':'mab-ds-write2-files-r1','low':'mab-ds-write2-files-low-r1','index':'mab-ds-write2-index-matched-r1'}
snapshots=[memory(r,'memory_before') for r in writers.values()]
assert len(set(snapshots))==1
for r in writers.values():
    p=inputs(r)
    assert p['model']=='deepseek-flash' and p['archive_files'] and p['provider_adapter']['max_output_tokens']==32768
    assert p['history_file']==inputs(writers['high'])['history_file']
board={r['run_id']:r for r in load('results/text-memory-scoreboard.json')['runs']}
matched={}
for strategy,writer in writers.items():
    stem={'high':'fullcurate','low':'lowcurate','index':'matched-index'}[strategy]
    readers=[f'mab-ds-q{i}-{stem}-files-r1' for i in [0,3]]
    exact(readers[0],'Belgium');exact(readers[1],'Russellville')
    rows=[board[x] for x in [writer]+readers]
    assert all(r['completed'] and not r['incomplete_usage_requests'] for r in rows)
    matched[strategy]={'writer':writer,'readers':readers,'correct_questions':2,
        'write_output_tokens':rows[0]['usage']['output_tokens'],'write_seconds':rows[0]['seconds'],
        'total_seconds':round(sum(r['seconds'] for r in rows),3),
        'total_cost_usd_range':[round(sum(r['cost_usd_range'][j] for r in rows),6) for j in [0,1]]}
for i,gold in enumerate(['Belgium','Rodez','Italy','Russellville','rugby']):exact(f'mab-ds-q{i}-index-files-r1',gold)
record={'scope':'Small-sample feasibility of three distinct training-free Agent project directions; not universal efficacy or framework ranking.',
    'direction_1':{'prices':{'complete_n':prices[0],'partial_n':prices[1],'complete_mean':prices[2],'partial_mean':prices[3]},
        'scope_corrected_runs':scope_runs,'important_counterevidence':'Generic caution also succeeded; strong consumers sometimes repair the original memory. No significant aggregate negative-transfer effect is claimed.'},
    'direction_2':{'paired_observations':retrieval,'atomic_parent_dates_preserved':True,'new_author_missing_in_failed_tool_results':True,
        'new_continent_missing_in_failed_tool_results':True,'limit':'Single-hop probe selected after mechanism inspection; not a random sample. Existing native file tools are a successful strong baseline.'},
    'direction_3':{'same_initial_memory_sha256':hashlib.sha256(snapshots[0].encode()).hexdigest(),'matched_update_and_read':matched,
        'independent_index_chain_correct':5,'high_writer_stale_claim':{'stored':'midfielder -> association football','newest_source_fact':facts[416][0]},
        'limits':['Two matched reader questions; five questions on the separate index chain.','Common initial-memory construction cost excluded from matched incremental totals.','Raw archives remain accessible. Timing includes API and host overhead.']}}
save_json(ROOT/'results/selection-evidence.json',record)
print(json.dumps({'directions_with_observation_checks':3,'matched_costs':{k:v['total_cost_usd_range'] for k,v in matched.items()},'atomic_same_dates':True}))
