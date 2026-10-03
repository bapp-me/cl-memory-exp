"""Section 7.3: read-only evidence joins and proposed diagnostic snapshots.

No model calls, candidate execution, rescoring, memory changes or interventions.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ANALYSIS=REPO/'experiments/section7_analysis_20261003'
OBS=REPO/'experiments/section7_observability_20261002'


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    inputs={}
    def tracked(p):
        inputs[p.relative_to(REPO).as_posix()]=sha(p)
        return read(p)
    tasks=tracked(ANALYSIS/'records/d0-tasks.json')
    summary=tracked(ANALYSIS/'records/d0-summary.json')
    pairs=tracked(ANALYSIS/'records/source-target-pairs.json')
    efficiency=tracked(ANALYSIS/'records/efficiency-pairs.json')
    tracked(ANALYSIS/'records/priority-16-adjudication.json')
    tracked(ANALYSIS/'records/control-36-adjudication.json')
    tracked(ANALYSIS/'records/scoring-surface-audit.json')
    tracked(ANALYSIS/'records/content-state-transitions.json')
    tracked(ANALYSIS/'records/section7.2-completion-audit.json')
    tracked(ANALYSIS/'records/review-audit.json')
    tracked(ANALYSIS/'records/citation-resolution.json')
    tracked(ANALYSIS/'records/babyai-protocol-audit.json')
    final=tracked(OBS/'records/section7.1-final.json')
    cfg=tracked(OBS/'records/complex-confirmed-config-v1.json')
    assets=tracked(OBS/'.cache/agentcl-codeeval.json')
    methods=['no_memory','bounded_icl','episodic_retrieval','mem0','awm','ace']
    by={(x['method'],x['benchmark'],x['scope']):x for x in summary['summaries']}
    base=by[('no_memory','codeeval','all_executed')]
    evidence=[]
    for method in methods:
        full=by[(method,'codeeval','all_executed')];target=by[(method,'codeeval','effective_complex')]
        pair=next(x for x in efficiency if x['method']==method and x['benchmark']=='codeeval')
        cov=next(x for x in summary['source_coverage'] if x['method']==method)
        native=next(x for x in final['summary'] if x['method']==method and x['benchmark']=='codeeval')
        roles=native['all_role_accounting'] or {}
        auxiliary=sum(x['known_usage']['totalTokens'] for role,x in roles.items() if role!='solver') if roles else 0
        evidence.append({'method':method,'effective_complex_correct':target['correct'],'effective_complex_denominator':46,
              'full_code_known_tokens':full['known_usage_subtotal']['totalTokens'],
              'full_code_token_ratio_to_historical_no_memory':full['known_usage_subtotal']['totalTokens']/base['known_usage_subtotal']['totalTokens'],
              'effective_target_known_tokens':target['known_usage_subtotal']['totalTokens'],
              'effective_target_working_tools':target['working_calls'],'paired_improvement_candidates':pair['improvement_candidates'],
              'paired_harm_candidates':pair['harm_candidates'],'source_coverage':cov,
              'auxiliary_known_tokens':auxiliary,'auxiliary_share_of_known_full_tokens':auxiliary/full['known_usage_subtotal']['totalTokens'],
              'level':'D0 descriptive; no causal interpretation'})
    # Chosen after inspecting development data: explicitly NOT a holdout sample.
    selected={
      '767':('H1_candidate','geometry_closed_path','检查裸数/单元素元组、回到起点、空/单点及数值容差；原测试有精确浮点相等，须先确认固定运行时。'),
      '619':('H1_candidate','hex_float_conversion','目标未写字节序；检查合法源示例与可见测试是否足以支撑 network/big-endian 约定，仅对该可核验解释作结论。'),
      '739':('H1_candidate','outlier_statistics','原测试 threshold=4 且期望均无 outlier；先补查可检出离群点、零方差、组索引、方差定义的质量覆盖。'),
      '896':('H1_candidate','dataframe_generation','原断言主要为 shape/columns/row count；先核验单元格确为合法字母、拼接内容与空输入，不用形状通过代替语义正确。'),
      '559':('H2_single_case_candidate','source_column_binding','只诊断固定列名被带入一般 DataFrame 的行为；排序/组合顺序语义另有歧义，不把全题 pass/fail 当唯一机制指标。'),
      '815':('G0_guardrail_only','weak_truthiness_checks','三条 assert 只检查非空；源失败且未注入、目标成功不能证明源没用/系统稳健。暂不进入质量保持主结论。'),
      '983':('G0_guardrail_only','partial_output_checks','测试主要检查四个部门的输出长度，缺合法 level 与输入覆盖检查；不是默认 H1 主样本。'),
      '699':('G0_guardrail_only','stochastic_assertion','题面允许 tie game，测试断言不得 tie；随机断言风险需隔离，不作为默认质量保持证据。'),
    }
    cards=[]
    for tid,(role,family,note) in selected.items():
        task=next(x for x in tasks if x['method']=='episodic_retrieval' and x['benchmark']=='codeeval' and x['task_id']=='new:BigCodeBench/'+tid)
        pair=next(x for x in pairs if x['method']=='episodic_retrieval' and x['target_task_id']==task['task_id'])
        folder=REPO/task['source_path'];state_paths={}
        for name in ['memory-before.json','injected.json','pi-result.json','execution.json','evaluator.json','submission.py']:
            p=folder/name
            if p.exists():
                inputs[p.relative_to(REPO).as_posix()]=sha(p)
                state_paths[name]={'path':p.relative_to(REPO).as_posix(),'sha256':sha(p)}
        asset=assets[task['index']]
        tree=ast.parse(asset['test_code'])
        checks=[ast.get_source_segment(asset['test_code'],n) for n in ast.walk(tree) if isinstance(n,ast.Assert)]
        controls={m:{k:next(x for x in tasks if x['method']==m and x['benchmark']=='codeeval' and x['task_id']==task['task_id'])[k]
                    for k in ['correct','scorable','known_usage_subtotal','working_tool_calls','submit_calls']} for m in methods}
        cards.append({'task_id':task['task_id'],'index':task['index'],'proposal_role':role,'family':family,
              'eligibility':'pending_G0_review_not_execution_approved','audit_requirement':note,
              'source_task_id':pair['source_task_id'],'source_index':pair['source_index'],'source_correct_offline_only':pair['source_correct'],
              'source_injected':pair['source_provenance_injected'],'snapshot_method':'episodic_retrieval',
              'historical_target_correct':task['correct'],'historical_target_turns':task['turns'],
              'historical_target_known_tokens':task['known_usage_subtotal']['totalTokens'],
              'historical_injected_text_bytes':task['injected_text_bytes'],'snapshot_files':state_paths,
              'task_prompt':asset['problem'],'static_assert_count':len(checks),'static_asserts_offline_only':checks,
              'method_outcomes_descriptive':controls,
              'online_visibility_rule':'Only legal before-state and target prompt allowed to solver; scores, assertions, pairing labels and this card stay in offline audit.',
              'selection_note':'Post-hoc development diagnostics, not random sample, not validation, not population estimate.'})
    maincards=[x for x in cards if x['proposal_role']=='H1_candidate']
    assert len(maincards)==4
    hist=sum(x['historical_target_known_tokens'] for x in maincards)
    turns=sum(x['historical_target_turns'] for x in maincards)
    budget={'status':'proposal_only_requires_separate_7.4_authorization','current_turn_model_calls':0,'current_turn_rollouts':0,
            'G0':'Static audit and isolated scorer/contract validation first; no candidate changed or executed in section 7.3.',
            'H1_primary':{'candidate_tasks':[x['task_id'] for x in maincards],'conditions':['R_original_context_current_rerun','C_deterministic_source_only_projection'],
                 'repetitions_per_condition':1,'max_solver_tasks':8,'writer_llm_calls':0,
                 'max_logical_generation_calls':8*18,'conditional_http_envelope_with_two_extra_transport_retries':8*18*3,
                 'max_completion_tokens_per_generation':8192,'conditional_output_token_envelope':8*18*3*8192,
                 'historical_original_four_task_tokens':hist,'two_times_historical_original_tokens_scale_only':hist*2,
                 'historical_original_four_task_turns':turns,'money':None,
                 'limits':'2x historical scale is not a prediction or cap; compact input may change reasoning, tool iterations/cache. Byte guard is not a token cap. Missing usage precludes exact economy claims.'},
            'H2_optional_separate_decision':{'task':'new:BigCodeBench/559','conditions':['raw','raw_plus_generic_check','raw_plus_source_condition_note'],
                 'max_solver_tasks':3,'writer_llm_calls':0,'note':'New matched control; do not reuse H1 or historical execution as contemporaneous control. Single-case diagnostic only.'},
            'H3_H4_H5':'Parked; no additive paid budget. Detailed bounded proposals in hypotheses.json.',
            'freeze_settings_from':str((OBS/'records/complex-confirmed-config-v1.json').relative_to(REPO)),
            'model_proposed':cfg['unchanged_common_settings']['model'],
            'solver_code_budget_proposed':cfg['unchanged_common_settings']['solver_budgets']['code']}
    save(ROOT/'records/evidence-summary.json',{'methods':evidence,'section7.2_historical_commit':'4747aff','model_calls':0})
    save(ROOT/'records/candidate-snapshots.json',{'candidates':cards,'approved_tasks':0,'all_eligibility_pending':True})
    save(ROOT/'records/proposed-budget.json',budget)
    save(ROOT/'records/source-hashes.json',inputs)
    print(json.dumps({'methods':6,'candidate_cards':len(cards),'H1_candidate_tasks':4,'proposed_max_solver_tasks':8,
         'historical_four_task_tokens':hist,'two_times_historical_scale':hist*2,'historical_four_task_turns':turns,'current_model_calls':0,'current_rollouts':0}))


if __name__=='__main__':main()
