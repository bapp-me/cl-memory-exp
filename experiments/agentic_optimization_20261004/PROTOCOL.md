# 五方案细致分析与最多三轮 agentic search 优化

日期：2026-10-04，香港时间。直接授权来自本聊天的新 goal：阅读旧 v1.5 第 7 节、用 GLM 5.3 Flash 替换旧 DeepSeek reviewer 分析五种新方案，然后自主提出/验证 agentic search 优化，最多三轮全量复杂题验证，第三轮后终止实验。此前用户已明确运行配置无需再次确认。

## 依据与范围

读取的旧计划是当前指导文档明确引用的 Git revision `0571ff586f818a6a20b142edb3f3ad2cd2a85cd4`；[完整第 7 节快照](records/v1.5-section7.md)及哈希已保存。重点采用 7.2.1 的三维框架、7.2.2 的证据等级、7.2.3 的获取方式；旧文中其他 benchmark、Hermes 切换、在线 writer 和旧审批流程不自动恢复。

| 维度 | 本轮要求 | 证据 |
| --- | --- | --- |
| 结果状态 | success / scorable_failure / asset_unscorable / infrastructure_interruption / protocol_invalid / observation_missing / unfinished | 原始评分、提交、终态；不改原 mask |
| 机制标签 | 沿用全部 12 类：EVAL_CONTRACT、INFRA_PROTOCOL、TASK_EXECUTION、OPPORTUNITY_SOURCE、WRITE_ADMISSION、REPRESENTATION、RETRIEVAL、PACKING_VISIBILITY、USE_TRANSFER、UPDATE_RETENTION、SCOPE_INTERFERENCE、COST_UTILITY | 具体源文本、查询/候选、返回与实际请求、动作和评分引用；多标签不相加当失败题数 |
| 证据等级 | D0 直接记录/可核验推导；D1 GLM 或主 agent 带引用的解释；新运行单独描述干预及局限 | GLM 标签不升级为因果真值；R=1 不证明稳定优势或统计非劣 |

固定库不研究写入和遗忘，WRITE_ADMISSION / UPDATE_RETENTION 通常为 not_applicable，不能机械套入失败分类。源题通过不验证它的所有经验；未搜索不等于本应搜索；源码相同、打开文件和 provenance 均不证明语义使用。

## 初始五方案分析

机械分析全量覆盖 240 次真实运行。除成败、tokens/cache、工具、终态、延迟与错误，还测量：主动访问时机、query/command 重复、无命中、截断、实际返回中正文与非正文的序列化字节、常驻索引在各请求中的累计字节、动态证据累计重放字节、源范围重叠，以及 corresponding source 的曝光/打开区别。

这些字节指标不冒充 token；非正文也可能是必要导航信息。终端脚本变换后的精确源字符归因、逐条记忆 token/cache、真实 recall 与因果收益依旧不可由日志直接得到。

本次用户明确要求对五种新方案做细致指标分析，因此**初始语义审查全量 240 条**，包括两个不可评分目标在每版的访问行为；不以质量筛选样本。它扩于旧文“后续默认最多 12 个独立目标”的抽样方案，已在当前运行 manifest 中明示，不伪装成旧预算内复用。后续优化轮恢复最多 12 个独立目标的定向语义审查，不每轮重做全量。

Reviewer 固定 `glm-5.3-flash`，high thinking、temperature=1、max_tokens=24000、JSON 输出，并发最多 48；保持旧四项语义判断与 12 类标签，增加搜索策略、失败边界、读取效率三个有证据的候选字段。复用旧 reviewer 提示规则，输入增加行号以便检查引用。不是新的 reviewer 选型比赛，不调用 DeepSeek，不生成隐藏思维链。

首条计入 240，验证模型兼容/输出后继续其余；每包只发一次审查，不因标签“不好”或不支持改进而重试。所有原始响应、usage、校验错误均保存；schema/逐字引用验证与主 agent 证据复核分开，均不称人类真值。分析证据中的隐藏测试/参考仅供离线审查，不进入任何 solver、共享记忆或部署工具。

## 优化计数与停止

- 硬上限为 **3 个候选版本 × 每版 48 个复杂题 = 144 次新增 solver 执行**。每轮唯一运行命名空间，canary 计入 48 次；无额外 paid 小试或全量 S0 重跑，正常失败不重试到成功。
- 按轮锁定协议、代码和假设后才分发。持久化登记已开始的轮，不通过换名字、重新开始或“最终测试”追加第四轮。
- 本轮比较的是固定简单题库的读取/检索，不开放复杂题写回。每题独立，允许高并发；模型、原始源、业务工具、评分、预算和只读边界沿用五方案实验。
- 首选一个 agent 原生接口作为优化参照。每轮只登记一个主要改动及关闭方式，写清现象、竞争解释、最简单替代、预期指标、不应变化项与反驳条件。不给工具硬编码目标 ID/答案，不改隐藏评分。
- 质量作为约束、总成本为主要目标；预登记最低实用节约和可接受质量边界后再看新分数。只有成本下降伴随质量下降时报告 trade-off，不称全面改善。
- 若前一轮已足够或没有新证据支持下一轮，可以提前停止；最多第三轮后强制停止，交付正/负结果。不得为追求显著性或更好榜单追加样本。

与旧版 7.5 的默认同期 S0/S1 多臂小试相比，本次用户授权的是最多三轮全量复杂题，本协议选择每轮只新增候选的 48 题并复用既有参照。因此时间、模型别名与 R=1 随机差异不能被完全排除，不把结果包装成严格同期随机对照或未见泛化。

## 外部设计线索

- [Anthropic: Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents)：强调同时测工具次数、时间、tokens 和错误；工具响应可以区分简洁/详细形式，分页与截断应让 agent 知道如何继续。本轮将其作为可检验的接口设计线索，不能把案例中的节约比例直接搬来。
- [Anthropic: Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)：轻量入口、路径/标识和按需工具访问；也明确运行时探索会增加时间。支持比较上下文交付方式，不说明越主动必然越好。
- [JAM, 2026 preprint](https://arxiv.org/abs/2609.34385)：保留原始历史、目录摘要与迭代查证。它包含 researcher 训练，不直接作为本项目 training-free 结果依据；这里只考察其可借鉴的读取组织方式。
- [GLM 官方模型文档](https://docs.z.ai/guides/vlm/glm-5.3-flash)：确认本次模型代码及结构化输出入口；沿用已实测兼容的 high 参数，不把可变 API 别名称为固定权重。

## 交付与完成条件

必须有：240 条 A0/A1 记录与分母；240 条 GLM 尝试及逐字段/引用审核状态；五方案结果＋机制标签＋证据等级分析；主 agent 对重点分歧/主张证据的可追溯复核；每一实际执行轮的先验假设、冻结配置、原始轨迹、只读/usage 审计、逐题质量/成本差值和接受/拒绝结论；不超过三轮的预算台账；代码开关、复现与完整报告。缺失或未知如实列出，不能靠“脚本全绿”代替语义证据。

部署运行成本、语义审查成本和本机分析/索引开销分开报告。缺少价格或 usage 不填零。代码与文档及时 commit，原始五方案记录与评分不改写。
