"""Publish bounded, reproducible observations; never infer unavailable metrics."""
from datetime import datetime,timezone,timedelta
from collections import Counter
from prepare import ROOT,read,save

METHODS={'pi_none':'Pi No Memory','pi_notepad':'Pi Notepad','pi_jaccard':'Pi Jaccard',
         'claude_memory_ready':'Claude Code','codex_memory_ready':'Codex','hermes_memory_ready':'Hermes'}
ENVS={'database_exploration':'Database','codebase_adaptation':'Codebase'}
METRICS={'faithfulness':'写入忠实性','relevance':'曝光内容相关性','applicability':'适用条件/时效',
         'organization':'写入组织质量','visible_reuse':'可观察行为对应','repetition_efficiency':'重复操作合理性','compression_retention':'压缩保留'}


def pct(v):return '未知/不适用' if v is None else f'{v:.1%}'
def number(v):return f'{v:,}' if isinstance(v,int) else str(v)
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def main():
    s=read(ROOT/'records/full-analysis-summary.json');life=read(ROOT/'records/full-lifecycle-metrics.json')
    retrieval=read(ROOT/'records/full-retrieval-details.json');quality=read(ROOT/'records/judge-quality-spotcheck.json')
    mechanical=read(ROOT/'records/full-mechanical-task-metrics.json');rel=s['reliability'];cost=s['new_provider_calls']
    finished=s['status']=='complete' and rel.get('valid_repeat_packets')==26 and not cost['phase_counts'].get('started',0)
    coverage=[
        ('官方评分、动作、reward、迁移前后/仓库分段、同题配对','代码','已完成，353 题有分数；1 题中止不补零','RESULTS_FINAL.md'),
        ('原实验全批次 attempts、缓存、未知 usage、旧题/恢复/中止成本','代码','已完成；按唯一 attempt，不将原生计数重复相加','records/final-closure-audit.json'),
        ('角色用量归因','代码','Codex 提取/整合可辨；其余原生请求部分只能按提交前后分组','records/full-mechanical-task-metrics.json'),
        ('会话隔离、任务交接、维护水位、持久化终态','代码','353 道已评分题验证；中止题独立处理','records/final-closure-audit.json'),
        ('记忆体积、类型、变化、相同文件/段落','代码','已统计；Pi 是状态负载，原生是文件负载，不等于同口径磁盘占用','records/full-mechanical-task-metrics.json'),
        ('维护触发/NOOP/staged、作业、已知等待及恢复时长','代码','已提取最终原生状态；缺字段或缺原端到端时长仍为未知','records/full-lifecycle-metrics.json'),
        ('子 agent/原生 job 数与父会话','代码','可取字段已统计；并非所有框架都有统一完整 actor 图','records/full-lifecycle-metrics.json'),
        ('工具调用、精确重复、搜索/读写词法分类','代码','已统计；精确重复不等于无效操作，词法标签不等于实际执行效果','records/full-mechanical-task-metrics.json'),
        ('前题内容实际曝光','代码','长行精确匹配提供保守下界；不等于完整读取范围或真实依赖','records/full-mechanical-task-metrics.json'),
        ('Jaccard 候选、排名、top-3、跨仓库/迁移选择','代码','59 次选择与原记录逐项复算；951 个候选-目标对','records/full-retrieval-details.json'),
        ('写入忠实性、相关性、适用条件、组织质量','LLM judge','按证据包评审，unknown 与 N/A 单列','records/full-semantic-task-labels.json'),
        ('可观察复用、重复操作合理性、误用/过时风险','LLM judge','D1 解释；需要可定位原文，不宣称因果','records/full-semantic-task-labels.json'),
        ('候选相关性及 precision/recall/nDCG','LLM judge + 代码','LLM 参考标签；仅完整且全部已知的候选集合进入指标','records/full-retrieval-details.json'),
        ('返回内容抽查、逆序证据复核一致性','人工式证据核对 + LLM','当前助手抽查，不是独立人类金标；复核含提示澄清版本差异','records/judge-quality-spotcheck.json'),
        ('压缩后是否保留关键约束','需前后上下文 + LLM','没有捕获到可比压缩前后对；不能补造数值，也不能证明从未压缩','records/full-mechanical-summary.json'),
        ('记忆造成提升/退化、子 agent 因果收益、批处理因果节省','需新干预实验','按用户选择未验证，不追加重跑','records/full-analysis-authorization.json'),
        ('Aixoras 实际账单金额、未知请求真实用量','服务端账单','账单/价目未取得；未知不填零，不套用旧 Z.AI 价格','records/full-analysis-summary.json')]
    save(ROOT/'records/full-metric-coverage.json',{'as_of':s['as_of'],'items':[dict(zip(['metric','method','status','evidence'],r)) for r in coverage]})
    lines=['# CL-Bench：全量观测与记忆语义分析',
        f"更新：{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M HKT')}。状态：{'已完成本轮可观测分析' if finished else '分析进行中，以下汇总随有效结果更新'}。",
        '本实验让六套 agent 系统依次处理数据库或代码任务，每题使用新会话，允许读取各自前题形成的记忆。两种环境彼此隔离。本报告分析既有记录：记忆写了什么、被看到了什么、行为是否与之对应，以及相关成本。原业务评分保持不变，见[执行结果](RESULTS_FINAL.md)。',
        f"共分析 354 个任务单元（353 已评分＋1 中止），拆为 426 个任务证据包和 84 个候选相关性包。当前通过验收 **{s['valid_packets']}/510**，失败待处理 {len(s['failed_packets'])}，尚无当前有效结果 {len(s['pending_packets'])}；逆序复核有效 **{rel.get('valid_repeat_packets',0)}/26**。每个 unknown 都表示证据不足，不能换算为 0 分。",
        '## 直接观察到的结果',
        '- **Claude Code 的 Codebase 没有形成持久记忆文件。** 19 题均为 completed_noop；其 17/19 业务成绩不能作为“该流跨会话记忆带来提升”的证据。Database 则有 31 个 changed、9 个 noop，说明同一框架在两个环境的写入行为不同。',
        '- **Codex 的主要可辨记忆成本来自整合。** 提取与整合均有原生记录；输出上限不等于实际生成量。实验取消原生等待并保留前期逐题、后期批次混合节奏，这些成本不代表日常默认 Codex。',
        '- **Jaccard 会带入条件不匹配的历史。** Codebase 51 次历史选择中 19 次来自另一仓库；Database 迁移后的 60 次选择中 37 次来自迁移前。它们是曝光组成，不自动等于错误或负迁移。',
        '- **语义审查发现具体的边界问题。** 例如 Hermes Database 第 9 题前的技能把时间戳统一描述为毫秒，当前 g3 样本却是 TEXT 日期；本题随后更新了分组条件。Claude Database 第 1 题则从一次判错推导出广泛的时间戳处理规则，其隐藏评分机制并未被证实。这些是可复核案例，不是机制的因果排名。',
        '## 指标覆盖与无法回答的部分',table(['指标','计算方式','覆盖/边界','证据'],[(a,b,c,f'[{d}]({d})') for a,b,c,d in coverage]),
        '## 记忆规模与维护行为',
        '下表“变化题数”是快照内容变化，可能包括追加原始 episode、恢复或阶段性文件，不能直接当作 writer 作业次数。“曝光题数”只计长度至少 60 字符的前题记忆行在提交前实际模型请求中精确出现，是保守下界。Pi 的体积取规范化状态负载；原生体积取纳入记忆快照的文件负载。两者均非整个 home 的磁盘占用。',
        table(['环境','方法','单元','内容变化题','长行曝光题','题前负载峰值 B','末快照分类'],
            [[ENVS[g['environment']],METHODS[g['method']],g['tasks'],g['content_changed_tasks'],g['long_line_exposure_tasks'],number(g['before_memory_bytes_max']),
              '; '.join(f"{k}: {v['bytes']:,} B" for k,v in (g['last_after_memory_categories'] or {}).items())] for g in s['groups']]),
        '![记忆负载轨迹](figures/full-memory-payload.png)',
        'Notepad 的对错反馈是独立的 previous_feedback 字段，不含在 notepad 文本字节数中；其交接已单独核对。Jaccard 原始历史、Codex 提取源/摘要、Hermes skills 与 notes 的用途不同，不应凭总字节数断言谁更有效。相同段落可来自有意的多层索引，语义冗余必须另看。',
        '曝光最初按提交前所有可取 provider 输入匹配；对原生系统仍需区分主会话与后台角色。Hermes 58 道已评分题的 1,790 条曝光长行中，1,724 条可由响应工具调用 ID 与主会话记录对应；剩余 66 条分布在 Codebase 第 11、19 题，角色未确认。两题的 judge 材料已把这些行从主求解者可见记忆中分离，只允许已确认子集用于当前任务的相关性/适用性/复用判断。中止题不在这项主会话佐证内。详见[角色核对](records/long-line-exposure-role-audit.json)。',
        table(['环境','方法','最终屏障状态','已知维护秒数','维护时长未知题'],
            [[ENVS[g['environment']],METHODS[g['method']],str(g['barrier_statuses']),f"{g['maintenance_seconds_known_sum']:.1f}" if not g['method'].startswith('pi_') else '不适用',g['maintenance_seconds_unknown_count'] if not g['method'].startswith('pi_') else '无独立异步维护'] for g in life['groups']]),
        '这些时间之和不是批次墙钟时间。恢复题缺失的原耗时保留未知，恢复片段另列。Claude 原生统计报告两种环境均 0 个 spawned 子 agent；Codex 59 题均有非空阶段一输出；Hermes 最终作业记录在 Codebase 为 25 个、Database 为 40 个，其中 Database 9 个旧作业没有完整 review_scope 字段。作业数、调用数、写文件次数是不同量，不能相加。',
        '## 各角色的原实验用量',
        '这里只展示能够可靠辨识的 Codex 提取与整合角色。其他角色详见逐题记录中的 cost_roles；原生提交前/后未归因项不能直接改名为 solver/writer。',
        table(['环境','角色','attempts','已知 tokens','usage 未知'],
            [[ENVS[g['environment']],role,v['attempts'],number(v['known_tokens']),v['unknown_usage']] for g in s['groups'] if g['method']=='codex_memory_ready' for role,v in g['cost_roles'].items()]),
        '原实验全部 5,642 个 attempts 的已知总量为 99,325,232 tokens，31 个 usage 未知，包含中止题、被替代旧题和验收成本。本报告新增 judge 成本另列，绝不混入原系统效率比较。',
        '## 七项语义评审',
        '评分标准为 0/1/2，另有 unknown 和 not_applicable。任务可能拆成多个包；下表只是该任务的已评片段中出现何种标签：任一 0 → I，否则任一 1 → M，否则出现 2 → P，随后为 U 或 N。P 不代表整题所有记忆都好，I/M 也不自动等于造成业务失败。长记忆被切包后，部分来源不在同包会增加 unknown，不能把各框架的标签直接当公平完整的标量排名。',
        '表内顺序为 **P/M/I/U/N/未评**：出现 2 分、出现 1 分、出现 0 分、未知、不适用、无有效评审。各指标的 0 分含义不同；例如可观察复用的 0 仅表示未找到显式联系，不等于坏记忆或负迁移。']
    label_order=['positive_evidence_observed','observed_mixed','observed_issue','unknown','not_applicable','not_judged']
    lines.append(table(['环境','方法','完整包覆盖任务']+list(METRICS.values()),
        [[ENVS[g['environment']],METHODS[g['method']],f"{g['all_task_packets_valid']}/{g['tasks']}"]+
          ['/'.join(str(g['semantic_metric_counts'][m].get(k,0)) for k in label_order) for m in METRICS] for g in s['groups']]))
    lines.extend(['“可观察行为对应”要求前题可见记忆与本题动作证据；相同命令也可能来自模型原有知识或本题提示，仍不证明心理依赖或因果贡献。所有压缩保留项不适用/未知仅反映缺少可比材料，不证明框架从未压缩。',
        '## Jaccard 检索相关性',
        '59 次原始 top-3 选择已逐项复算一致，候选共 951 对（Database 780、Codebase 171）。第 1 题没有历史，因此 57 道目标进入候选评审。相关性 1 表示背景/部分帮助，2 表示直接可迁移细节。检索选择对候选 judge 隐藏；这是同模型生成的参考标签，不是人类金标。',
        table(['环境','参考阈值','完整标签目标 / 有候选目标','宏平均 precision','宏平均 recall','recall 有定义目标'],
            [[ENVS[g['environment']],'>= '+t,f"{v['tasks_complete_labels']}/{g['tasks_with_candidates']}",pct(v['macro_precision']),pct(v['macro_recall']),v['recall_defined_tasks']] for g in retrieval['groups'] for t,v in g['thresholds'].items()]),
        table(['环境','已选择 / 全候选对','完整标签目标','nDCG@k（相似度顺序）','nDCG 有定义目标'],
            [[ENVS[g['environment']],f"{g['selected_pairs']}/{g['candidate_pairs']}",g['all_semantic_labels_known_tasks'],f"{g['mean_ndcg_at_k_jaccard_rank']:.3f}" if g['mean_ndcg_at_k_jaccard_rank'] is not None else '未知',g['ndcg_defined_tasks']] for g in retrieval['groups']]),
        'precision = 选中且相关 / 选中数；recall = 选中且相关 / 全候选相关数。候选无相关项时 recall 无定义；有 unknown 时该题不进入这些均值。nDCG 用 2^score−1 增益、按 Jaccard 排名计算，实际输入按历史时间排序，两种顺序不能混为一谈。微平均、分母、每题标签与跨条件选择详见 [检索明细](records/full-retrieval-details.json)。',
        '## Judge 返回质量与一致性',
        f"已核对 {quality['case_count']} 个有意选取的案例，覆盖六种方法、两类环境、候选检索和写入/使用判断。核对者是本聊天助手，不能称为独立人工金标或据此估计总体准确率。完整记录见[内容抽查](records/judge-quality-spotcheck.json)。",
        '发现并处理的问题包括：空 JSON；字段/候选覆盖错误；引用不在原文；把当前新计划当作跨题记忆；把来源缺失当作差质量；解释中带未经证实的因果措辞。原响应和全部费用保留，不手改分数。引用校正仅允许可逆 JSON 显示变换、同源片段定位，或在所给材料中唯一命中的逐字原文定位；不把改写句变成证据。',
        'Notepad 的输入证据曾遗漏独立反馈及写入时序，已对 59 个单元补全并作废旧包对应判断。引用当前记忆与动作的验收要求也已统一补查；不能因 HTTP 200 就认为内容合格。自由解释仍可能有过度措辞，报告仅采用经核对的有界事实，不原样传播因果断言。',
        f"逆序复核覆盖 {rel.get('valid_repeat_packets',0)}/26 个有效包，共 {rel['comparisons']} 个可比较条目。包含 N/A 的状态＋分数一致率为 {pct(rel['exact_agreement_rate'])}；双方均可评分的 {rel.get('both_assessed_comparisons',0)} 项分数一致率为 {pct(rel.get('both_assessed_score_agreement'))}；至少一方可评分的 {rel.get('either_assessed_comparisons',0)} 项状态＋分数一致率为 {pct(rel.get('either_assessed_status_score_agreement'))}。",
        '复核使用同一模型，并逆转证据文档顺序；实际执行跨越了格式/证据要求澄清版本及重试反馈，属于运行条件敏感性检查，不能当成控制变量完备的纯随机复测，更不是正确率。N/A 很多会抬高总体一致率，因此另报可评分子集。',
        '## 新增分析成本与并发',
        f"Aixoras glm-5.3-flash 已记录 {cost['attempts']:,} 个实际请求，终态分布 {cost['phase_counts']}；无 usage 的 {cost['unknown_usage_attempts']} 个请求保留未知（包含仍在途者）。原始 usage 字段各自求和：输入 {cost['raw_reported_usage_totals']['input_tokens']:,}，输出 {cost['raw_reported_usage_totals']['output_tokens']:,}，provider total {cost['raw_reported_usage_totals']['total_tokens']:,}。有 {len(cost['usage_arithmetic_discrepancies'])} 次返回不满足 input+output=total，保留原值，不强行修平。实际金额未知，不套旧 Z.AI 价目。",
        '75 并发试跑实际峰值为 75，没有观察到 429。该 25 包试跑共 40 次请求，35 次 HTTP 200、5 次 HTTP 524；终态耗时中位数 81.7 秒。包大小和组成不同，不能把此数与先前 50 并发批次直接解释为加速比，也不能当作服务商最大容量。按用户要求，5xx 留痕并重试，不作为自动降低并发的理由。后续目标总并发保持 75，实际在途量随尾批完成而下降。',
        f"关键原始证据的 {s['frozen_evidence']['files_verified']} 个文件哈希核对未变。新 key 只保存在忽略追踪的加密本地文件；请求、响应、完整轨迹和衍生证据包留在私有分析区，报告不回写被测 memory。",
        '逐请求的无正文用量记录见 [新增 attempt 台账](records/analysis-attempt-ledger.json)，HTTP、耗时、重叠与原始 usage 核对见[调用审计](records/analysis-call-audit.json)。返回 model 字段作为接口身份记录，不能证明服务商未公开的内部实现。',
        '## 复算与解释边界',
        '所有指标的机器可读索引见 [覆盖清单](records/full-metric-coverage.json)。原始分数与因果范围不因 judge 判断而改变。跨框架比较仍受不同执行器、混合输出预算、Codex 混合整合节奏、R=1 和一个中止题限制。',
        '离线复算（不会调用模型）：',
        '```powershell\n.local/clbench-venv/Scripts/python.exe -X utf8 summarize_full_analysis.py\n.local/clbench-venv/Scripts/python.exe -X utf8 analyze_native_lifecycle.py\n.local/clbench-venv/Scripts/python.exe -X utf8 analyze_retrieval_details.py\nD:/anaconda3/python.exe plot_full_analysis.py\n.local/clbench-venv/Scripts/python.exe -X utf8 write_full_analysis_report.py\n```',
        'full_analysis.py 可重新提取全部证据并自动补入 Notepad 时序；有 judge 请求在途时禁止重建。judge_full_analysis.py 是付费入口，本报告复算不需要运行它。'])
    (ROOT/'FULL_ANALYSIS.md').write_text('\n\n'.join(lines)+'\n',encoding='utf8')
    print({'report':'FULL_ANALYSIS.md','finished':finished,'valid_packets':s['valid_packets']})


if __name__=='__main__':main()
