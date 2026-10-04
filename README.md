# cl-memory-exp

Training-free Agent memory 实验代码与研究证据。主要语言为中文，包含三个独立阶段；历史探索不能直接当作本轮基准结果。

## 从这里开始

- [Jaccard基线下的完整HTML分析报告](experiments/jaccard_comparison_report_20261004/report.html)（[离线分享包](experiments/jaccard_comparison_report_20261004/jaccard-memory-report.zip)）：面向外部读者，从数据集构造、48条来源、七种访问配置、执行/评分隔离到336次逐题对照、指标定义、GLM提示词/输入输出和真实轨迹逐项解释。第三轮48条补充语义审查已完成，未新增求解；含搜索时机、证据充分性和条件迁移的文献讨论，明确评分缺陷、开发集复用与评审局限。

- [五方案 GLM 细致分析](experiments/agentic_optimization_20261004/五方案细致指标分析.md) / [三轮 agentic search 优化报告](experiments/agentic_optimization_20261004/三轮优化报告.md)：按旧v1.5第7节审查240条轨迹，再完成3×48次全量验证并停止。保留完整索引与精简文件工具返回；两次观察为25/46、733,031 tokens和28/46、790,487 tokens，原参照25/46、993,760。按需索引27/46、1,020,806，未通过效率门槛。节约集中于原参照高成本个例且受缓存影响，不声称稳定15%节约、金额下降或全面超过冻结Jaccard。

- [五种记忆访问方式：240 次独立复杂题执行报告](experiments/agentic_native_20261004/五种记忆访问方式实验报告.md)：三版检索工具加用户追加的原生文件/终端两版，均已完成各 48 题 R=1。原 46 题得分依次为 24/21/25/25/24，均未超过已有冻结 Jaccard 的 27；对应 tokens 也更多。240 次共 4,131,760 tokens、871 个请求，usage 完整；简单库只读、复杂题隔离、实际 payload 曝光和原始归档均通过审计。设计与边界见 [前三版](experiments/agentic_search_20261004/README.md) / [原生两版](experiments/agentic_native_20261004/README.md)，不宣称完整产品复现或稳定因果优势。

- [冻结 No Memory 简单题库的 Jaccard top-3 补跑](experiments/section7_frozen_jaccard_20261004/冻结简单题库Jaccard补跑报告.md)：2026-10-04 完成 48 道复杂题 R=1，复杂题不写回；正确 27/46，与历史在线 Jaccard 相同，有效目标 tokens 574,109→468,934（下降 18.3%），PYTHON 52→48。99 个请求均有 usage，峰值并发 47，来源只读隔离通过。这是独立补充对照，不改变 S0 路线或宣称单因素因果收益。

- [Pi 短任务写入与后台观测核验](experiments/pi_memory_lifecycle_20261003/短任务写入与后台观测核验.md)：Pi coding-agent 1.0.0 + pi-hermes-memory 0.9.10 的真实 SDK/原生子进程合成检查，13 组集成和 4 项组件断言通过。默认单轮任务不触发常规 review/flush；waitForIdle/dispose 不能代替记忆完成确认，辅助及子进程调用须单独记账。轻量底座路线可继续，生产适配、真实 provider 和 S0 尚未验收；没有付费模型调用。

- [Pi 与 Hermes 记忆生态补充调研](experiments/memory_ecosystem_20261003/Pi与Hermes记忆生态补充调研.md)：Pi coding-agent 可用 SDK 作为实验底座；核对 pi-hermes-memory、Mem0、Hindsight、Honcho、pi-memctx 和 Hermes 第三方 provider。前轮 B 优于自行移植的结论不能扩成对全部 Pi 现成插件的排名；新候选尚未运行验收。

- [S0 接入审查与路线决定](experiments/section7_s0_audit_20261003/S0接入审查与路线决定.md)：7.4.1–7.4.2 已完成，选择 Hermes 原生 Harness；Pi 完整桥接约 12–21 人日，原生适配约 6–11 人日（工程估算）。六组无模型接口 spike 通过，S0 尚未验收冻结，未执行在线 canary。现行下一步为 7.4.3，H1 不再自动先行。

- [第 7.3 节可证伪假设分析](experiments/section7_hypotheses_20261003/第7.3节可证伪假设分析.md)：G0测评检查、H1–H5、竞争解释、反驳条件与待确认的最小实验建议。

- [第 7.2 节 baseline 分析报告](experiments/section7_analysis_20261003/第7.2节baseline分析报告.md)：624 次执行重算、324 条审查、模型选择、失败诊断与证据边界。

- [第 6 节完成报告](experiments/agent_memory_plan_20261002/第6节完成报告.md)：本轮结果、成本、协议变更与解释边界。
- [完整实验过程](Agent_Memory_实验过程记录.md)：决策、修复、暂停、并发、资源采样和审计。
- [原研究计划](Agent_Memory_Research_Plan_CN_v1.0_Final.md)：原文保留；实际执行以用户修订及过程记录为准。
- [复核与环境配置](docs/REPRODUCING.md)：先离线核验，再配置付费运行环境。

