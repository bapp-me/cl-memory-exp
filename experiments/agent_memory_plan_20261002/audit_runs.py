"""Audit durable cross-task history and commit chains without additional API calls."""
import json
from core import ROOT,digest,memory_context,save

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    checks=[];errors=[]
    for root in sorted((ROOT/'runs').iterdir()):
        if not (root/'manifest.json').exists():continue
        manifest=read(root/'manifest.json');previous=None
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and p.name.isdecimal()):
            if not (folder/'commit.json').exists():continue
            before=read(folder/'memory-before.json');after=read(folder/'memory-after.json');injected=read(folder/'injected.json');commit=read(folder/'commit.json')
            result=read(folder/'pi-result.json')
            user=next(m for m in result['messages'] if m['role']=='user')
            content=user['content']
            prompt=content if isinstance(content,str) else ''.join(c.get('text','') for c in content)
            current={'run':root.name,'task':folder.name,
                     'before_hash_matches':digest(before)==commit['before_hash'],
                     'after_hash_matches':digest(after)==commit['after_hash'],
                     'retrieval_reproducible':digest(injected)==digest(memory_context(before,manifest['method'],prompt)),
                     'state_chain_matches':previous is None or digest(before)==previous,
                     'no_future_episodes':all(e in before for e in injected)}
            if manifest['method']=='no_memory':current['all_history_channels_empty']=before==after==injected==[]
            elif manifest['readonly']:current['frozen_unchanged']=before==after
            else:
                current['single_legal_episode_append']=len(after)==len(before)+1 and after[:-1]==before
                newest=json.loads(after[-1]['text'])
                current['episode_schema_excludes_evaluator']=set(newest)=={'task','trajectory'}
            checks.append(current)
            if not all(v for k,v in current.items() if k not in ['run','task']):errors.append(current)
            previous=digest(after)
    report={'commits_checked':len(checks),'errors':errors,'passed':not errors,'checks':checks,
            'limits':['Checks explicit persisted state and deterministic selection; not a proof against every possible provider-side implementation.']}
    save(ROOT/'records/state-audit.json',report)
    print(json.dumps({'commits_checked':len(checks),'passed':not errors,'errors':errors}))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
