# Database 定向后续实验结果

2026-10-06。D0 已完成；用户授权后恢复了 HTTP 520 中断的同一 Codex 会话。当前 D1 阶段状态：completed。Claude 采用实测验收的原生 Aixoras /v1/messages 接口；阶段结果见下方记录。

D0 核验了 320 份快照、354 份业务轨迹、两份数据库与实际评分器。Q31 的错误反馈及两个候选值进入了 Codex 阶段一输出和原生 DB，但没有进入 Q34 题前记忆文件或任何已捕获的主请求。这是可达性缺口；不等于模型看过后忽略。Claude Q23 的真实 Write 事件引入了关于 Q21 的错误历史前提，Q25 又强化了它；Q23 writer 对 Q21 完整 DDL 的实际读取仍未得到证明。

D1 使用 GLM-5.3-Flash / Aixoras Responses，启动 8 个独立 Codex 作业，完成 8 个；剩余 0 个未启动。每次恢复原始目标题前完整原生状态，使用正确的 drifted 数据库。R1 只额外提供同方法最近三题原始 prompt、完整工具记录、最终二值反馈。两臂初次请求的指令、工具、预算和前置状态核验一致；会话独立，记忆文件未变化。Q28 R0 第一次重复经历 HTTP 520 后同会话恢复及未提交后的格式续行；Q28 R1 第二次重复在大量无进展工具调用后也恢复了同一会话。全部额外成本计入对应作业，两者均不能当作无故障延迟样本。

| 任务 | 分支 | 正确 | 已完成答案 | 查询数 |
| --- | --- | --- | --- | --- |
| Q34 | R0 | 0/2 已完成 | 430, 430 | 4, 2 |
| Q34 | R1 | 0/2 已完成 | 694, 370 | 1, 2 |
| Q28 | R0 | 2/2 已完成 | 1.11, 1.11 | 2, 2 |
| Q28 | R1 | 2/2 已完成 | 1.11, 1.11 | 2, 2 |

未达到两次风险题同向改善条件，不扩大整流 benchmark。

用户请求直接测试 /v1/messages 后得到 HTTP 200，返回模型为 glm-5.3-flash、标准 Anthropic message 和已报告用量。先前仅依据已验收接口记录而作出的阻断判断已撤销；本轮不使用协议转换。D2/D3 当前状态分别为 in_progress / pending_D2_qualification。

原生实验共有 131 个唯一 provider attempt（D1 90、D2 41、D3 0），另有 1 次用户指定的 Messages 接口验收。HTTP 失败缺 usage 时保留 unknown。按实际协议分别汇总 input、output 和 cache：Anthropic 的 input 不含 cache 读写，Responses 的 input 已含 cache；不直接混加这两个 input 字段。原始 provider 字段及算术不一致均保留。只计算网关一次用量，不叠加原生重复记账。实际账户扣费未知。DPAPI 身份失败和 D2 缺 method_id 的首次启动均发生在提供商模型调用之前，私有区保留零调用基础设施记录。

33 项相关测试通过；源快照和历史评分保持原样。结果仅是目的性选择案例上的开发诊断，不能声称泛化、显著性、新算法成立；Claude 写入改善须以 D2 源证据审查为准。

详细证据：[D0](followup-records/d0-evidence.json)、[配对结果](followup-records/d1-paired-results.json)、[运行锁](followup-records/d1-runtime-lock.json)、[核验](followup-records/verification.json)、[阶段决定与成本](followup-records/conclusion.json)。原始请求、状态 DB、会话和评价材料仍在忽略目录，不发布。
