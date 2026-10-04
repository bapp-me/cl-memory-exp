# CL-Bench 跨会话记忆系统比较：执行入口

2026-10-05。状态：本轮实验已执行，尚未完成全部矩阵。阶段结果、恢复偏差及待决定的口径见 [阶段报告](experiments/clbench_memory_systems_20261004/RESULTS_PARTIAL.md) 和 [执行记录](experiments/clbench_memory_systems_20261004/EXECUTION.md)；不要把已完成的部分结果当作六组最终结论。

请从 [实验方案](experiments/clbench_memory_systems_20261004/README.md) 和 [本地 Codex 执行交接](experiments/clbench_memory_systems_20261004/LOCAL_CODEX_TASK.md) 开始。

本轮取消完整历史 ICL；保留 Pi 无记忆、Pi Notepad、Pi Jaccard、Codex、Claude Code、Hermes 六组候选。统一 256k 上下文，每个 benchmark instance 新会话，同一流保留许可的长期状态。原生异步记忆采用任务边界加速及完成屏障，完成后才允许下一任务。

这是新的系统评测分支，不续跑已关闭的 agentic-search 优化，也不重新开启已在 Q1 停止的操作前提案例。旧研究计划和历史报告不删除；涉及本轮的下一步、配置、放行规则，以本目录为准。

- [配置映射与兼容性取舍](experiments/clbench_memory_systems_20261004/CONFIGURATION.md)
- [运行采集与离线分析要求](experiments/clbench_memory_systems_20261004/OBSERVABILITY.md)
- [机器可读实验合同](experiments/clbench_memory_systems_20261004/config/experiment.json)
- [版本与接入锁定模板](experiments/clbench_memory_systems_20261004/config/runtime-lock.template.json)
- [调研来源及证据边界](experiments/clbench_memory_systems_20261004/SOURCES.md)
