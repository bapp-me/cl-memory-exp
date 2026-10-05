# CL-Bench 跨会话记忆系统比较：执行入口

更新：2026-10-05。

## 当前下一步：只做 Database 定向后续

已根据新上传的记忆快照确定 [Database 后续指导](experiments/clbench_memory_systems_20261004/DATABASE_FOLLOWUP.md)，对应 [本地 Codex 交接](experiments/clbench_memory_systems_20261004/DATABASE_FOLLOWUP_LOCAL_CODEX.md)、[快照复核与证据](experiments/clbench_memory_systems_20261004/DATABASE_SNAPSHOT_REVIEW.md) 和 [机器可读计划](experiments/clbench_memory_systems_20261004/config/database-followup.plan.json)。

先零调用核对 Codex 提取/文件/实际读取三个水位，再视证据做有限纠错可达性对照；随后检查 Claude 纠错写入的证据一致性。最多 16 个 solver 与 8 个维护作业，均有进入和停止条件，不默认跑满。本次只提交方案，没有启动新模型实验。

**Codebase 暂缓；六系统原矩阵、全量 judge 与已关闭的操作前提案例不自动重开。** 未来 Codebase 可考虑同一 Pi 底座、同一合法历史上的语义/关键词检索＋agentic search，现在不接入。涉及新阶段的下一步，以这份 Database 指导为准；下列旧方案与 LOCAL_CODEX_TASK.md 保留为历史执行依据。

## 已完成实验与原始证据

R=1 已结束：353 道任务已评分并完成当时规定的记忆屏障；Hermes Codebase 第 16 题按用户要求中止、未评分，第 17–19 题已完成。正确数不是完成进度。见 [最终报告](experiments/clbench_memory_systems_20261004/RESULTS_FINAL.md)、[收尾审计](experiments/clbench_memory_systems_20261004/records/final-closure-audit.json) 和 [执行记录](experiments/clbench_memory_systems_20261004/EXECUTION.md)。

后续全量观测与 LLM judge 已完成，见 [FULL_ANALYSIS.md](experiments/clbench_memory_systems_20261004/FULL_ANALYSIS.md) 和 [指标覆盖清单](experiments/clbench_memory_systems_20261004/records/full-metric-coverage.json)。分析阶段使用 Aixoras `glm-5.3-flash`，不新增业务任务、不改原评分；其账本与原 Z.AI 求解账本分别保留，不自动继承为新阶段 provider。

- [纯业务轨迹](experiments/clbench_memory_systems_20261004/trajectories/README.md)：353 份已评分轨迹、1 份中止动作记录，共 7,864,387 字节；文件来源与哈希见索引。
- [Database 记忆快照](experiments/clbench_memory_systems_20261004/database-memory-snapshots/README.md)：四种记忆配置各 40 题题前/题后，共 320 份；文件内容 15,709,620 字节，含 Hermes 管理文件。它们不是完整原生状态包。

## 历史方案导航

[实验方案](experiments/clbench_memory_systems_20261004/README.md)与[旧本地交接](experiments/clbench_memory_systems_20261004/LOCAL_CODEX_TASK.md)记录了 Pi 无记忆、Pi Notepad、Pi Jaccard、Codex、Claude Code、Hermes 六组设计。完整历史 ICL 已取消。实际输出预算、Codex 批次整合和恢复差异以最终报告为准，不能只从初稿推断所有题的实际配置。

- [配置映射](experiments/clbench_memory_systems_20261004/CONFIGURATION.md)
- [观测合同](experiments/clbench_memory_systems_20261004/OBSERVABILITY.md)
- [原实验配置](experiments/clbench_memory_systems_20261004/config/experiment.json)
- [原版本锁模板](experiments/clbench_memory_systems_20261004/config/runtime-lock.template.json)
- [原调研来源](experiments/clbench_memory_systems_20261004/SOURCES.md)
