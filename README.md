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

第 7.0 节已启动：208 次旧任务离线盘点及三个简单方法共 36 次任务的观测验收通过，实际模型调用 206 次。用户确认 API 并发上限为 50，本批实际峰值 16；复杂方法配置待确认，7.1 正式 baseline 未启动。见 [进度登记](experiments/section7_observability_20261002/records/section7-progress.json)和[待确认配置](experiments/section7_observability_20261002/records/complex-proposed-config-v1.json)。

## 数据与凭据边界

仓库包含代码、配置、结果、模型/工具轨迹和研究者评分证据。本轮原始轨迹在 `experiments/agent_memory_plan_20261002/artifacts/00-06-raw-runs.tar.gz`，保留原始哈希并提供恢复脚本。早期两轮轨迹按原目录提供，HTTP 捕获为 gzip。

不包含 API key、加密凭据文件、虚拟环境、`node_modules`、下载缓存、临时沙箱或其他求职/简历资料。历史记录中的机器路径是实验来源信息，不代表新机器已具备该环境。保留原实验源码，新增配置入口不会回写冻结代码。

本仓库是从原工作区按清单导出的独立历史，不包含原工作区的混合 Git 提交历史。第三方基准与框架仍受各自许可约束，参见 [来源与分发说明](docs/PROVENANCE.md)。
