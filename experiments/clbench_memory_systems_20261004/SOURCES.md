# 调研来源与核对边界

核对日期：2026-10-04。仅阅读官方文档、公开源码/发行元数据及本仓库记录；未安装框架，未调用GLM，未编译补丁，未做复杂代码验证。方案中的上限、矩阵、屏障和停止条件是本项目决定，不是上游性能结论。

## CL-Bench

- **S1｜Database Exploration**：[固定源码说明](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/tasks/database_exploration/README.md)。40题默认迁移流、QUERY/ANSWER及探索成本计分；实际任务文件/预算须本地锁定。
- **S2｜Codebase Adaptation**：[固定源码说明](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/tasks/codebase_adaptation/README.md)。两个仓库19题、逐题base commit和隔离patch评分；不等于连续保留全部代码修改。
- **S3｜官方 Notepad ICL**：[README](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/systems/icl_notepad/README.md)、[system.py](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/systems/icl_notepad/system.py)。optional notepad_update、整体替换、跨instance清上下文而保留笔记；本轮移植到Pi，不是同一runner。
- **S4｜Codex adapter**：[README](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/systems/codex/README.md)。single_conversation、hard reset、原生记录和旧CLI版本；可复用但不能免除新版本验收。
- **S5｜Claude adapter**：[README](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/systems/claude/README.md)。stream-json、原生记忆/会话导出、重试与原Anthropic成本路径；主session导出不保证覆盖子agent。

## 原生配置与观测

- **S6｜Codex 配置**：[官方配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)。model_context_window、auto-compaction、模型目录、提取/整合模型和idle限制。本次正文说明idle默认6小时、钳制1–48；不能写0便宣称立即生效。属于滚动文档，实际release可能不同。
- **S7｜Claude Code**：[模型与上下文](https://code.claude.com/docs/en/model-config)、[Monitoring](https://code.claude.com/docs/en/monitoring-usage)。自定义模型ID下的MAX_CONTEXT_TOKENS、AUTO_COMPACT_WINDOW；原生原始请求日志及子agent关联有版本要求。配置存在不等于本地采集成功。
- **S8｜Pi coding-agent**：[compaction](https://github.com/earendil-works/pi/blob/200387122ca450d6387f033949423114a270b96c/packages/coding-agent/docs/compaction.md)、[settings](https://github.com/earendil-works/pi/blob/200387122ca450d6387f033949423114a270b96c/packages/coding-agent/docs/settings.md)。原生reserveTokens和keepRecentTokens；这是本次可见main快照，不声称等于正式发行的全部文件。
- **S9｜用户指定的国内接入**：[BigModel Codex](https://docs.bigmodel.cn/cn/coding-plan/tool/codex)。链接可检索，但本轮多次正文抓取超时，未核实国内endpoint及模型范围。保留为本地账号接入第一来源，不据国际地址推测国内地址。
- **S10｜可读取的同厂商官方接入说明**：[Z.AI Codex](https://docs.z.ai/devpack/tool/codex)、[Z.AI Claude Code](https://docs.z.ai/devpack/tool/claude)。Codex为Responses＋模型目录，国际示例base URL为https://api.z.ai/api/v1，示例model为glm-5.3。它不自动证明用户现有Flash模型在该协议/账户可用，也不授权国内国际账号互换。
- **S11｜Codex 原生提取**：[phase1.rs](https://github.com/openai/codex/blob/afb436df8b70bb5bc57b86d9a3e829968988cd21/codex-rs/memories/write/src/phase1.rs)。来源资格、idle、claim、提取模型、成功有输出/无输出/失败分支。该main源码比调研时latest release更新，必须在实际安装版本上确认调用点与字段。
- **S12｜Claude auto memory**：[官方记忆文档](https://code.claude.com/docs/en/memory)。会话中读写、项目路径、索引按需展开、非每会话必写、部分后台/嵌套会话禁用；不能从auto名称推断后台机制，也不能为了有记忆额外代写总结。
- **S13｜Hermes 原生记忆**：[Persistent Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/)、[agent_init.py](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_init.py)。会话初始冻结笔记、nudge、background_review routing/defer/budget、审批及pending状态。文档描述write_approval关闭仍可能有后台replace/remove staged例外；必须记录真实应用结果。
- **S14｜Hermes 压缩与运行配置**：[Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/)。model.context_length、compression.threshold、auxiliary.compression及延迟/超时；256k不代表维护累计预算也只有256k。
- **S15｜Claude 生命周期**：[Hooks reference](https://code.claude.com/docs/en/hooks)。用锁定版本支持的hook采集工具、会话、压缩和子任务；hook终点不自动代表全部工作完成。

## 发行版本证据

**S16｜官方 latest release查询**：本轮实际查询GitHub releases/latest得到以下非预发布结果。执行时重查一次并锁定，而非永远将这些值称作最新。

| 框架 | 调研可见版本 | 官方链接 |
|---|---|---|
| Codex | 0.160.0；发布2026-10-01T20:19:13Z | [release](https://github.com/openai/codex/releases/tag/rust-v0.160.0) |
| Claude Code | 2.1.289；发布2026-10-03T23:07:17Z | [release](https://github.com/anthropics/claude-code/releases/tag/v2.1.289) |
| Pi | 1.0.2；发布2026-10-04T00:56:36Z | [release](https://github.com/earendil-works/pi/releases/tag/v1.0.2) |
| Hermes | v2026.9.24 / 0.21.5；发布2026-09-24T10:09:38Z | [release](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.24) |

## 本仓库沿用证据

- **E1**：[资格检查停止决定](../precondition_qualification_20261004/records/stop-decision.json)：当前两个候选停在Q1，没有进行48次模型对照；本轮不重新开启。
- **E2**：[Pi插件短任务写入与后台核验](../pi_memory_lifecycle_20261003/短任务写入与后台观测核验.md)：历史pi-hermes-memory的flushMinTurns、显式shutdown及递归子进程问题。只说明插件版本的事实，不当作Hermes原生当前配置。
- **E3**：[凭据链路复盘](../../docs/GLM凭据存储与跨对话记忆链路复盘.md)：沿用安全加载入口和账户边界；不能将真实密钥复制到实验模型目录或日志。
- **E4**：[旧Pi/Jaccard实现](../agent_memory_plan_20261002/core.py)：词法top-3与旧48KB规则。本轮更换环境、256k和oversize处理，必须保留新配置身份，不拼旧成绩。

## 尚待本地确认，不写成已完成

账户实际Flash/Responses兼容；256k真实窗口与每条原生压缩路径；release对应的idle/source gates；按instance触发Hermes review而不是每次工具反馈触发；Claude当前启动方式的auto-memory启用及异步行为；子agent/辅助调用日志覆盖；CL-Bench最新资产与评分。方案允许有界的配置/调度/日志适配，并明确不能通过时的BLOCKED处理，不要求在远端完成复杂代码验证。
