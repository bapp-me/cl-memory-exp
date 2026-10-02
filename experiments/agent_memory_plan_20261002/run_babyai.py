"""Native AgentBoard non-code subset, hidden subgoals kept controller-only."""
import argparse
import copy
import json
from core import ROOT,CACHE,run_pi,save,digest,schema
from prepare_babyai import wrapper

class Task:
    max_turns=20
    timeout_seconds=900
    response_timeout_ms=60000
    system_hint='Complete the navigation goal using ACTION. Use "check available actions" when needed. The environment ends the task when the goal is reached. You have at most 20 high-level actions.'
    def __init__(self,row):
        self.env=wrapper()(game_name=row['additional_info']['subtask'],seed=1234+row['occurrence_index'],obs_to_reward=copy.deepcopy(row['subgoals']))
        assert self.env._get_obs()==row['additional_info']['init_obs']
        self.submission=None;self.actions=0
    def tool(self,name,args):
        if self.submission is not None:return {'submitted':True}
        self.actions+=1
        obs,reward,done,info=self.env.step(args['action'])
        if done or self.actions>=20:self.submission='goal reached' if done else 'action budget exhausted'
        return {'observation':obs,'submitted':self.submission is not None}
    def score(self):
        return {'correct':bool(self.env.done),'progress':self.env.reward,'actions':self.actions,'scorable':True}

def run(args):
    manifest=json.loads((ROOT/'records/babyai-selection.json').read_text(encoding='utf-8'))
    assert manifest['ready']
    rows=[json.loads(x) for x in (CACHE/'agentcl-babyai.jsonl').read_text(encoding='utf-8').splitlines()]
    rows=[x for x in rows if x['id'] in manifest['task_ids']]
    root=ROOT/'runs'/f'noncode-babyai-{args.provider}-{args.method}'
    history=[];results=[]
    for index,row in enumerate(rows):
        out=root/f'{index:03d}'
        if (out/'commit.json').exists():
            committed=json.loads((out/'commit.json').read_text(encoding='utf-8'))
            assert committed['before_hash']==digest(history)
            history=json.loads((out/'memory-after.json').read_text(encoding='utf-8'));results.append(committed['result']);continue
        if (out/'events.jsonl').exists():raise RuntimeError('Uncommitted non-code attempt requires audit')
        task=Task(row);before=digest(history)
        prompt='Goal: '+task.env._get_goal()+'\nObservation: '+task.env._get_obs()
        episode,execution=run_pi(args.provider,prompt,history,args.method,task,[schema('ACTION','Perform one native AgentBoard high-level action, including check available actions.','action')],out)
        if execution['error'] and not execution['response_timed_out']:raise RuntimeError(execution['error'])
        result={**execution,**task.score(),'task_id':row['id'],'index':index}
        if args.method!='no_memory':history.append(episode)
        save(out/'memory-after.json',history);save(out/'commit.json',{'before_hash':before,'result':result,'after_hash':digest(history)})
        results.append(result);save(root/'summary.json',results)
        task.env.env.close()
        print(json.dumps({'task':row['id'],'correct':result['correct'],'actions':result['actions']}),flush=True)
    save(root/'final-memory.json',history)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--provider',required=True,choices=['glm','deepseek']);p.add_argument('--method',required=True,choices=['no_memory','bounded_icl','episodic_retrieval']);run(p.parse_args())