## 内容结构

| 目录 | 内容与状态 |
|---|---|
| `experiments/agentic_optimization_20261004/` | 五方案240条GLM审查、三轮144次全量agentic search验证；已关闭实验，原始归档与最终报告 |
| `experiments/section7_frozen_jaccard_20261004/` | 固定 No Memory 简单源库的 Jaccard top-3：48 道复杂题完成，协议、逐题结果、费用及原始审计归档 |
| `experiments/section7_hypotheses_20261003/` | 第7.3节假设分析、候选冻结快照、建议预算；仅离线分析，7.4未启动 |
| `experiments/section7_analysis_20261003/` | 第 7.2 节全量离线分析、三方小样本校准、324 条审查、逐字证据与主 agent 复核、原始调用归档 |
| `experiments/agent_memory_plan_20261002/` | 当前 00–06 执行：配置、Pi/工具适配、隔离评分、冻结协议、全部结果索引与审计 |
| `experiments/memory_scope_fix_20261002/` | 历史跨任务效率迁移、writer scope、memory fix；10 组 a/b/c/d 实验及原始证据 |
| `experiments/memory_direction_20261002/` | 更早的三个方向可行性探索、Hermes 适配、原始轨迹和分析 |
| `秋招调研/2026-10-01-环境知识跨任务复用/` | 实验相关的来源、数据和框架审计；沿用原路径以保留引用关系 |
| `tools/` | 新增的安全离线核验、归档恢复、环境变量凭据入口、Pi 依赖安装入口 |
| `docs/export-manifest.json` | 从原工作区导出的文件清单、来源提交、逐文件 SHA256 |

## 本轮结果摘要

GLM 5.3 Flash，单次独立运行。代码复杂目标中，无记忆 18/46，检索记忆 27/46；对应 token 172,965 与 601,793，工具调用 108 与 102。记忆组表现为正确性收益与更高输入成本的权衡，不是全面效率提升。

第 6 节实际执行 444 次：192 pilot、32 新诊断分支、192 完整第一遍、16 BabyAI、12 记忆只读抽测。无记忆不做第二遍；只读抽测不是完整原生第二遍，也不支持未见泛化。隐藏答案不向 agent 开放；三个评分资产问题按约定排除评分但保留执行。

第 7.0/7.1 节已完成。六方法共 72 次在线观测验收通过；新增正式代码 384 次全部提交并通过完整观测审计。六方法 R=1 矩阵共 624 次，含历史两组 208 次、完整 BabyAI canary 32 次及新增代码 384 次。API 并发上限 50，同一记忆流串行；新增正式流实测 API 峰值 4。见[逐项完成核对](experiments/section7_observability_20261002/records/section7-completion-audit.json)、[完整观测审计](experiments/section7_observability_20261002/records/formal-new-streams-acceptance.json)、[逐题/成本汇总](experiments/section7_observability_20261002/records/section7.1-final.json)、[配对表](experiments/section7_observability_20261002/records/section7.1-pairs.json)和[基线适配说明](experiments/section7_observability_20261002/records/baseline-adaptations.json)。

| 方法 | 复杂目标 /46 | 全代码 /93 | BabyAI /8 | 96 题代码 tokens（含缓存与所有角色） |
|---|---:|---:|---:|---:|
| No Memory（历史描述复用） | 18 | 60 | 3 | 310,663，历史 SDK 登记值 |
| 受限 ICL | 21 | 63 | 5 | 3,637,459 |
| Jaccard episodic（历史描述复用） | 27 | 71 | 6 | 1,214,123，历史 SDK 登记值 |
| Mem0 classic 0.1.118 | 18 | 61 | 4 | 542,447 |
| AWM online | 18 | 59 | 4 | 3,211,143 |
| ACE online（原生 ADD 与计数更新） | 20 | 63 | 5 | 已知小计 6,916,335，另有未知 usage |

评分保留固定排除项：每方法执行 96 个代码任务，评分 93 个；复杂目标执行 48 个，评分 46 个。所有执行与费用均保留。历史两组的原始失败请求 usage 未完整核验，模型使用可变别名，历史延迟不用于统一速度对照；这些结果是描述性复用。金额因缺少核验价格/账单保持未知，表中 tokens 不等于美元费用，也不能由 R=1 推出稳定或因果优势。

