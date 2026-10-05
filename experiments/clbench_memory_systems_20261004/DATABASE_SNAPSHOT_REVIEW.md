# Database 快照定向复核：已知事实与不能推断的部分

2026-10-05。本次只读复核，证据冻结于 `ef79ae2e40dddbec3bbfcd27576b72da48ca6473`。核对对象是 Codex Q30–Q34、Claude Q21/Q23/Q25 价格链，以及 Notepad Q4 的边界说明；不是 320 份快照的全量语义审计。后续执行以 [DATABASE_FOLLOWUP.md](DATABASE_FOLLOWUP.md) 为准。

## E1：Codex 的文件可读层确实滞后于提取作业

对 GitHub 目录对象逐项查询，下面两个 `home/.codex/memories` 子树具有**相同 Git tree SHA**：

| 边界 | Git tree SHA | 文件数/内容字节 |
| --- | --- | --- |
| Q30 后，`codex/task-029/after` | `dc2c365993a9d53376f4626d4b26507a38ee0273` | 36 / 263,444 |
| Q34 前，`codex/task-033/before` | `dc2c365993a9d53376f4626d4b26507a38ee0273` | 36 / 263,444 |

这比较的是整个 memories 内容树，不包括各自不同的 `.snapshot.json` 来源说明，也不包括原生状态数据库和会话目录。[Q30 目录][c30-tree]、[Q34 目录][c34-tree]；对应 [.snapshot Q30][c30-index]、[.snapshot Q34][c34-index]。

三个主要文件的 SHA-256 也相同：

| 文件 | SHA-256 |
| --- | --- |
| MEMORY.md | `cfc0536339580b0a973b809132eaa32d34ace0877f69f01f84c21d13bf1e1997` |
| memory_summary.md | `10ed5dc3f4be7482b90cc5ceff73c1f3fdcda04b68cb4bb4d07ee8add1ae6f90` |
| raw_memories.md | `6ca740afbb4ab099c00c9e1d740d35d9fde57b6c5249830ccc76e5624ea6ccbd` |

Q31 后的 [.snapshot][c31-index] 仍列相同大小与上述哈希；Q34 前的 [memory_summary][c34-summary] 只列到 Q21–Q30，rollout_summaries 目录也止于 Q30。与此同时，[批次审计][batch] 在 Q31/Q32/Q33/Q34 记录 `extracted_sources=31/32/33/34`、无 consolidation thread、`completed_staged`。

**可下结论：**本实验的提取/暂存完成与可读文件材料刷新并非同一事件。Q31 反例没有改变 Q34 前这一整批记忆文件。这与每十题整合的已登记研究调度一致，不是未加速原生默认运行的普遍结论。

**还不能下结论：**阶段一具体保存了什么、主 solver 是否从其他通道读取过 Q31、仅补齐它是否就会答对。需要本地阶段一输出和 Q34 真实主请求。

业务链：[Q31][c31-trace] 同时计算 66.3 与 94.8，提交 66.3 被拒绝；[Q34][c34-trace] 同时计算 430 与 514，提交 430 被拒绝。下一步首先定位到达路径，而非笼统声称模型看到反例还不改。

## E2：Codex 已有相当强的通用核验指令

Q34 前的 [skill][c34-skill] 已明确要求比较候选解释，并写有：`Treat INCORRECT as undiagnosed failure rather than evidence of any particular mistake.` 也要求把同类先前失败当作警示。

因此，“从未告诉 agent 不要盲信经验”不是被现有证据支持的解释。另一段功能相同的 prompt 不是默认新算法。skill 文件存在仍不等于每一条要求都被模型执行；实际读取需查 payload。

## E3：Claude 纠错时产生了可被原轨迹反驳的历史前提

Q23 前 [schema-conventions][a23-before] 已把 Q21 `prc/100 = 21.99 CORRECT` 写为旧字段规范性的支持。

Q23 后新建的 [list-price-column-ambiguity][a23-after] 记载 Q23 的 prc 答案 1035 被判错、prc_v2 候选未计算，同时提出 Q21 的成功是因为当时没有记录 prc_v2：

> `prc is only the safe default when prc_v2 is absent (Q21 instance ... no prc_v2 recorded there)`

但是 [Claude Q21 业务轨迹][a21-trace] 的 DDL、助手文本和 min/max 查询都明确含 `prc_v2`。因此不能用“Q21 环境没有这个列”解释两次反馈。未在某个摘要里展开记录，不等于环境不存在。

[Q25 后同一文件][a25-after] 保留了该历史前提，并进一步写成 `now verified twice`、`CONFIRMED GT binding`、`prc_usd ... never the GT`。这里将有限反馈用于加强普遍规则；同一更新中直接观察与候选解释混在一起。

**可下结论：**这些主张实际落盘，且至少一项关于旧环境的条件与已导出业务来源冲突；不再只是 assistant 声称“我记住了”。

