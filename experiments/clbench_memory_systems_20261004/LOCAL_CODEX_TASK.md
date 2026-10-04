# 给本地 Codex：实现、验收与运行交接

请执行本目录的新方案，不重启已关闭的agentic-search优化和precondition qualification。当前仓库只新增文档和配置合同，尚无本轮可运行runner；不要声称JSON已被CL-Bench直接支持。

## A. 先读与锁定

读取 README.md、CONFIGURATION.md、OBSERVABILITY.md、config/experiment.json。复用已有benchmark adapter、隔离沙箱和请求账本；不要为了目录统一移动或重写旧归档。

一次性解析最新官方版本，记录实际包版本、Git SHA、依赖锁、二进制和镜像哈希。生成私有运行锁及可公开摘要，模板见 config/runtime-lock.template.json。若选main以获得新功能，注明与release差异；正式流中不再自动更新。

沿用用户实际GLM身份与凭据入口。核查用户给的BigModel Codex官方页，确认所用账户的Responses地址、模型目录和Flash可用性；本轮远端研究没有成功取得该中文页面正文，不能照猜国内地址。国际Z.AI说明只作为同厂商接入路线参考。禁止让某一组静默换成glm-5.3旗舰或其他模型。

## B. 实现最少必要差异

1. Pi coding-agent三组：无显式跨任务经验、官方语义Notepad、Jaccard top-3。任务内共享同一业务接口/压缩实现，跨任务状态严格按配置区分。
2. 复用官方Codex/Claude适配器的instance边界与容器思路，更新CLI版本和事件解析；Hermes用原生任务循环，不替换成Pi插件。
3. 统一262144上下文、245760触发目标及16384预留，实际GLM接入不支持时报告阻断。所有辅助角色也计入，禁用未声明模型fallback。
4. 实现task_end → final feedback → native maintenance → durable commit → next context的屏障。Codex必要时仅补eligible/启动/等待；Hermes做按instance而非按工具轮的末水位review。
5. 完整采集主/子会话、真实payload、维护状态、compaction、源到返回再到模型输入的映射。私有记录在被测agent不可读目录；凭据不进入任何payload或Git。

保持原生writer/检索内容策略；已列的调度、权限、GLM和日志改动是允许的工程适配。更大改动须先写trade-off，不以完整产品名称掩盖替代实现。

## C. 有限验收，不先跑完整流调试

| 门槛 | 必须交付的证据 | 不算通过的情况 |
|---|---|---|
| 版本/路由 | 所有实际角色model/provider映射与锁 | 只看到主model配置，没有真实辅助请求 |
| 工具/评分 | 正常与失败工具、真实提交、hidden tests隔离、预算共用 | 原生Bash能绕过数据库QUERY或代码环境计数 |
| 会话/状态 | 同题续会话、跨题新ID、同run记忆保留、他组不可见 | 每题reset删除所有记忆，或恢复同一主会话 |
| 生命周期 | 能力fixture里可完成一次原生写入并在新会话读到；NOOP另有终态；队列等待证据 | 主agent结束就复制文件；固定sleep；空候选当内容NOOP |
| 256k/压缩 | 配置解析、长历史fixture、压缩前后请求与成本；摘要器自己不超窗 | 仅改UI或声明窗口，实际仍200k；溢出后静默丢旧消息 |
| 子agent/成本 | 唯一attempt账本、父子图或明确缺口、用量对账 | 只用主session总数、将未知当0、重复相加累计usage |
| 恢复 | 人为中断的已提交状态/未完成状态被区分 | 重跑业务答案以掩盖维护失败 |

长历史和生命周期先用本地fixture，不必为压测运行所有题。只有需要确认真实协议/模型时做有限在线canary。能力fixture可显式要求保存无害事实，但其提示、笔记和经验不进入正式冷启动流。

测试必须证明空结果与失败区分、源库只含过去合法内容、compaction不会抹掉审计原文；不要为了验证“能写”要求正式每题生成非空笔记。

将结论写成 compatibility.json：每组 READY / LIMITED_OBSERVABILITY / BLOCKED，具体原因、允许主张与补丁。非空能力存在不代表效果更好；模型答错也不自动意味着接入失败。

## D. 按已通过组执行

顺序：Pi简单参照接通 → 各原生组验收 → 完整Database → 完整Codebase。可独立并行适配，但不为凑齐六组阻塞其他已通过组。每个新配置用独立run，不拼旧结果。

首轮R=1；每流按官方顺序串行。Database迁移不reset；Codebase按各题base commit恢复工作树，项目记忆sidecar独立保留。任务边界等待所有与该水位相关的作业结束；超时/失败暂停该流并保全业务提交，不立刻加载下一题。

本地用户已批准的批次范围内，完成manifest和验收后直接运行，不每个请求重复确认。若缺少新阶段明确的账户/费用授权，先一次补齐；不要挪用已关闭实验的不限额授权。默认不追加新模型、连续会话、第二次重复或优化轮次。

## E. 验收最终产物

提交实际配置/补丁说明、版本锁摘要、兼容性表、task/session/barrier索引、全角色费用与未知项、逐题/阶段结果、评分与故障限制。文档里的354仅是当前六组×59的规划量，以实际通过组和冻结manifest去重计算。

先机械统计，再最多12个独立目标的重点语义复核。原生不同harness的成绩只称系统比较，不自动归因记忆；pi_none不替代每个原生系统自己的stateless消融。本轮没有这些消融时，明确不能量化纯记忆因果增益。

新问题以证据提出即可，不自行启动下一轮研究。同步Git前审查密钥、私有会话、请求正文和evaluator数据；本目录默认忽略运行原件。
