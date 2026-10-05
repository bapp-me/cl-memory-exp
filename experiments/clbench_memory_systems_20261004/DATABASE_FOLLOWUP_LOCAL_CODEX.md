# 本地 Codex 交接：Database 定向后续

2026-10-05。本文件交接方案，不是自动执行脚本。先读 [主方案](DATABASE_FOLLOWUP.md) 与 [证据复核](DATABASE_SNAPSHOT_REVIEW.md)；参数见 [计划合同](config/database-followup.plan.json)。旧 LOCAL_CODEX_TASK.md 是已完成六系统矩阵的历史交接，不能作为新一轮全流启动命令。

## 先做什么

1. 保留用户当前工作区修改；确认本次文档提交已同步。只读取证据基线 `ef79ae2e40dddbec3bbfcd27576b72da48ca6473` 的快照/轨迹，不改它们。
2. 在已有忽略目录下建立独立私有工作区，例如 `private-runs/database-followup-20261005/`。只分享脱敏的 `followup-records/` 汇总，发布前检查实际 .gitignore 和敏感内容，不强制上传原始请求。
3. 执行原有快照/轨迹 verify 或等价的只读哈希核对，重点确认两个 Codex memories 子树一致。不要重复建设整个审计平台。
4. 完成 D0 的两条链路核对、实际 grader/数据库哈希、反馈权限检查。读取阶段一 DB 与 payload 在研究者进程内完成，不让求解 agent 访问这些私有审计材料。
5. 写 `followup-records/d0-evidence.json`：每条判断记录源文件/事件/hash，分别给 extracted/materialized/solver_visible 状态及未知项。写明 D1 执行或跳过理由。

**本地原始状态不足时停在 D0 并说明缺少哪个文件。** 不把导出的 memories 目录称为完整 home；不从 after-Q40 复制回早期；不重跑旧源任务“补造历史”。

## 付费阶段的有限顺序

收到本地用户对这份计划的执行指令后，先冻结每阶段 `runtime-lock.json` 与运行包络，再按条件执行；本次仓库文档同步本身没有发起模型调用。

- D1（条件性）：Codex Q34、Q28，R0/R1 各 2 次，最多 8 solver 作业。R1 最近三题来源固定，见合同；不得手工给出正确字段。若 D0 已证明反例可见，跳过，不为跑满预算重复注入。
- D2：Claude Q23、Q25 两个独立写入 fixture，W0/W1 各 2 次，最多 8 维护作业。W0/W1 来源完全相同，仅附加文本不同。明确这是受控维护而非原始请求逐字重放。
- D3（条件性）：D2 的每个产物一次下游执行，Q23→Q25、Q25→Q27，最多 8 solver 作业。两臂共同跳过中间任务及其记忆，不筛最佳产物。

总计上限 24 个原生作业，不是 24 个 HTTP 请求。不给旧全量 judge、旧六系统流或 Codebase 自动续跑权限。不新增 provider 探索实验；实际 endpoint/GLM 不可用时登记阻断，禁止静默替换某一个分支。

## 实施时最容易出错的五件事

- 目标新会话启动前就已读入旧快照，后台随后才提交：禁止用“最终文件变了”证明当前输入已更新。
- 复制公开 snapshots 时遗漏原生状态 DB、会话登记和 project path：应复用本地完整原始状态，文件导出仅用于对账。
- 把参考答案/容差/其他方法成功轨迹加入 writer 来源：这是不允许的信息增益，不是方法提升。
- 给 W1 更多来源、工具、迭代或 output budget：失去单项干预的解释。
- 只看笔记变谨慎或官方 CORRECT：还要保留有用事实，并在 D3 看行为、查询与全链路成本。

## 记录与验收

每个作业保留：method/phase/arm/repeat、源任务与目标的零基索引/instance_id、源数据/前置状态/配置哈希、输入材料清单、实际主/辅助请求、工具结果、写入 diff、提交/反馈与唯一 attempt 台账。实际 input/output/cache/unknown 分开，失败重试不丢弃，不能对同一请求重复加原生与网关用量。

检查 prompt、源码、工具定义与 mount：除计划差异外两臂一致；旧题输出上限曾混用，不能仅从旧计划推断实际配置。本轮统一锁定已验收配置，禁止中途更新 agent。

阶段结果分别写 `d1-paired-results.json`、`d2-claim-review.json`、`d3-downstream-results.json` 与一份短结论；未执行的阶段写 skipped/blocked，不填 0 分。语义判断附具体源片段及审查者身份，不默认 LLM judge 是人类金标。

每阶段结束先作 continue/stop 决定。简单侧栏/提示已足够时，记录工程结论；只变了措辞、效果不稳定、来源不足或控制题退化时，不扩大为完整 benchmark。需要新算法、训练或独立验证环境时，另定方案，不擅自把本合同延长。

**第一项实际工作是 D0 的本地请求/状态链核对，不是重新安装六个框架或立刻提交 40 道数据库题。**
