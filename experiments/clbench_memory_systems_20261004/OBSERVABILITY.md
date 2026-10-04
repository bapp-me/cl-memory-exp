# 运行时采集与离线分析合同

目标：运行时尽量保全可合法观察的事实，离线再做成本核对、机制分析和重点语义审查。本文件是采集要求，不表示任何框架已完成这些埋点。原始证据必须在agent不可访问的审计区保存。

## 1. 最低交付结构

```text
private-runs/<run_id>/
  manifest.json               # 实际版本、模型、预算、权限、环境顺序
  requests/                  # 唯一request/attempt的请求与响应/SSE
  events.jsonl               # 框架原生事件，不替换为只有摘要的日志
  tools.jsonl                # 主/子agent工具、参数、结果、退出状态
  sessions/                  # 主会话与全部可取到的子会话原始记录
  memory/                    # 快照/diff、合法源档、写入及来源映射
  compactions/               # 原输入、摘要、保留/删除范围、触发、成本
  barriers.jsonl             # 任务末水位、作业终态、提交、下一题加载版本
  submissions/               # 冻结业务产物，不允许维护期间修改
  evaluator-private/         # 评分器的私有证据，绝不交给被测系统
  derived/                   # 聚合与离线标注，不回写被测memory
```

运行目录、源对话、凭据、未脱敏响应默认不提交Git。提交公开报告、manifest摘要、可分享证据索引/哈希；需要共享原文先人工审查。不要把带真实上下文的请求日志放在受测agent能grep到的仓库目录中。

## 2. 每类分析需要在运行时保存什么

| 后续问题 | 必要材料 | 无法直接推出的结论 |
|---|---|---|
| 是否做对、花多少业务动作 | 原query、环境/评分版本、所有动作、冻结提交、原生feedback/reward | agent自称完成不是成功 |
| 是否实际获得前题记忆 | task-start实际请求、注入块、读取返回、source版本 | 文件存在不等于已经可见 |
| 为什么没有写入 | 触发条件、计数、水位、job输入/输出、NOOP/拒绝/失败/审批、持久化结果 | 缺日志不能补造“模型认为不重要” |
| 搜索/阅读是否浪费 | query、可观测候选、实际返回原文范围、截断和分页、重复曝光、后续行为 | 无相关性真值不能报告真实recall |
| 条件误用与过期知识 | 当时可见来源、原适用条件、变更通知/环境证据、实际动作和结果 | 失败不自动等于负迁移 |
| 压缩有没有丢关键内容 | 压缩前实际上下文、摘要与保留尾部、下一请求、原轨迹 | 摘要看起来漏写不等于已证明因果影响 |
| 各角色与缓存开销 | 全部唯一HTTP attempts、usage原字段、返回model、角色/父子关联 | 缺失usage不是0；tokens不等于美元 |
| 子agent是否改变结果 | spawn/finish、父子ID、输入、工具、响应、全角色费用 | 只看最终汇总不能判断每个子agent用途 |
| 等待是否有效 | 最终source水位、job覆盖水位、文件/DB提交、下一题实际加载版本 | 固定sleep、主进程idle、stdout结束都不是充分证据 |

每个记录至少带 run_id / method_id / instance_id / project_key / session_id / agent_id / parent_agent_id（可空）/ role / call_id / attempt_id / timestamp / config_hash。重试属于同一logical call的不同attempt，不能覆盖第一次失败。

## 3. 三层独立对账

**业务环境层**是动作与评分的权威来源；所有主/子agent必须通过共同计数入口。**框架层**记录会话、工具、压缩、文件修改和生命周期。**传输层**核对实际发往GLM的请求、响应和usage。

优先原生完整日志，必要时采用透明受控网关。若存在Responses/Anthropic到GLM的协议转换，保存转换前后去凭据payload及ID映射；不得只记录转换前输入，却假设模型实际看到了它。不要修改模型输入来嵌入审计标记；优先header、进程/连接上下文或旁路关联。

网关必须覆盖主进程、维护线程、子进程和fallback。只把主base_url改成代理不证明全覆盖；用允许的网络目的地和实际请求数量核对。无法取得服务端未公开内部处理不虚构，尤其不把加密/脱敏thinking还原成明文。

