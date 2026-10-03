"""Persist primary-agent evidence adjudication; not a human annotation claim.

Findings below were authored after reading all 16 raw task prompts/evaluator
traces, candidate annotations, and selected source/submission/reference excerpts.
Deterministic quote extraction only makes those authored judgments auditable.
"""
from common import *

FINDINGS=[
 (48,'seed_scope','underspecified_candidate','整批仅 seed 一次，参考逐 length 重设；题面未说明。保留 USE_TRANSFER 候选，删除把已注入本身标为 RETRIEVAL 失败的解释。', [('target_prompt','a seed for random generation'),('target_visible','seed once'),('offline_target_reference','combined_counter.update(task_func(length, seed))')]),
 (50,'seed_and_extrema','underspecified_candidate','多组 seed 重设与极小值平局规则在题面未定；choices 子步骤复用不能单独说明这些新增规则。', [('target_prompt','least frequent letter'),('target_submission','least_frequent'),('offline_target_reference','total_counter.update(task_func(length, count, seed))')]),
 (52,'fixed_column_binding','none','目标未限定列名，提交仍使用 item1–item5 并报 KeyError。这是条件适配候选；原始 episode 完整保留，不应把未发生抽象的该次差异解释为压缩损失。', [('target_prompt','multiple DataFrames'),('source_visible',"item_cols = ['item1'"),('target_submission',"item_cols = ['item1'"),('offline_target_evaluation',"KeyError: 'item1'")]),
 (53,'nested_return_shape','underspecified_candidate','源覆盖单图生成，目标新增 rows/cols；提交扁平列表，测试按行再按图遍历。题面层级有歧义，不把源未提供的新条件称记忆遗失。', [('target_prompt','a list of lists containing the points'),('target_submission','all_points.append(points)'),('offline_target_evaluation','for row in points_grid for points in row')]),
 (54,'row_vs_global_rng','underspecified_candidate','源序列扩为 rows*cols 后 reshape，测试要求每行重建。保留适配/契约候选；没有跨项目或过期经验，撤回 SCOPE_INTERFERENCE 的强定位。', [('target_prompt','each cell in the grid follows'),('target_submission','range(rows * cols)'),('offline_target_reference','row = task_func(cols, colors, rng_seed)')]),
 (59,'axes_vs_matrix_return','underspecified_candidate','题面要求返回 heatmap，提交返回 Axes，测试读取矩阵 shape。直接失败点可定位，返回对象契约需要澄清。', [('target_prompt','return a combined heatmap'),('target_submission','return ax'),('offline_target_evaluation',"'Axes' object has no attribute 'shape'")]),
 (61,'horizontal_vs_vertical','explicit_text_tension','题面明确 horizontally，同时写每行对应原句，内部也存在张力；参考 axis=0、断言 (4,11)。先列契约问题，不能把遵循横向要求判为记忆害处。', [('target_prompt','concatenated horizontally'),('offline_target_reference','pd.concat(all_dtm, axis=0, ignore_index=True)'),('offline_target_evaluation','result.shape == (4, 11)')]),
 (63,'per_text_seed','underspecified_candidate','文本扰动子步骤复用，整批 seed 一次与逐文本相同 seed 的隐藏期望不一致；题面未规定重设范围。', [('target_prompt','one for each input text'),('target_visible','global seed once'),('offline_target_reference','return [task_func(text, seed) for text in texts]')]),
 (66,'literal_plot_title','underspecified_candidate','直接失败为标题多出 Overall Trend；题面未提供精确标题，不能把这次失败归因于记忆或回归计算。', [('target_prompt','show the overall trend'),('target_submission','Aggregated Predictions vs Date (Overall Trend)'),('offline_target_evaluation',"Plot title should be 'Aggregated Predictions vs Date'")]),
 (74,'dictionary_input_schema','underspecified_candidate','函数按序列枚举输入，测试传字典；题面只描述多组数据和标识符，未明确 data 容器结构。', [('target_prompt','keys are identifiers'),('target_submission','enumerate(data, start=1)'),('offline_target_reference','for key, value in data.items():')]),
 (81,'leap_boundary_and_time','underspecified_candidate','源使用 >start.year，参考使用 >=given_date.year；还存在分别求 current time 后精确相等的竞争解释，不将边界差异视为唯一根因。', [('target_prompt','until the current time'),('source_visible','LEAP_SECONDS > start.year'),('offline_target_reference','LEAP_SECONDS >= given_date.year'),('offline_target_evaluation','== sum([')]),
 (83,'report_schema','underspecified_candidate','Dataset_1 与测试 Dataset 1 及嵌套键结构不同；题面只要求 summary report。源元组到目标字典的接口变化，不是写入摘要失真。', [('target_prompt','summary report with the details'),('target_submission','Dataset_'),('offline_target_evaluation',"KeyError: 'Dataset 1'")]),
 (84,'empty_list_filling','explicit_text_tension','题面明确填空列表后计算所有值，断言均值 3.5 对应未计填充值；可见冲突比负迁移解释更直接。保留原评分，无重跑。', [('target_prompt','If a list is empty, fill it with SIZE'),('target_submission','random.randint(0, 100)'),('offline_target_evaluation',"'mean': 3.5")]),
 (85,'coordinate_container','underspecified_candidate','目标自选数组转换，隐藏数据为 x/y 字典并报 TypeError；源算法经验不决定新增集合容器。', [('target_prompt','multiple sets of (x, y) coordinates'),('target_submission','np.asarray(data, dtype=float)'),('offline_target_evaluation',"not 'dict'")]),
 (86,'row_index_vs_columns','explicit_text_tension','题面称 indices A/B，参考和检查要求列 A/B；提交形成 2×3 而测试要求 3×2。源文本与通过实现也有同样张力。', [('target_prompt',"with indices 'A' and 'B'"),('source_visible',"pd.DataFrame({'A': a, 'B': b})"),('offline_target_evaluation','DataFrame shape mismatch')]),
 (90,'one_line_vs_each_matrix','underspecified_candidate','题面 single plot 与 across all matrices 未明确线条数量；提交均值一条线而测试要求每矩阵一条。保留契约及聚合适配竞争解释。', [('target_prompt','across all matrices in a single plot'),('offline_target_evaluation','There should be a line for each matrix'),('target_visible','prior PCA task')]),
]