**还不能下结论：**原 writer 当时是否获得了 Q21 完整 DDL、该错误前提的净行为损失有多大、哪种新方法一定有效。缺来源与违背已可见来源必须分开。

## E4：正反馈不能唯一确认字段解释

核对的是固定官方版本 `5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26`；本地执行还要确认实际安装 grader 与题目文件哈希。

| 任务 | 官方参考字段/答案 | 已记录其他提交 | 官方接受条件解释 |
| --- | --- | --- | --- |
| Q21 / id 114 | prc_v2，22.09，题目 tolerance 0.5 | Claude 使用 prc，提交 21.99，CORRECT | 差 0.10，小于 0.5 |
| Q25 / id 101 | prc_v2，101.80，题目 tolerance 0.05 | No Memory 使用 prc，提交 100.85，CORRECT | 浮点评分有 1% 相对容差下限；差 0.95，小于 1.018 |
| Q23 / id 103 | prc_v2，1049，整数精确比较 | Claude 使用 prc，提交 1035，INCORRECT | 两个解释在此产生可区分结果 |

来源：[官方题目定义][official-questions]、[官方 grader][official-grader]、[Claude Q21][a21-trace]、[Claude Q23][a23-trace]、[Claude Q25][a25-trace]、[No Memory Q25][n25-trace]。计算是对已记录值和代码规则的算术核对，本次未下载数据库重执行 SQL。

**保留官方成绩。** 严格字段/解释检查只是后续隔离诊断，不改旧榜单，不将参考 SQL 当作唯一可执行写法。一个数值被接受不意味着推导它的所有叙述都被验证；这不等于二值反馈毫无信息，也不等于所有任务题意都已唯一可识别。

受测模型仍只接收本方法原本合法反馈；不得把研究者已看到的容差、答案和其他方法成功轨迹送给候选来“修好”问题。

## E5：Notepad 快照不能替代完整交接

[Notepad Q4 后文本][notepad4] 保存 Q4=26 与另一候选 8，没有明确写明 Q4 判错。[业务轨迹][notepad4-trace] 则记有 INCORRECT。现有报告还说明 previous_feedback 独立携带，不在 notepad 文本内。

因此本次不从这份文本单独推出“下一题没有得到判错反馈”，也不新开 Notepad 修复流。若后续使用这一例，必须回到写入时间和下一题实际请求。

## 复核边界与产物用途

[导出说明][export-readme] 明确快照只含选定记忆文件，不含完整原生 DB、会话与请求。因此它适合核对内容版本、落盘主张和索引，不足以单独重建完整 agent 运行状态。

本次只把证据转成下一阶段的可证伪问题，没有新增 paid judge、运行因果重放、修改原始快照或证明新颖性。D0 的本地核对范围限定在这些链条；不要以补齐观测为由重做所有 320 快照或 510 个 judge 包。

[c30-tree]: database-memory-snapshots/codex/task-029/after/home/.codex/memories
[c34-tree]: database-memory-snapshots/codex/task-033/before/home/.codex/memories
[c30-index]: database-memory-snapshots/codex/task-029/after/.snapshot.json
[c31-index]: database-memory-snapshots/codex/task-030/after/.snapshot.json
[c34-index]: database-memory-snapshots/codex/task-033/before/.snapshot.json
[c34-summary]: database-memory-snapshots/codex/task-033/before/home/.codex/memories/memory_summary.md
[c34-skill]: database-memory-snapshots/codex/task-033/before/home/.codex/memories/skills/clbench-sql-benchmark/SKILL.md
[c31-trace]: trajectories/codex/database/task-030.json
[c34-trace]: trajectories/codex/database/task-033.json
[batch]: records/codex-batch-online-audit.json
[a23-before]: database-memory-snapshots/claude_code/task-022/before/home/.claude/projects/-state-work-database/memory/clbench-schema-conventions.md
[a23-after]: database-memory-snapshots/claude_code/task-022/after/home/.claude/projects/-state-work-database/memory/clbench-list-price-column-ambiguity.md
[a25-after]: database-memory-snapshots/claude_code/task-024/after/home/.claude/projects/-state-work-database/memory/clbench-list-price-column-ambiguity.md
[a21-trace]: trajectories/claude_code/database/task-020.json
[a23-trace]: trajectories/claude_code/database/task-022.json
[a25-trace]: trajectories/claude_code/database/task-024.json
[n25-trace]: trajectories/no_memory/database/task-024.json
[notepad4]: database-memory-snapshots/notepad/task-003/after/notepad.txt
[notepad4-trace]: trajectories/notepad/database/task-003.json
[export-readme]: database-memory-snapshots/README.md
[official-questions]: https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/data/database_exploration/questions_post_drift.json
[official-grader]: https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/tasks/database_exploration/task.py
