"""Legal action-result fragments for section 6.6 (no fabricated knowledge).

Selection uses dependency metadata and observable historical text, never scores.
This corrects the initial overly restrictive whole-episode diagnostic selector;
the online retrieval baseline and the eight registered targets are unchanged.
"""
import argparse
import json
import re
from core import ROOT,Database,CodeTask,CODE_TOOLS,DB_TOOLS,run_pi,grade_code,save,digest,memory_context
from run_stream import rows_for

def units(episode):
    obj=json.loads(episode['text']);pending=[];result=[]
    for index,item in enumerate(obj['trajectory']):
        if item.get('type')=='toolCall':pending.append((index,item))
        elif 'tool' in item:
            found=next((j for j,(_,call) in enumerate(pending) if call['name']==item['tool']),None)
            if found is not None:
                start,call=pending.pop(found)
                result.append({'indices':[start,index],'items':[call,item]})
    return obj['task'],result

def fragments(episode,required_terms=None):
    task,parts=units(episode)
    choices=[]
    for start in range(len(parts)):
        for end in range(start+1,min(start+8,len(parts))+1):
            chosen=parts[start:end]
            # Preserve exact original order even when one response contains many calls.
            indexed=[(i,item) for unit in chosen for i,item in zip(unit['indices'],unit['items'])]
            indexed.sort(key=lambda x:x[0])
            text=json.dumps({'task':task,'trajectory':[item for _,item in indexed]},ensure_ascii=False)
            if required_terms and not any(t.lower() in json.dumps([item for _,item in indexed],ensure_ascii=False).lower() for t in required_terms):continue
            value={'sequence':episode['sequence'],'text':text}
            size=len(json.dumps([value],ensure_ascii=False).encode())
            if size<=48000:choices.append({'episode':value,'bytes':size,'indices':[i for i,_ in indexed]})
    return choices

def imported_modules(problem):
    return set(re.findall(r'(?:from|import)\s+([A-Za-z_][\w]*)',problem))

def choose(rows,index,history,database):
    target=rows[index]
    if database:
        topics=set(target.get('knowledge_dependencies',[]));tables=set(target.get('tables_involved',[]))
        generic={'SCHEMA_MAP','GROUP_ID','FK_JOINS','DRIFT'}
        stage_start=0 if index<20 else 20
        related=[];unrelated=[]
        for i in range(stage_start,index):
            prior=rows[i];shared=tables & set(prior.get('tables_involved',[]))
            overlap=topics & set(prior.get('knowledge_dependencies',[]))
            specific=(topics-generic)&(set(prior.get('knowledge_dependencies',[]))-generic)
            if shared and overlap and any(t.lower() in history[i]['text'].lower() for t in shared):related.append((len(specific),len(shared),i,shared))
            if not shared and not specific:unrelated.append(i)
        if not related:return {'available':False,'reason':'no earlier same-stage episode with observed relevant table evidence'}
        _,_,rel,terms=max(related,key=lambda x:x[:3])
        basis='same stage, shared required tables actually observed in prior actions/results; includes schema/join experience; relevance is a hypothesis, not guaranteed correctness'
    else:
        rel=next((i for i,r in enumerate(rows[:index]) if r['id']==target['id'] and r['category']=='raw'),None)
        if rel is None:return {'available':False,'reason':'published source episode absent'}
        target_modules=imported_modules(target['problem'])-{'os','sys','unittest','math','typing','collections','random','re','string'}
        unrelated=[i for i,r in enumerate(rows[:index]) if r['id']!=target['id'] and not target_modules.intersection(imported_modules(r['problem']))]
        terms=None
        basis='published source-target dependency; control has a different task identity and disjoint domain-specific imported modules; generic skills may still overlap'
    related_options=fragments(history[rel],terms)
    candidates=[]
    for i in unrelated:
        for fragment in fragments(history[i]):candidates.append((i,fragment))
    matches=[]
    for rf in related_options:
        for i,uf in candidates:
            ratio=uf['bytes']/rf['bytes']
            if .8<=ratio<=1.25:matches.append((rf['bytes'],-abs(1-ratio),-i,rf,uf,i))
    if not matches:return {'available':False,'reason':'no legal paired fragments within fixed 0.8-1.25 byte-length ratio','related_index':rel,'basis':basis}
    # Maximize retained relevant evidence, then minimize length mismatch.
    _,_,_,rf,uf,irr=max(matches,key=lambda x:x[:3])
    return {'available':True,'related_index':rel,'irrelevant_index':irr,'basis':basis,
            'related_fragment':rf,'irrelevant_fragment':uf,
            'length_ratio':uf['bytes']/rf['bytes']}

