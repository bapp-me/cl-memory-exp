"""Read-only interventions from real episodic stream snapshots.

Candidate selections are researcher-only hypotheses, not oracle answers. Missing
relevant or length-comparable unrelated history is explicitly not evaluable.
"""
import argparse
import json
from core import ROOT,Database,CodeTask,CODE_TOOLS,DB_TOOLS,run_pi,grade_code,save,digest,memory_context
from run_stream import rows_for

def choose_history(rows,index,history,database):
    target=rows[index]
    if database:
        generic={'SCHEMA_MAP','GROUP_ID','FK_JOINS','DRIFT'}
        topics=set(target.get('knowledge_dependencies',[]))-generic
        tables=set(target.get('tables_involved',[]))
        stage_start=0 if index<20 else 20
        candidates=[];unrelated=[]
        for i in range(stage_start,index):
            prior=rows[i]
            overlap=topics & (set(prior.get('knowledge_dependencies',[]))-generic)
            shared=tables & set(prior.get('tables_involved',[]))
            # The actual trajectory must mention a shared table, not just a label.
            if overlap and shared and any(t.lower() in history[i]['text'].lower() for t in shared):
                candidates.append((len(overlap),len(shared),i))
            if not overlap and not shared:unrelated.append(i)
        related=max(candidates)[2] if candidates else None
        basis='same native stage, overlapping specific knowledge labels and tables, shared table appears in actual trajectory; relevance remains an auditable hypothesis'
    else:
        related=next((i for i,r in enumerate(rows[:index]) if r['id']==target['id'] and r['category']=='raw'),None)
        unrelated=[i for i,r in enumerate(rows[:index]) if r['id']!=target['id']]
        basis='published source-target dependency; actual prior source episode exists; its correctness is not assumed'
    if related is None:return {'available':False,'reason':'no observed related history satisfying pre-registered relevance rule'}
    related_bytes=len(history[related]['text'].encode())
    candidates=[i for i in unrelated if .8<=len(history[i]['text'].encode())/max(related_bytes,1)<=1.25]
    if not candidates:return {'available':False,'reason':'no unrelated whole episode within 0.8-1.25 length ratio','related_index':related,'basis':basis}
    irrelevant=min(candidates,key=lambda i:abs(len(history[i]['text'].encode())-related_bytes))
    if len(json.dumps([history[related]],ensure_ascii=False).encode())>48000:return {'available':False,'reason':'related episode exceeds fixed injection budget'}
    return {'available':True,'related_index':related,'irrelevant_index':irrelevant,'basis':basis,
            'related_bytes':related_bytes,'irrelevant_bytes':len(history[irrelevant]['text'].encode())}

def run(args):
    database=args.benchmark=='database'
    rows=Database().rows if database else rows_for('pilot')
    source=ROOT/'runs'/f'pilot-{args.benchmark}-{args.provider}-episodic_retrieval'
    if database:targets=json.loads((ROOT/'records/database-selection.json').read_text())['diagnostic_zero_based_indices']
    else:
        ids={x['id'] for x in json.loads((ROOT/'records/agentcl-selection.json').read_text())['diagnostic_targets']}
        targets=[i for i,r in enumerate(rows) if r['category']=='new' and r['id'] in ids]
    for index in targets:
        prior=source/f'{index:03d}'
        history=json.loads((prior/'memory-before.json').read_text(encoding='utf-8'))
        frozen_hash=digest(history)
        selection=choose_history(rows,index,history,database)
        card={'benchmark':args.benchmark,'target_index':index,'source_snapshot':str(prior.relative_to(ROOT)),
              'snapshot_hash':frozen_hash,'selection':selection,'branches':{},'readonly':True}
        out=ROOT/'runs'/f'diagnostic-{args.benchmark}-{args.provider}'/f'{index:03d}'
        out.mkdir(parents=True,exist_ok=True)
        normal=json.loads((prior/'commit.json').read_text(encoding='utf-8'))['result']
        injected=json.loads((prior/'injected.json').read_text(encoding='utf-8'))
        if database:
            db=Database();db.start(index);prompt=db.prompt()
        else:prompt=rows[index]['problem']
        assert digest(memory_context(history,'episodic_retrieval',prompt))==digest(injected)==normal['injected_hash']
        card['branches']['normal']={'reused':True,'source_result':normal,'reason':'identical recorded starting snapshot, retrieval and frozen configuration'}
        save(out/'card.json',card)
        if not selection['available']:continue
        for branch,key in [('related','related_index'),('irrelevant','irrelevant_index')]:
            folder=out/branch
            if (folder/'result.json').exists():
                card['branches'][branch]=json.loads((folder/'result.json').read_text());continue
            if (folder/'events.jsonl').exists():raise RuntimeError('Uncommitted diagnostic attempt needs audit')
            if database:
                task=Database();task.start(index);tools=DB_TOOLS
            else:
                task=CodeTask(rows[index],ROOT/'.runtime/workspaces'/f'diagnostic-{args.benchmark}-{args.provider}'/f'{index:03d}'/branch);tools=CODE_TOOLS
            _,execution=run_pi(args.provider,prompt,history,'episodic_retrieval',task,tools,folder,injection_override=[history[selection[key]]])
            if execution['error'] and not (execution['response_timed_out'] or execution['context_exceeded']):raise RuntimeError(execution['error'])
            score=task.score() if database else grade_code(rows[index],task.submission or '')
            result={'execution':execution,'score':score,'source_episode':selection[key]}
            save(folder/'result.json',result);card['branches'][branch]=result
        assert digest(history)==frozen_hash
        card['snapshot_unchanged']=True
        save(out/'card.json',card)
        print(json.dumps({'benchmark':args.benchmark,'target':index,'branches':list(card['branches'])}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--provider',required=True,choices=['glm','deepseek']);p.add_argument('--benchmark',required=True,choices=['database','codeeval']);run(p.parse_args())
