# cl-memory-exp

Training-free Agent memory 实验代码与研究证据。主要语言为中文，包含三个独立阶段；历史探索不能直接当作本轮基准结果。

## 从这里开始

- [第 6 节完成报告](experiments/agent_memory_plan_20261002/第6节完成报告.md)：本轮结果、成本、协议变更与解释边界。
- [完整实验过程](Agent_Memory_实验过程记录.md)：决策、修复、暂停、并发、资源采样和审计。
- [原研究计划](Agent_Memory_Research_Plan_CN_v1.0_Final.md)：原文保留；实际执行以用户修订及过程记录为准。
- [复核与环境配置](docs/REPRODUCING.md)：先离线核验，再配置付费运行环境。

## 内容结构

| 目录 | 内容与状态 |
|---|---|
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

新增正式代码的原始请求、工具轨迹、提交、记忆状态及失败证据已归档为 `experiments/section7_observability_20261002/artifacts/full-native-raw-runs.tar.gz`，12,649 个文件均逐成员核验哈希；[归档索引](experiments/section7_observability_20261002/records/full-native-raw-archive.json)保留摘要和逐文件 SHA256。下一阶段为 7.2 失败诊断；未自动运行第二次重复、第二遍、未见验证或最终测试。

## 数据与凭据边界

仓库包含代码、配置、结果、模型/工具轨迹和研究者评分证据。本轮原始轨迹在 `experiments/agent_memory_plan_20261002/artifacts/00-06-raw-runs.tar.gz`，保留原始哈希并提供恢复脚本。早期两轮轨迹按原目录提供，HTTP 捕获为 gzip。

不包含 API key、加密凭据文件、虚拟环境、`node_modules`、下载缓存、临时沙箱或其他求职/简历资料。历史记录中的机器路径是实验来源信息，不代表新机器已具备该环境。保留原实验源码，新增配置入口不会回写冻结代码。

本仓库是从原工作区按清单导出的独立历史，不包含原工作区的混合 Git 提交历史。第三方基准与框架仍受各自许可约束，参见 [来源与分发说明](docs/PROVENANCE.md)。