权威用量以每个唯一provider attempt为单位求和。原生usage、CLI total、OTel和网关可能指同一请求，不能四次相加。保留原字段和归一化映射：输入是否含cache、output是否已含reasoning、累计usage如何取差。失败无usage标unknown并给下界；不得用OpenAI/Anthropic价目为GLM计算成本。[S4–S7](SOURCES.md)

## 4. 原生采集映射

### Codex

保留 `exec --json` 或所选SDK的全部事件；保存本run的CODEX_HOME会话、记忆阶段作业、提取/整合子任务、状态DB和文件diff。不能只导出stdout中主conversation_id对应的日志。对原生startup或阶段作业补父任务ID、水位和完成标记，日志补丁不改变内容算法。[S4、S6、S11]

### Claude Code

优先 `--output-format stream-json --verbose` 加原生OTel；必要时用受控网关核对。官方当前文档支持以下启动环境配置（保存路径必须在agent可读目录之外）：[S7]

```text
CLAUDE_CODE_ENABLE_TELEMETRY=1
OTEL_LOG_USER_PROMPTS=1
OTEL_LOG_ASSISTANT_RESPONSES=1
OTEL_LOG_TOOL_DETAILS=1
OTEL_LOG_RAW_API_BODIES=file:/ABSOLUTE/PRIVATE/AUDIT/api-bodies
```

还需配置实际OTel exporter/collector，设置变量不等于日志已落盘。文件模式优先于可能截断的内联正文。若使用traces和自定义base_url，按锁定版本配置trace传播并检验父子关联，不依赖仅对直连Anthropic有效的默认值。

使用SessionStart/End、Pre/PostToolUse、SubagentStart/Stop、Pre/PostCompact等该版本实际支持的hooks；保留hook原事件。Stop/SubagentStop表明某个生命周期事件，不能单独证明所有异步任务结束。不要为了凑字段注册不存在的hook。[S15]

保留主session及可访问的所有subagent transcript。官方CL-Bench适配器主会话导出会漏掉未列为主session ID的子会话，需扩大当前run范围，不可扫描整个用户全局home。某些completed事件的token只描述最后请求，不能当整个子agent费用。具体字段按实际版本核对。[S5、S7]

### Hermes

收集原生SessionDB/messages/FTS、session_model_usage、review job与父session关系、memory/skills/pending/curator变化，以及压缩和auxiliary调用。DB使用SQLite backup或可靠关闭后复制，不能只拷贝活动WAL数据库的主文件。[S13–S14]

### Pi coding-agent

收集消息/工具/compaction事件和pi-ai传输层；Notepad每次提议与应用状态、Jaccard完整选择记录、task-start实际注入都保留。前题业务episode、用于模型的压缩表示和私有审计信息三者分离。所用SDK自己的waitForIdle不自动代表所有扩展后台任务结束。[S8、E2]

## 5. 子agent的取舍与覆盖等级

主矩阵保留原生已启用的子agent/维护能力，不为了省埋点静默禁用；不额外为Pi添加delegation。原生允许的并发仍受共同全局请求和业务预算约束；维护子任务的递归禁止沿用原生保护或薄适配。

- `FULL`：主/子角色请求、关键工具内容、父子关系和费用可关联。
- `LIMITED_CONTENT`：完整请求成本可对账，但部分子角色输入/工具正文不可取；允许系统级结果，明确该机制无法做完整语义分析。
- `INCOMPLETE_ACCOUNTING`：无法界定遗漏调用或成本，阻断完整成本主表；不能把它作为与其他组同口径的系统。

由接口本来不公开造成的缺失，和采集器漏记是不同原因。前者缩小主张，后者修采集。即使FULL，也不声称观察到“模型真实依赖了哪条记忆”。

## 6. 离线分析顺序

先做机械核对：任务完成/异常状态、正确分母、业务计数、请求usage、模型一致性、256k实际配置、跨题新session、barrier、隐私隔离。通过后再做全文语义审查；先选少量结果变化或高成本案例，不默认逐条调用强模型。

语义输出必须含可定位的来源和unknown；把直接事实D0、语义解释D1、干预证据D2分开。自动标签、引用次数、相似度、模型自称“用到了”不是因果真值。对压缩/记忆误用的因果结论需要后续同起点分叉，不纳入本轮默认执行。

无法取得原始数据时，明确不能回答哪项问题，不用离线LLM生成看似完整的替代轨迹。离线分析结果及隐藏评分不得回写任何正式运行分支。
