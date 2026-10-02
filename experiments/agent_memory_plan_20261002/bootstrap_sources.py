"""Reconstruct public source inputs at the versions used by this experiment."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent
CL='5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26'
AG='a01e2ca6e33fd07d9cf80e4bd69a5b3585d3400f'
BOARD='bb7255e2daf1989069a186dad9e53f70680961db'

def main():
    assets={
      '.cache/agentcl-codeeval.json':f'https://huggingface.co/datasets/osunlp/AgentCL/resolve/{AG}/codeeval-pro/bigcodebench_lite_pro.dependent.json',
      '.cache/agentcl-babyai.jsonl':f'https://huggingface.co/datasets/osunlp/AgentCL/resolve/{AG}/agentboard_babyai/dependent.jsonl',
      '.cache/agentboard/agentboard_environment_babyai_env.py':f'https://raw.githubusercontent.com/hkust-nlp/AgentBoard/{BOARD}/agentboard/environment/babyai_env.py',
      '.cache/clbench/task.py':f'https://raw.githubusercontent.com/pgasawa/continual-learning-bench/{CL}/src/tasks/database_exploration/task.py',
      '.cache/clbench/src_tasks_database_exploration_prompts.py':f'https://raw.githubusercontent.com/pgasawa/continual-learning-bench/{CL}/src/tasks/database_exploration/prompts.py',
      '.cache/clbench/data_database_exploration_questions.json':f'https://raw.githubusercontent.com/pgasawa/continual-learning-bench/{CL}/data/database_exploration/questions.json',
      '.cache/clbench/data_database_exploration_questions_post_drift.json':f'https://raw.githubusercontent.com/pgasawa/continual-learning-bench/{CL}/data/database_exploration/questions_post_drift.json',
    }
    records=[]
    for relative,url in assets.items():
        path=ROOT/relative
        if not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(urlopen(url,timeout=60).read())
        raw=path.read_bytes();records.append({'path':relative,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    dest=ROOT/'records/source-assets.json'
    if dest.exists():
        if json.loads(dest.read_text())!=records:raise RuntimeError('Existing source hashes differ; do not overwrite freeze')
    else:dest.write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    print(f'Verified {len(records)} source assets; no model calls')

if __name__=='__main__':main()
