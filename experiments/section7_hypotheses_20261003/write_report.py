"""Render section 7.3 hypotheses from the frozen evidence and proposal registry."""
from build_evidence import ROOT,read


def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(str(v).replace('\n',' ') for v in row)+' |\n' for row in rows)


def main():
    registry=read(ROOT/'records/hypotheses.json')
    evidence=read(ROOT/'records/evidence-summary.json')['methods']
    cards=read(ROOT/'records/candidate-snapshots.json')['candidates']
    budget=read(ROOT/'records/proposed-budget.json')['H1_primary']
    names={'no_memory':'No Memory','bounded_icl':'受限 ICL','episodic_retrieval':'Jaccard','mem0':'Mem0','awm':'AWM','ace':'ACE'}
    overview=table(['现象','证据支持到哪里','7.3 的处理'],[
      ['Jaccard 27/46 对 18/46；全代码 token 3.91×；有效目标工作工具同为52','D0描述，质量/成本权衡；9个改善含1个无记忆传输故障','优先研究保持质量的低成本表示，不把9个改善视为纯因果收益'],
      ['ICL 45/46 个源包装丢弃','源候选存在但不可见，非检索漏召回','H3包装机制对照，已有Jaccard强简单参照，暂不作为主创新'],
      ['Mem0 91空facts+4原生JSON拒绝','写入稀疏/格式问题是事实，原因为D1','H4适配诊断；不得把内容不存在归为retrieval failure'],
      ['AWM索引47–95 workflow不变，49次字节预算拒绝','当前预算下未更新，不是已证遗忘','H5预算/历史范围诊断，不能冒称该阶段持续online学习'],
      ['ACE全代码6.916M已知token，约50.7%为辅助角色','开销高、部分来源条目预算丢弃','保留强对照；不以复杂程度或helpful计数证明价值'],
      ['16重点失败中15有契约疑点；559固定列名越界较具体','D1候选；只有少量适配行为可直接定位','G0先分契约与机制；H2只作559单例条件适配诊断'],
    ])
    candidate_table=table(['候选目标','用途','Jaccard源通过/注入/目标通过','测评前提'],[
      [c['task_id'].replace('new:BigCodeBench/',''),c['proposal_role'],f"{c['source_correct_offline_only']} / {c['source_injected']} / {c['historical_target_correct']}",c['audit_requirement']] for c in cards])
    sections=[]
    for h in registry['hypotheses']:
        phenomenon=h['phenomenon_and_evidence_level']
        extra=''
        if h.get('representation_specification'):
            extra='\n**C 的构造约束：**\n\n'+''.join('- '+x+'\n' for x in h['representation_specification'])
        if h.get('source_only_note_example'):
            extra+='\n**只依据源的说明示例：** '+h['source_only_note_example']+'\n'
        if h.get('decision_rule_proposed_not_frozen'):
            extra+='\n**建议判断门槛（尚未获批冻结）：** '+h['decision_rule_proposed_not_frozen']+'\n'
        sections.append(f'''### {h['id']}：{h['name']}

**优先级：** {h['priority']}。

| 7.3 必填项 | 分析 |
|---|---|
| 现象与证据等级 | D0：{phenomenon['D0']} D1：{phenomenon['D1_hypothesis']} |
| 适用任务、历史起点与配置 | {h['applicable_tasks_history_and_config']} |
| 主假设与竞争解释 | 主假设：{h['main_hypothesis_and_competing_explanations']['main']} 竞争解释：{'；'.join(h['main_hypothesis_and_competing_explanations']['alternatives'])}。 |
| 唯一改变因素 | {h['single_changed_factor']} |
| 预期改变与不变项 | {h['expected_changes_and_invariants']} |
| 新增调用/预算与停止 | {h['calls_budget_and_stop_rules']} |

**什么结果会反驳或不足以支持：**

{''.join('- '+x+chr(10) for x in h['falsification'])}
{extra}
**主张边界：** {h['claim_boundary']}
''')
    text=f'''# 第 7.3 节：从 baseline 现象形成可证伪假设

日期：2026-10-03（香港时间）。依据第 7.2 节冻结结果（提交 `4747aff`）。状态：**7.3 分析已完成；所有 7.4 分支、阈值与预算均为待确认建议，未启动实验。** 本轮新增外部模型调用、agent rollout、候选代码执行、重评分、memory 写入均为 0。

## 1. 建议优先检验什么

优先主线是 **H1：在源信息和来源覆盖保持不变时，可逆去重的经验表示能否降低总 token，并维持当前任务质量**。先用简单、无 LLM writer 的结构表示建立对照；不要直接跳到新的多层 memory 架构。

H2 把“必要条件虽然存在，却没有在目标适配时得到检查”作为独立诊断，先限定到 559。H3 包装、H4 提取目标、H5 AWM 更新预算有明确可观察现象，但暂作解释/适配对照，不把五个方向同时开发。**选择 H1 是研究优先级判断，不是声称 7.2 已证明压缩有效或输入冗余是唯一根因。**

依据是：Jaccard 在这批任务中有最高正确数与较高对应源覆盖，适合作为强简单参照；成本高却没有有效目标工作工具总量下降，值得首先检验能否降低费用负担。相反，多数失败的契约疑点还没有排除，直接以“会使用经验”为主张容易混入评分问题。

{overview}

举例：同一段代码若先出现在 PYTHON 调用、又原样出现在 SUBMIT，候选去重表示只存一份代码，并让两个有序事件各自引用它；工具结果、错误和发生顺序仍保留。若两版代码不同，就保留两版，不能把“看起来类似”当成精确重复。还原结果相同只是构造检查，模型是否同样读得懂仍需实验。

原始多标签频数不参与“哪一机制最常见”的排序。7.2 中 46 段未匹配引用、源库/实际注入语义混用、BabyAI SUBMIT 误判已经表明，自动标签不是可靠的机制真值。这里优先引用 D0 和逐例复核后的具体事实。

## 2. G0：先确认成败能回答实验问题

G0 是进入干预的条件，不是 memory 创新，也不代表修改旧榜单。

1. 固定保留 7.1/7.2 原始分母、分数、费用与排除项。新的诊断资格表与评分版本独立存放，**不把旧46题悄悄改成另一个分母**。
2. 先核对测试真正调用提交函数。316 的同名覆盖不能作为成功质量证据；954 的无记忆工具故障不能当纯能力失败。这两项不进入拟议主批次。
3. 核对规范、输入、输出与断言是否对齐。存在歧义时保留 pending；必要的契约澄清必须来自公开题意/合法源经验，不能将隐藏参考答案灌进 solver。
4. 核对测试是否检查所声称的质量。若要补性质检查，在看新分支结果之前按规范定义、冻结且放在隔离评分端；原分数与新性质结果并列，不冒称原 benchmark 成绩。
5. 任务进入诊断与否由上述规则决定；已知的源通过/失败、目标历史成败只用于离线分层，不能流入 writer 筛选和检索规则。

### 2.1 本轮静态检查暴露的边界

- `815`：现有三条断言只验证结果非空，不能验证676个 bigram及逐词计数。源失败、未注入、目标通过只能作为**弱评分的警示例**，不作为“坏源没有损害”的因果证据。
- `896`：断言主要验证形状、列名和行数，没有检查单元格是否属于合法字母集。形状通过不够支撑完整质量保持。
- `739`：现有用例 threshold=4 且各组期待无 outlier，还需正离群点、零方差、组索引与方差定义的检查，不能仅靠当前一条复合断言。
- `699`：题面允许平局，测试却断言不得平局，且各次调用重新随机生成。先隔离随机断言风险，暂不作为质量保持样本。
- `619`：目标题未显式说明字节序；来源示例/可见探索可能提供合法约定，但必须核验这一条件，不能只借用隐藏参考的 `!f`。
- `559`：固定列名问题可单独定位，但 tuple是否排序另有语义未定；用“是否仍访问不适用列名”的具体行为指标诊断，不把整个任务pass当唯一机制证据。

这些是新增静态阅读记录，没有执行候选代码或修正原 scorer。[候选任务、实际断言及快照哈希](records/candidate-snapshots.json)

源经验正确性保留为所有假设的竞争解释和离线分层，不另开一条付费实验线：174 的源失败且已注入、269 的源不可评分且已注入，均不能归入“正确经验使用失败”；源通过也不证明每条陈述或所有边界正确。不能用隐藏通过标签筛选在线 writer/检索器。H1 首批限定来源配对通过的候选，同时保留其原选中集合中的所有合法失败/错误记录，不按 gold 清洗记忆。

## 3. 五个可证伪假设

{''.join(sections)}

## 4. 建议的最小 7.4 顺序

```mermaid
flowchart TD
    A[7.2 的 D0 与已复核 D1] --> B[G0 契约和测试覆盖检查]
    B --> C{{候选能支撑预定义质量判断?}}
    C -->|否| D[保留 pending 或只做契约诊断]
    C -->|是| E[无模型可逆去重 fixture]
    E --> F{{可完整恢复且输入确实更短?}}
    F -->|否| G[停止该表示构造，记录无收益]
    F -->|是| H[另行批准 H1 的同期 R/C 分支]
    H --> I[质量、总 token、工具与缓存共同判定]
    I --> J[再决定 H2 或必要长度对照]
```

**只建议先选 H1 小批，不把所有假设的预算相加。** 目前候选四题 `767、619、739、896` 分别覆盖路径距离、字节转换、统计分析、表格生成；包含历史两例 Jaccard/No Memory 都通过和两例描述性改善，全部源通过且已注入。选择已使用开发结果，**不是盲抽样、未见测试或新的独立验证集**。

候选需要 G0 核验后才能冻结为执行清单。若某题不合格，先缩小批次并记录原因，不根据新分支分数挑替代题。本轮没有把任何候选标为已批准可跑。

{candidate_table}

### 4.1 保持同起点

- H1 的 R/C 均从同一任务的 **Jaccard 自己的 memory-before**、同一环境初态与原选中 episode 集开始，每分支新建隔离会话。
- 同期重跑 R，不能拿旧 No Memory 或旧 Jaccard 的一次结果当新 C 的唯一对照。各方法自己历史不同，7.2 的跨方法表也不能充当这个实验。
- 两分支都只读同一冻结历史；不得把前一分支或当前目标的答案、反馈、writer更新带到后一分支或另一目标。候选历史与注入的路径/SHA已登记。
- 建议预先交替 R/C 执行顺序，记录请求顺序、provider返回模型、cache分项与资源配置；不能强称模型随机性或服务端缓存已完全控制。
- 只运行同一冻结 Pi/GLM 配置，保留工具、响应/任务上限、源码和环境版本。DeepSeek 是 7.2 的**审查器**，不因此替换 GLM 主 solver。

### 4.2 计量和判定

对每个任务 i 定义 `Δtokens_i = tokens(C_i) - tokens(R_i)`，工作工具、重复/无效动作、错误后恢复步数、非缓存输入、输出与延迟分别报差，不合成一个混合“效率分”。API cacheRead 是 prompt 的子集，completion 已含 reasoning，不能重复加。具体memory块精确token若仍不可得，就报告可核验的实际请求字节与provider总usage，不估成真值。

完整经济性必须计 `构建 + 读取 + 更新/维护`。本次 H1 建议使用确定性可逆去重，writer LLM 调用为0，但解析/构建CPU耗时、保存量与缓存仍记录；跨多个目标复用的构建费用应计一次并披露摊销次数。实验执行费用包含 R/C 两臂，但部署成本比较不能把 R 的费用也算到 C 方法身上。

建议先采用“当次 C 不比同期 R 新增质量失败”这一保守筛查条件，并同时通过 G0 冻结的性质检查；**四题R=1零下降不等于统计上的非劣性证明**。20% token下降和至少 ceil(0.75*n) 题下降（n为G0后冻结题数，四题时为3题）只是尚未批准的实用门槛，后续执行前可由用户调整；不在看到新结果后改门槛。

只省输入字节但输出/工具开销抵消，不支持总-token经济性；只省totalTokens但非缓存输入或金额增大，不称货币成本更低；质量退化则不能称Pareto改善。无invoice或完整usage时金额/总量保持未知。

### 4.3 调用规模与停止规则

| 项目 | 建议范围及边界 |
|---|---|
| 本轮7.3实际新增 | 0外部模型调用、0 rollout、0重评分、0 memory修改 |
| H1首批 | 最多4题×R/C×1次 = **8个solver任务**；writer LLM=0 |
| 历史量级 | 同四题原Jaccard共 **{budget['historical_original_four_task_tokens']:,} tokens、{budget['historical_original_four_task_turns']} turns**；双倍约 **{budget['two_times_historical_original_tokens_scale_only']:,} tokens**只是参照，不能作为预测或硬上限 |
| 保留原单任务上限时的极端包络 | 8×18=144逻辑生成；如每次最多2个额外传输重试则最多432 HTTP attempts；按8192输出上限计算输出包络3,538,944 tokens。输入另计，320k字节guard不是token上限 |
| 硬预算 | 7.4的总token/金额上限和传输重试策略**尚未确认**；7.0/7.1的历史授权不自动延伸到新实验 |
| H2若后续另选 | 单题3分支=3个solver任务，必须包含新的同期R；不默认叠加到H1 |
| H3/H4/H5 | 暂存，不预付费、不自动扩展；各自小规模提议见注册表 |

G0未通过、C不可逆/不更短、源/输入哈希不符或隔离失败：在模型调用前停止对应构造。运行中出现402、usage缺项影响费用判定、新评分冲突或会突破已批准预算：在安全边界停下并讨论，不无限重试、补题或加独立重复。R/C任一异常都保留，不用重跑后的好结果替换。

若之后修改writer/retriever并声称完整方法更好，必须从相同初始状态重新跑相应完整流；这组只读分叉不能代替它。最终验证/SkillFlow/项目场景仍保留，当前不读取其正式实例来调整假设。

## 5. 如何由结果决定后续方向

| 观察到的结果 | 可以作出的决定 | 不可以作出的结论 |
|---|---|---|
| 可逆表示明显更短，但C质量下降 | 检查引用表示可读性/重复强调价值，拒绝当前保质构造 | 必须改用更大模型或任意扩大预算 |
| C保质且总token下降达到预定门槛 | 保留简单去重为强基线，再讨论额外有损压缩/条件抽象是否有增益 | 当前四题足以证明长期或未见泛化 |
| C字节更短、totalTokens/工具不降 | 当前经济性假设未获支持，保留负结果 | 用输入字节下降包装成总体效率提升 |
| 条件说明S与一般提醒G效果相同 | 不支持“条件内容”特异机制，可能是提醒/额外计算 | 条件模块已证明有效 |
| 包装提高来源可见性但下游不变 | 把覆盖与效用分开，优先简单对照 | 只凭coverage宣布记忆改善 |
| 新提取/新更新只让条目更多 | 只确认写入/可运行性，再评质量与读取效用 | 状态变化就是持续学习质量提升 |
| G0无法形成足够可靠的质量对照 | 先完成基准/契约诊断，必要时收缩本轮主张 | 用未见验证集来补开发失败或静默更换benchmark |

不为完成项目提前命名最终方法。若收益仅来自序列化去重，报告为工程经济性基线，不升格为记忆学习创新；条件抽象或有损压缩是否有额外价值仍需另证。清楚解释基线失效条件的负结果也需要对应证据。

## 6. 产物与完成核对

- [假设注册表](records/hypotheses.json)：G0及H1–H5，逐项覆盖现象、适用起点、竞争解释、唯一改动、预测、反驳、预算/停止。
- [证据汇总](records/evidence-summary.json)、[候选快照](records/candidate-snapshots.json)、[建议预算](records/proposed-budget.json)、[输入哈希](records/source-hashes.json)。
- [完成核对](records/section7.3-completion-audit.json)：只读来源核验及无新调用边界。
- `build_evidence.py` 只解析已有JSON和测试AST；`write_report.py` 从注册表生成本文，不调用模型。

本节完成的是**从现象形成可证伪假设**。尚未完成的不是被省略的7.3实验，而是需另行确定的7.4执行：候选G0验收、确切干预文本/表示、quality/费用硬门槛、分支顺序与停止预算。人类逐条签认、因果证据、重复稳定性与外部验证均未被本分析替代。
'''
    (ROOT/'第7.3节可证伪假设分析.md').write_text(text,encoding='utf-8')
    print(f'Report written: {len(text)} characters')


if __name__=='__main__':main()
