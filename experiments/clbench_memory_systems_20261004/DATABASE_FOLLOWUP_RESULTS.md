# Database 定向后续实验结果

2026-10-06。按照 DATABASE_FOLLOWUP_LOCAL_CODEX.md 的条件执行；D0 完成，D1 执行中遇到 provider HTTP 520 而停止，D2/D3 因原生接口条件不足而阻断。本轮没有完成计划中的全部付费作业。

D0 核验了 320 份快照、354 份业务轨迹、两份数据库与实际评分器。Q31 的错误反馈及两个候选值进入了 Codex 阶段一输出和原生 DB，但没有进入 Q34 题前记忆文件或任何已捕获的主请求。这是可达性缺口；不等于模型看过后忽略。Claude Q23 的真实 Write 事件引入了关于 Q21 的错误历史前提，Q25 又强化了它；Q23 writer 对 Q21 完整 DDL 的实际读取仍未得到证明。

D1 使用当前已授权 GLM-5.3-Flash / Aixoras Responses，已启动 4 个独立 Codex 作业，其中 3 个完成，1 个在提交前因 HTTP 520 中断；剩余 4 个未启动。每次恢复原始目标题前完整原生状态，使用正确的 drifted 数据库。R1 只额外提供同方法最近三题原始 prompt、完整工具记录、最终二值反馈。已启动配对的第一请求指令、工具、预算和前置状态均核验一致；所有已启动会话独立，捕获的记忆文件均未变化。

| 任务 | 分支 | 正确 | 已完成答案 | 查询数 |
| --- | --- | --- | --- | --- |
| Q34 | R0 | 0/1 已完成 | 430 | 4 |
| Q34 | R1 | 0/1 已完成 | 694 | 1 |
| Q28 | R0 | 未完成，无分数 | 未提交 | 中断前 1 次 |
| Q28 | R1 | 1/1 已完成 | 1.11 | 2 |

首组风险题两臂均错；第二次重复未运行，控制题对照也未完成，因此不能判定重复效果或控制题退化。侧栏确实进入了已完成 R1 的模型请求，但在这个案例中没有带来正确提交。

D2 需要 Claude 原生 Anthropic 维护接口。当前配置只验收了 Aixoras Responses；旧 Z.AI 原生入口已停用。本计划禁止新增 provider 探索和静默替换，因此 D2 未启动，D3 的前置资格也没有成立。两阶段均标 blocked，未填写零分。

本轮共有 22 个唯一 provider attempt；其中 HTTP 520 请求缺 usage，保留为 unknown。input、output、cache、缺失字段和 provider 总量算术不一致均保留在汇总。只计算网关一次用量，不叠加原生重复记账。实际账户扣费未知，不能宣称金额节省。首次 DPAPI 身份启动失败发生在任何模型请求之前，保留在忽略目录的 infrastructure-history 中。

26 项相关测试通过；源快照和历史评分保持原样。结果仅是目的性选择案例上的开发诊断，不能声称泛化、显著性、新算法成立或 Claude 写入改善。

详细证据：[D0](followup-records/d0-evidence.json)、[配对结果](followup-records/d1-paired-results.json)、[运行锁](followup-records/d1-runtime-lock.json)、[核验](followup-records/verification.json)、[阶段决定与成本](followup-records/conclusion.json)。原始请求、状态 DB、会话和评价材料仍在忽略目录，不发布。
