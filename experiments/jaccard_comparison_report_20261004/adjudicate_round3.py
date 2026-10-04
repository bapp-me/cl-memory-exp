"""Record primary-agent evidence checks, not human truth or new counterfactuals."""
from common_report import *
import json

NOTES={
48:('limited_support','读取对应源可核验；一次seed与每次调用重设seed的差异确实存在，但复杂题题面未明确跨字符串随机状态，不能把评分差异唯一归因于误用记忆。'),
49:('score_validity_limit','GLM原文标为一致适配/无失败，但JSON不合格；测试重新定义new_task_func，保留原通过分数，不据通过或模型标签证明迁移成功。'),
53:('no_search_not_failure','无动态记忆调用且目标通过，支持不搜索不等于检索失败；启动索引已可见，不能称完全无记忆反事实。坏JSON的标量值不等于引用审核通过。'),
59:('contract_candidate','一读一执行、当前无工具错误；Axes与矩阵返回期望的张力可核查。相比旧版11次执行，成本下降不能全部解释为检索优化。'),
62:('behavior_only','对应源曝光和多样本扩展行为可核验；观察到相似代码不证明记忆不可替代，建议无记忆反事实并未实际执行。'),
69:('reject_hidden_contract_retrieval_fix','评审自己指出ValueError仅由隐藏测试规定，却建议额外搜索异常约定。其他历史的异常类型不能建立当前任务契约；拒绝据此把正确异常检索当已知可修复方案。'),
72:('behavior_only','相关源和另一份相近源的读取可核验；第二次读取是否是必要对照不能由最终成功判定，GLM的上下文确认解释仅为候选。'),
73:('downgrade_source_quality','对应基础源的correct=null且scorable=false；GLM原文仍给pass_with_limits。来源质量应保留未知/资产问题，不能将43个该标签当43个真实通过源。'),
80:('recoverable_error_observed','目标43在本轮有2次Python、1个错误观察后通过；宽grep与续读可核验。直接读是否同样成功且更便宜没有反事实，不能把可避免开销标签视为已证节约。'),
84:('falsifier_already_met','GLM把mode形式和读取截断列为主要缺失，并把均值不可能作为反驳条件。题面填5个整数后总11个整数，测试却要求均值3.5（总和38.5），矛盾已在原证据成立；补读不能解决该断言，不能报告为单纯检索失败。'),
89:('contract_candidate','读取s024后返回tuple，而评分访问Axes.collections导致AttributeError；题面未明确返回类型，保留契约候选，不声称多读即可修复。'),
92:('observed_gain_not_causal','本轮通过而Jaccard失败；一次对应源读取与一次Python验证可核验。只能称一次成功增益，不能凭相似实现或一次结果证明稳定因果收益。')}

def main():
    data=read(ROOT/'records/report-data.json');audit=read(ROOT/'records/review-audit-round3.json');rows=[]
    for index,(status,note) in NOTES.items():
        metric=next(r for r in data['rows'] if r['method']=='compact_r3' and r['index']==index)
        review=next(r for r in audit['rows'] if r['index']==index)
        packet_path=ROOT/'packets/round3'/f'report-r3-{index:03d}.json';packet=read(packet_path)
        folder=REPO/metric['source_path'];files=[folder/'pi-result.json',folder/'evaluator.json',packet_path]
        checks=[]
        if index==49:
            section=next(s for s in packet['evidence'] if s['id']=='target_contract_reference_offline')
            assert 'def new_task_func(' in json.loads(section['text'])['tests'];checks.append('Hidden tests redefine submitted function')
        if index==73:
            source=json.loads(next(s['text'] for s in packet['evidence'] if s['id']=='source_evaluation_offline'))
            assert source['correct'] is None and source['scorable'] is False;checks.append('Source quality is not verified pass')
        if index==84:
            prompt=next(s['text'] for s in packet['evidence'] if s['id']=='target_prompt')
            tests=json.loads(next(s['text'] for s in packet['evidence'] if s['id']=='target_contract_reference_offline'))['tests']
            assert 'random integers' in prompt and "'mean': 3.5" in tests and "'b': []" in tests
            assert 11*3.5!=int(11*3.5);checks.append('11 integer values cannot have mean3.5')
        if index==89:
            evaluation=read(folder/'evaluator.json');submission=(folder/'submission.py').read_text(encoding='utf-8')
            assert "'tuple' object has no attribute 'collections'" in evaluation['stderr']
            assert 'return labels_list, axes_list, combined_ax' in submission;files.append(folder/'submission.py');checks.append('Tuple/Axes contract failure')
        rows.append(dict(index=index,task_id=metric['task_id'],status=status,note=note,correct=metric['correct'],source_exposed=metric['source_exposed'],
            python_calls=metric['python_calls'],memory_calls=metric['memory_calls'],error_observations=metric['error_observations'],
            review_json_parseable=review['parsed'],checks=checks,evidence_hashes={p.relative_to(REPO).as_posix():sha(p) for p in files}))
    save(ROOT/'records/primary-adjudication-round3.json',dict(reviewer='Primary Codex agent; not human labels',selection='12 purposive independent targets: contract issues, source-quality ambiguity, no-search control, gains/losses, business-execution outlier',
        records=rows,model_calls=0,no_raw_review_or_score_rewrites=True,scope='Evidence checks, not independent experimental counterfactuals'))
    print('Recorded 12 AI evidence checks with source hashes; no model calls.')

if __name__=='__main__':main()
