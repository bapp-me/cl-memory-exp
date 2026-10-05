# CL-Bench 跨会话记忆系统比较：执行入口

2026-10-05。状态：本轮 R=1 已结束，353 道任务已评分并完成规定的记忆屏障，Hermes Codebase 第 16 题按用户要求中止、未评分，后续第 17–19 题已完成。没有待执行任务。见 [最终报告](experiments/clbench_memory_systems_20261004/RESULTS_FINAL.md)、[收尾审计](experiments/clbench_memory_systems_20261004/records/final-closure-audit.json) 和 [执行记录](experiments/clbench_memory_systems_20261004/EXECUTION.md)。正确数不等于完成进度，例如 Codex Database 已完成 40 题，其中 20 题正确。

请从 [实验方案](experiments/clbench_memory_systems_20261004/README.md) 和 [本地 Codex 执行交接](experiments/clbench_memory_systems_20261004/LOCAL_CODEX_TASK.md) 开始。

用户随后授权对既有记录进行全量指标分析与 LLM judge，见[全量观测分析及最新进度](experiments/clbench_memory_systems_20261004/FULL_ANALYSIS.md)和[指标覆盖清单](experiments/clbench_memory_systems_20261004/records/full-metric-coverage.json)。这一阶段使用新授权的 Aixoras `glm-5.3-flash` 入口，不新增业务任务，不改原评分，因果项按用户选择标为未验证。

用户另行授权提交并推送的[纯业务轨迹](experiments/clbench_memory_systems_20261004/trajectories/README.md)包含 353 份已评分题轨迹及 1 份中止题动作记录，共 7,864,387 字节；各文件来源和哈希见目录内索引。

本轮取消完整历史 ICL；保留 Pi 无记忆、Pi Notepad、Pi Jaccard、Codex、Claude Code、Hermes 六组候选。统一 256k 上下文，每个 benchmark instance 新会话，同一流保留许可的长期状态。原生异步记忆采用任务边界加速及完成屏障，完成后才允许下一任务。

这是新的系统评测分支，不续跑已关闭的 agentic-search 优化，也不重新开启已在 Q1 停止的操作前提案例。旧研究计划和历史报告不删除；涉及本轮的下一步、配置、放行规则，以本目录为准。

- [配置映射与兼容性取舍](experiments/clbench_memory_systems_20261004/CONFIGURATION.md)
- [运行采集与离线分析要求](experiments/clbench_memory_systems_20261004/OBSERVABILITY.md)
- [机器可读实验合同](experiments/clbench_memory_systems_20261004/config/experiment.json)
- [版本与接入锁定模板](experiments/clbench_memory_systems_20261004/config/runtime-lock.template.json)
- [调研来源及证据边界](experiments/clbench_memory_systems_20261004/SOURCES.md)
