import json
from core import ROOT,save

def main():
    rows=[]
    for benchmark in ['database','codeeval']:
        for model in ['deepseek','glm']:
            for method in ['no_memory','bounded_icl']:
                name=f'calibration-{benchmark}-{model}-{method}'
                data=json.loads((ROOT/'runs'/name/'summary.json').read_text(encoding='utf-8'))
                assert len(data)==(20 if benchmark=='database' else 2)
                rows.append({'benchmark':benchmark,'model':model,'method':method,'tasks':len(data),
                             'correct':sum(x['correct'] is True for x in data),'submitted':sum(x['submitted'] for x in data),
                             'queries':sum(x.get('queries',0) for x in data),
                             'seconds':sum(x['seconds'] for x in data),
                             'tokens':sum(x['usage']['totalTokens'] for x in data),
                             'source':f'runs/{name}/summary.json'})
    report={'rows':rows,'executions':88,'repetitions':1,'matrix':'2 models x 2 simple methods, not 2x3',
            'selected_model':'glm','selected_api_id':'glm-5.3-flash',
            'rationale':[
                'GLM submitted all 44 calibration tasks; DeepSeek submitted 39/44 under the same registered budgets.',
                'Database correctness matched across models: 13/20 No Memory and 15/20 ICL. GLM ICL used 93 SQL queries versus 238 without history, showing history can reduce exploration.',
                'GLM submitted both code tasks in each configuration. DeepSeek exhausted the 8192-token output budget without submitting the complex task in both configurations.',
                'GLM is slower in stateless database calibration (1352 versus 617 seconds), but more reliable at producing submitted artifacts; selected on this tradeoff, not largest accuracy gain.'
            ],
            'limits':['Single repetition; no stability claim.','One code dependency pair is a narrow capability check; both models failed its complex target.',
                      'Selection is conditional on these budgets and thinking=high; does not establish intrinsic model ranking.',
                      'Mem0 confirmation remains deferred to baseline integration as permitted by section 4.1.']}
    save(ROOT/'records/calibration-decision.json',report)
    print(json.dumps({'executions':88,'selected_model':'glm','rows':rows}),flush=True)

if __name__=='__main__':main()