[记忆健康统计](experiments/section7_observability_20261002/records/memory-health.json)记录：Mem0 96 次代码更新中有 91 次空 facts、4 次原生 JSON 拒绝；AWM 有 49 次累计历史超过 320,000 字节请求预算，保留旧 workflow；ACE 有 3 次 Reflector 超时及 1 次 Solver 响应超时。前者均保留原失败，从核验未改变的提交状态继续；后者未提交答案并保留原评分，均不重跑。正式新代码共有 4 条未返回 usage 的 HTTP 请求，复用的 Mem0 BabyAI 另有 1 条。上述统计描述实际操作与预算，未进行语义或因果归因。

新增正式代码的原始请求、工具轨迹、提交、记忆状态及失败证据已归档为 `experiments/section7_observability_20261002/artifacts/full-native-raw-runs.tar.gz`，12,649 个文件均逐成员核验哈希；[归档索引](experiments/section7_observability_20261002/records/full-native-raw-archive.json)保留摘要和逐文件 SHA256。第 7.2 离线失败诊断已交付，见下文；未运行第二次重复、第二遍、D2 干预、未见验证或最终测试。

## 第 7.2 节分析已交付

六方法 624 次执行完成 D0 重算；276 条有效复杂目标和 48 条 BabyAI 共 324 条完成 DeepSeek 辅助审查。6 条相同样本先由 GPT 6.1 sol xhigh、DeepSeek、GLM 比较；DeepSeek 语义字段与 GPT 参照一致 20/24，GLM 原样 14/24、仅修复 JSON 括号后 18/24。此小样本只支持本轮标注器选择，不代表总体排名。

主要发现：ICL 的 45/46 个对应源在包装阶段被丢弃；Mem0 多为空写入；AWM 索引 47–95 的 workflow 冻结；ACE 辅助计算及输入成本高。Jaccard 虽有本轮正确性收益，完整代码流 token 仍约为 No Memory 的 3.91 倍。16 条“源通过且已注入仍失败”混有目标新增条件及题意/测试疑点，不能直接认定为负迁移。

新增审计发现 new:BigCodeBench/316 的测试覆盖被测函数；No Memory/new:BigCodeBench/954 多次提交 fetch failed。原分数、固定 mask 和 memory 均保留。自动标签还出现 D0/D1、来源/实际注入范围及 BabyAI 无 SUBMIT 协议的误判，因此主报告使用 D0 与逐例证据复核，不将原始标签频数当失败率；人类逐条签认尚未登记。

审查共 362 个 HTTP 请求（含校准、参数拒绝、余额不足及用户充值后获批补齐），已知 9,700,314 tokens，与 baseline 成本分开。模型输出、失败记录和证据包共 2,094 个文件已归档并核验。见[完整报告](experiments/section7_analysis_20261003/第7.2节baseline分析报告.md)、[完成核对](experiments/section7_analysis_20261003/records/section7.2-completion-audit.json)、[审查费用](experiments/section7_analysis_20261003/records/review-costs.json)及[离线复核说明](experiments/section7_analysis_20261003/REPRODUCING.md)。随后已完成7.3假设分析，见下节；7.4有限干预尚未执行。

## 第 7.3 节分析已完成（历史建议）

下述 H1 优先建议保留为 7.3 历史记录。现行 v1.5 路线先建立成熟 S0，7.4.1–7.4.2 已选择 Hermes 原生底座；未批准或启动原 H1 分支。

建议先检查评分契约与测试覆盖（G0），再优先检验 H1：冻结合法源信息和注入集合，只改变为可逆去重表示，能否降低总 token 且不新增质量失败。这是进入创新前的简单经济性对照，尚未证明有效；条件显式化、包装、Mem0 提取目标、AWM 更新预算分别作为 H2–H5，保持独立变量。

H1 暂列 767、619、739、896 四个候选目标，全部待 G0 验收；最多8个solver任务是建议预算，未获得执行授权。已逐项写明竞争解释、证伪条件、质量/费用计量和停止规则。本轮新增外部调用与rollout为0，旧分数/memory未修改。见[完整分析](experiments/section7_hypotheses_20261003/第7.3节可证伪假设分析.md)与[完成核对](experiments/section7_hypotheses_20261003/records/section7.3-completion-audit.json)。

## 数据与凭据边界

仓库包含代码、配置、结果、模型/工具轨迹和研究者评分证据。本轮原始轨迹在 `experiments/agent_memory_plan_20261002/artifacts/00-06-raw-runs.tar.gz`，保留原始哈希并提供恢复脚本。早期两轮轨迹按原目录提供，HTTP 捕获为 gzip。

不包含 API key、加密凭据文件、虚拟环境、`node_modules`、下载缓存、临时沙箱或其他求职/简历资料。历史记录中的机器路径是实验来源信息，不代表新机器已具备该环境。保留原实验源码，新增配置入口不会回写冻结代码。

本仓库是从原工作区按清单导出的独立历史，不包含原工作区的混合 Git 提交历史。第三方基准与框架仍受各自许可约束，参见 [来源与分发说明](docs/PROVENANCE.md)。
