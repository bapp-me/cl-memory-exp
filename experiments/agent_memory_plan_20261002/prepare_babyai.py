"""Verify a complete non-code dependency family with the native AgentBoard wrapper."""
import ast
import copy
import json
import os
import re
import sys
from collections import defaultdict
from urllib.request import urlopen
from core import ROOT,CACHE,save

sys.path.insert(0,str(ROOT/'.runtime/babyai-libs'))
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import numpy as np
import gymnasium
import minigrid

def wrapper():
    path=CACHE/'agentboard/agentboard_environment_babyai_env.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    body=[]
    for n in tree.body:
        if isinstance(n,(ast.Import,ast.ImportFrom)):continue
        if isinstance(n,ast.ClassDef):n.decorator_list=[]
        if isinstance(n,ast.If):continue
        body.append(n)
    ns={'gymnasium':gymnasium,'np':np,'os':os,'re':re,'defaultdict':defaultdict,'BaseEnvironment':object}
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(path),'exec'),ns)
    return ns['BabyAI']

def main():
    url='https://huggingface.co/datasets/osunlp/AgentCL/resolve/a01e2ca6e33fd07d9cf80e4bd69a5b3585d3400f/agentboard_babyai/dependent.jsonl'
    raw=urlopen(url,timeout=40).read()
    (CACHE/'agentcl-babyai.jsonl').write_bytes(raw)
    rows=[json.loads(line) for line in raw.decode().splitlines()]
    group=rows[0]['dependent_group']
    selected=[r for r in rows if r['dependent_group']==group]
    assert len(selected)==8
    BabyAI=wrapper()
    checks=[]
    for r in selected:
        seed=1234+r['occurrence_index']
        env=BabyAI(game_name=r['additional_info']['subtask'],seed=seed,obs_to_reward=copy.deepcopy(r['subgoals']))
        checks.append({'id':r['id'],'seed':seed,'goal_matches':env._get_goal()==r['goal'],
                       'initial_observation_matches':env._get_obs()==r['additional_info']['init_obs']})
        env.env.close()
    manifest={'group':group,'task_ids':[r['id'] for r in selected],'selection':'first group in original dependent stream, all 4 source and 4 target tasks, original relative order',
              'seed_rule':'native AgentBoard base 1234 plus occurrence_index, verified against published initial observations',
              'checks':checks,'ready':all(x['goal_matches'] and x['initial_observation_matches'] for x in checks),
              'wrapper_commit':'bb7255e2daf1989069a186dad9e53f70680961db','minigrid':'2.3.0','gymnasium':'0.29.1',
              'scope':'8-task non-code subset, not full BabyAI coverage','models_called':0}
    save(ROOT/'records/babyai-selection.json',manifest)
    print(json.dumps(manifest),flush=True)

if __name__=='__main__':main()