def excerpt(packet,section,needle):
    text=next(s['text'] for s in packet['evidence'] if s['id']==section)
    index=text.find(needle)
    if index<0:raise ValueError(f'{packet["case_id"]}: missing {section}: {needle}')
    # Exact quote; use only the explicitly reviewed needle to avoid misleading cuts.
    return {'section':section,'quote':needle,'char_start':index,'char_end':index+len(needle)}


def main():
    manifest=read(ROOT/'records/manifest.json');results=[]
    for index,category,contract,judgment,evidence in FINDINGS:
        case=next(c for c in manifest['cases'] if c['method']=='episodic_retrieval' and c['benchmark']=='codeeval' and c['index']==index)
        packet=read(ROOT/'packets'/f'{case["case_id"]}.json')
        results.append({'case_id':case['case_id'],'task_id':case['task_id'],'index':index,'diagnostic_category':category,
                        'contract_status':contract,'adjudication':judgment,'evidence':[excerpt(packet,s,n) for s,n in evidence],
                        'reviewer':'primary Codex agent, source-evidence review','human_reviewed':False,'level':'D1 diagnostic judgment; quoted mismatch facts D0','causal_claim':False,
                        'scoring_changed':False,'needs_controlled_intervention':True})
    assert {r['case_id'] for r in results}==set(manifest['priority_16_ids'])
    save(ROOT/'records/priority-16-adjudication.json',{'records':results,'reviewed':16,
         'conclusion':'Complete injection is established; failure labels must first separate added target conditions and contract/test tension from causal memory failure.',
         'limits':['Adjudicator is an AI agent, not a human annotator.','No score changes, reruns or D2 claims.','Contract candidates are not automatic exclusions or proof of test invalidity.']})
    print(json.dumps({'reviewed':len(results),'quotes':sum(len(r['evidence']) for r in results)}))


if __name__=='__main__':main()
