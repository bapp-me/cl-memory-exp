"""Static test-binding audit, prompted by a calibration finding; never rescores."""
import ast
from common import *


def main():
    asset_path=OBS/'.cache/agentcl-codeeval.json';assets=read(asset_path);cases=[]
    final=read(OBS/'records/section7.1-final.json')
    for i,a in enumerate(assets):
        reference=ast.parse(a['problem']+a['solution']);tests=ast.parse(a['test_code'])
        entries={n.name for n in reference.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        redefinitions=[{'name':n.name,'test_line':n.lineno,'test_end_line':n.end_lineno,
                       'source':ast.get_source_segment(a['test_code'],n)}
                      for n in tests.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in entries]
        if redefinitions:
            calls=[{'function':n.func.id,'line':n.lineno} for n in ast.walk(tests)
                   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in entries]
            cases.append({'index':i,'task_id':a['category']+':'+a['id'],'redefinitions':redefinitions,'named_calls':calls,
                          'registered_outcomes':[{k:r[k] for k in ['method','correct','scorable','source_path']} for r in final['results'] if r['benchmark']=='codeeval' and r['index']==i],
                          'level':'D0 static source structure','interpretation':'Frozen grader concatenates submitted code before tests; test top-level def rebinds submitted function before shown target calls. These checks cannot certify the submitted implementation of that function.',
                          'scoring_change':False,'new_rollouts':0})
    save(ROOT/'records/scoring-surface-audit.json',{'assets_scanned':len(assets),'asset_sha256':sha(asset_path),
         'grader_source':'experiments/agent_memory_plan_20261002/core.py:92','grader_sha256':sha(LEGACY/'core.py'),
         'findings':cases,'limit':'Only top-level named function shadowing checked. Absence is not proof of adequate tests. Fixed mask and all original outcomes retained.'})
    print(json.dumps({'assets':len(assets),'shadowed_targets':[x['task_id'] for x in cases],'score_changes':0}))


if __name__=='__main__':main()