def run(args):
    database=args.benchmark=='database';rows=Database().rows if database else rows_for('pilot')
    source=ROOT/'runs'/f'pilot-{args.benchmark}-{args.provider}-episodic_retrieval'
    if database:targets=json.loads((ROOT/'records/database-selection.json').read_text())['diagnostic_zero_based_indices']
    else:
        ids={x['id'] for x in json.loads((ROOT/'records/agentcl-selection.json').read_text())['diagnostic_targets']}
        targets=[i for i,r in enumerate(rows) if r['category']=='new' and r['id'] in ids]
    for index in targets:
        prior=source/f'{index:03d}';history=json.loads((prior/'memory-before.json').read_text(encoding='utf-8'));frozen=digest(history)
        selection=choose(rows,index,history,database)
        out=ROOT/'runs'/f'diagnostic-{args.benchmark}-{args.provider}'/f'{index:03d}';out.mkdir(parents=True,exist_ok=True)
        card={'benchmark':args.benchmark,'target_index':index,'source_snapshot':str(prior.relative_to(ROOT)),
              'snapshot_hash':frozen,'selection':selection,'branches':{},'readonly':True,'selector':'diagnostic_fragments_v2'}
        normal=json.loads((prior/'commit.json').read_text(encoding='utf-8'))['result'];injected=json.loads((prior/'injected.json').read_text(encoding='utf-8'))
        if database:db=Database();db.start(index);prompt=db.prompt()
        else:prompt=rows[index]['problem']
        assert digest(memory_context(history,'episodic_retrieval',prompt))==digest(injected)==normal['injected_hash']
        card['branches']['normal']={'reused':True,'source_result':normal,'reason':'same actual snapshot, frozen configuration and normal retrieval'}
        save(out/'card.json',card)
        if not selection['available']:continue
        for branch in ['related','irrelevant']:
            folder=out/branch
            if (folder/'result.json').exists():card['branches'][branch]=json.loads((folder/'result.json').read_text());continue
            if (folder/'events.jsonl').exists():raise RuntimeError('Uncommitted diagnostic attempt requires audit')
            if database:task=Database();task.start(index);tools=DB_TOOLS
            else:task=CodeTask(rows[index],ROOT/'.runtime/workspaces'/f'diagnostic-{args.benchmark}-{args.provider}'/f'{index:03d}'/branch);tools=CODE_TOOLS
            fragment=selection[branch+'_fragment']['episode']
            _,execution=run_pi(args.provider,prompt,history,'episodic_retrieval',task,tools,folder,injection_override=[fragment])
            if execution['error'] and not (execution['response_timed_out'] or execution['context_exceeded']):raise RuntimeError(execution['error'])
            score=task.score() if database else grade_code(rows[index],task.submission or '')
            result={'execution':execution,'score':score,'source_episode':selection[branch+'_index'],'source_indices':selection[branch+'_fragment']['indices']}
            save(folder/'result.json',result);card['branches'][branch]=result
        assert digest(history)==frozen
        card['snapshot_unchanged']=True;save(out/'card.json',card)
        print(json.dumps({'benchmark':args.benchmark,'target':index,'branches':list(card['branches'])}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--provider',required=True,choices=['glm','deepseek']);p.add_argument('--benchmark',required=True,choices=['database','codeeval']);run(p.parse_args())
