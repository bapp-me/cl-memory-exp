# 执行记录

2026-10-05。本轮未完成。用户要求的三道提示偏差题已重跑，原始记录保留；Hermes 维护耗时诊断已完成。官方动作格式、256k 对齐和后续 65,536 输出上限已确认，维护等待仍为 600 秒。早期“四项待答”和 16/19 No Memory Codebase 均为历史停点，最新结果见末节。运行事实来自本次私有轨迹、评分器记录与机械汇总；方案中的预期不作为验收成功证据。

## 已冻结的口径

- Z.AI 同一 `glm-5.3-flash`，主求解 high；R=1，最多六组 ×（Database 40 + Codebase 19）。不追加重复实验。
- 方法与环境分别冷启动、分别存储记忆；每流题目顺序不变，完成业务及记忆屏障后才开始下一题。最多 12 条独立流；所有主、辅助、子代理请求共用 50 并发信号量。
- Database 隐藏正确答案，保留对错、提交值、查询数和超时信息。Codebase 按用户选择显示官方 test_patch，参考修复 patch 始终只在评分器侧。
- 初始输出 16,384；确认耗尽后可自动提升至 32,768、65,536、131,072，同题续会话，不重新执行已完成动作。总上下文仍为 262,144；输出提升要同步预留空间。原生增额入口要求实际 provider length stop 及用量达到当前上限，避免把网络故障或输入窗口耗尽当作输出不足。
- 不额外限制模型总请求数或本轮金额；官方 Database 15 QUERY、Codebase 40 步保持不变。记忆边界等待 600 秒。框架原生更紧约束单独记录。

## 已完成的 Pi Database

三个正式流各 40 题均完成，未混入早期调试 canary。

| 方法 | 正确 / 40 | 总 QUERY | provider 报告的总 token | 迁移前正确 / 20 | 迁移后正确 / 20 |
|---|---:|---:|---:|---:|---:|
| Pi No Memory | 26 | 374 | 1,379,200 | 18 | 8 |
| Pi Notepad | 24 | 283 | 1,003,361 | 14 | 10 |
| Pi Jaccard top-3 | 26 | 174 | 1,015,966 | 15 | 11 |

按与 No Memory 都答对的配对题目统计：Notepad 的 20 题合计少 46 次 QUERY、少 142,980 tokens；Jaccard 的 21 题合计少 93 次 QUERY、少 88,787 tokens。这些子集是条件化描述，不能替代全体任务结果，也不能据此宣布稳定排名或纯记忆因果效应。

三条 Pi Codebase 正式流现已全部完成：No Memory 16/19、350 步；Notepad 16/19、293 步；Jaccard 17/19、205 步。六条 Pi 流合计 177 个正式任务。新的 v4 两题前缀通过完整验收且配置未变，按方案继续为正式流，不重复求解这两题。旧 v3 容器故障前缀完全隔离。Notepad 的前两题没有写笔记是模型选择：实际工具 schema 包含可选 notepad_update，官方定义允许空笔记；后续正式题已出现写入。

Claude Database 与 Hermes Database 已各自通过业务、跨会话状态、原生完成状态及实际模型请求验收，正式流从空状态开始。

## 原生框架的隔离与状态证据

原生框架固定在实验容器内，只有本流 home、项目路径和只读运行器；没有宿主研究仓库、评分器、其他流的记忆或真实 API key。业务 SQL/Bash 通过同一计数控制器。原生模型协议保持 Responses / Anthropic / Chat 各自原样，仅作已登记的预算与兼容参数映射。

原生容器请求的真实密钥仅在普通 Windows 身份的模型网关中使用。Pi 则由同一普通身份的宿主 SDK 直接持有凭据，其模型只有业务工具，无宿主文件读取工具。WSL 内部网络通过文件流代理访问原生网关，避免添加 Windows 入站防火墙规则。代理开销属于本轮完整系统运行时间的一部分；不把跨框架耗时差全部归因于记忆。

原生运行器按内容哈希冻结只读快照；正在执行的流继续使用自己的快照，后续适配不会替换其会话脚本。主控制器也保存源码副本。原生请求保留逐次 provider usage；CLI 的美元估算和 Pi 模型目录里的零费率均不当作实际 GLM 账单。

Claude 收集完整流式事件、home 和子会话，核对最终状态与子代理终态。Hermes 收集每个原生 review job 的源轨迹哈希、实际结果、父子会话与完成事件；不能仅凭 wait/close 或文件存在判定成功。

Hermes 的官方最终 JSON action 经过同一业务入口执行，反馈回到原会话；原生任务内维护保持原触发规则，在最终水位没有被覆盖时只补一次原生边界 review。GLM-5.3-Flash 不接受关闭 thinking，网关仅把原生辅助调用不支持的 none/off 映射为 low；主求解 high 不变，前后参数均留存。

## Codex 的当前状态

固定 Codex 0.160.0 源码，调度补丁仅在实验环境变量存在时启用：选择确切已完成 source thread、允许 exec 来源、取消该边界的 idle 等待及成功后 6 小时 cooldown。writer 提示、提取与整合算法未替换。补丁及二进制哈希见 [codex-build.json](records/codex-build.json)。`just fmt` 通过，`just test -p codex-state -p codex-memories-write` 为 **257 passed，0 failed，0 skipped**；编译产物在固定运行镜像内报告 `codex-cli 0.160.0`。

这个版本在首次 turn/start 才调用 memory startup hook，单独 thread/start 不够。适配器用无未来题目、仅要求 ACK 的维护同步轮触发原生管线，并把该模型调用计入维护成本。

在线验收曾发现：phase2::run 返回后仍可能有整合 job 在运行。早期探针因此过早关闭进程，已判为验收失败，未放行正式 Codex。修正后必须等待所有实际已启动 job 结束，再核对 SQLite 状态、源水位及一致快照。后续能力探针中管线确实完成，但原生提取器明确将测试标记判为无长期价值并返回空结果；不能把这次内容筛选误称为触发失败，也不能宣称标记召回成功。

实际 Database canary 的首题已完成非空提取与整合；次题业务已固定，但整合请求耗尽 16,384 输出后失败。按用户授权，已根据真实 provider 证据将该维护路由预算提升至 32,768，当前只登记预算、未重跑业务或发起新请求。见 [codex-output-budget-staged.json](records/codex-output-budget-staged.json)。

## 已向用户提出的三项口径问题

1. 原生 Codebase 的最终输出：建议使用官方 command JSON schema，并经过同一计数入口执行；没有命令时不自动替模型补提交。已有探针显示 Claude 可能只给文字总结、Hermes 可能只给最终 JSON。源码复核表明，官方 Codex/Claude 适配器是把 schema 转成提示并解析最终 JSON，不等于原生 CLI 的 `--json-schema`/`--output-schema` 标志。官方额外的格式修复请求也不等于传输重试；本轮尚未批准增加此类语义重试。
2. Codex 的压缩触发：原生 0.160.0 将配置阈值硬限制为窗口的 90%，即 235,929，而非配置声明的 245,760。建议保留原生行为并报告差异；如要求统一数值，需要额外阈值补丁。其上游 AGENTS.md 要求 protocol 改动后运行完整测试套件并事先征求同意。该数值差异不改变总窗口 262,144。

3. 提高输出预算后是否同步延长维护完成等待：建议按 600 → 1,200 → 2,400 → 4,800 秒随预算增长，保留所有已完成业务，仅恢复未完成维护。Hermes 正式 Database 第 10 题业务已答对，但维护先遇一次服务端错误，随后耗尽 16,384；实际自动提高至 32,768 的请求已发生，最终仍触及当前 600 秒屏障。该流暂有 9 个完整已提交任务，第 10 题的分数、提交及状态卷均保留。

这三项选择尚未收到回复；相关正式流及超时维护未据此继续。其余已通过验收的流继续运行。

## 故障与成本

所有旧 canary、失败调用、错误配置与修复后的探针分别保留，均不静默删除费用。已有事件包括错误启用未被官方 runner 调用的 60 秒 hook、最初 high 参数漏映射、WSL 重启导致的旧 Codebase 容器失效、原生控制器并发写状态文件冲突，以及上述 Codex 异步整合误判。它们是适配/基础设施验收问题，不赋予算法零分。

Pi No Memory Codebase 的第 13 题则是另一种情形：模型正常结束，但把提交标记放在说明文本中，没有产生合法结构化动作。已核实官方 `CodebaseAdaptationTask.handle_system_error` 明确对此计零分，因此零模型调用地补齐该原生失败记录并继续下一题；不把它当传输故障，不从文本补提交，不重跑求解。前 8 个命令及最后一次无效动作共记官方 9 步。该题原始控制器耗时无法精确恢复，时间列记 unknown，实际模型用量完整保留。

Pi Jaccard Codebase 第 18 题也有一次官方格式失败：最后工具命令把测试与提交 echo 合并，未满足单独提交命令要求；随后最终回复为文字总结，没有合法 JSON 动作。前 17 个命令及最后无效响应记 18 步，按官方错误入口零分推进。两次最终回复均用锁定版本官方 action parser 复核失败，未把可解析的最终 JSON 错判为格式失败。

Pi No Memory Codebase 第 16 题发生 HTTP 500。唯一已执行命令仅为读取文件；已保留失败 attempt 与用量 unknown，并在同一 Pi SDK session 恢复。首次重发 payload 与失败请求作逐字段相等断言；重建业务沙箱后额外一次控制器只读校验确认观察相同，不交给模型，不额外记业务步骤。恢复后本题共 28 步、评分通过。原始整题耗时不可精确恢复，单列恢复耗时，不将其混作正常任务延迟。

并发状态写入冲突修复后，真实容器的四路创建及 100 次并发状态读取通过，零模型调用。实际停止 Codebase 容器的故障注入也验证了：不会生成可计分的业务结果。

[attempt-ledger.json](records/attempt-ledger.json) 按唯一实际 HTTP attempt 汇总；[progress-summary.json](records/progress-summary.json) 包含时间戳及未完成流。进行中的请求暂无 usage，不等于失败或零成本。已失败但没有 usage 的请求单列 unknown，已知量只是下界。缓存不重复计入 input，reasoning 不重复加到 output。

最终仍需：完成已授权且可兼容的矩阵、完整机械核验、最多 12 个目标的离线语义复核，以及带限制的完整系统对比报告。

当前机械审计见 [mechanical-audit.json](records/mechanical-audit.json)，逐题脱敏索引与配对统计见 [task-index.json](records/task-index.json)、[efficiency-analysis.json](records/efficiency-analysis.json)。审计只覆盖完成业务与屏障的已提交行，不把未完成维护补算为已完成任务。

离线检查还修正了后续原生控制器的提交顺序：先核对所有 HTTP attempt 已结束且保留证据，再提交完成屏障；有完整失败证据的传输请求保留 usage unknown，不因原生已成功恢复就丢弃该请求，也不把它填零。屏障前暂存完整结果行，便于崩溃后不重跑业务地恢复。6 个故障 fixture 加 5 个预算 fixture 共 11 项通过，并重放核对 43 个已完成真实任务；见 [native-accounting-fixture.json](records/native-accounting-fixture.json)。该改动未热替换正在运行的 Claude 流，未恢复超时维护，也未增加重试授权。

[阶段报告](RESULTS_PARTIAL.md) 已整理完整 Pi 矩阵、配对效率与 8 个重点目标的证据索引；首次语义复核还剩 4 个目标名额。

对既有能力探针的离线复核：Claude 两个新会话确实写入并召回受控标记；Hermes 也写入并召回，原记录的 jobs/calls 已结束且覆盖末水位，但旧探针未采集当前合同要求的压缩阈值字段，不能单独作为当前完整验收证据。当前阈值及原生技能在下一会话的真实可见性由 `candidate-db-hermes-v2` 另行核验。Codex 管线完成、标记召回失败，两者分开登记，未放行正式流。

共享请求门截至 2026-10-04 19:49 UTC 观察峰值为 **8**，配置上限 50，最大本地信号量等待约 0.016 秒；当时只有 Claude 正式流仍在运行。已归档的全部正式 HTTP attempt 都有该门的进入记录，早期 114 条验收/协议探针在设立共享门前执行，单列为历史差异。HTTP 200 内也可能承载服务端错误，不能只看 HTTP 状态统计失败率。见 [concurrency-observation.json](records/concurrency-observation.json)。

Codex 求解阶段的自动增额续接已补齐：通过 `/budget` 的实际 length/usage 证据后，原生 `exec resume` 必须回到同一 session，输出预留随预算调整；正常结束、网络故障、输入超窗不能触发该路径。14 项离线测试通过，锁定二进制在无网络只读容器内接受所用 CLI 参数。未做新的在线验收，未注入活动流；维护 job 的恢复与 600 秒上限仍受待答问题约束。见 [codex-output-continuation-fixture.json](records/codex-output-continuation-fixture.json)。

## 扩展审计发现的 Codebase 恢复偏差

加入跨方法逐字提示比对后，发现 No Memory 的 index 13、16，以及 Jaccard 的 index 18 多了一句 `NOTICE: We are now coding in a new repo.`。恢复代码原先从初始 tablib 阶段直接恢复到 tenacity，误把重启当成了真实仓库切换。正常顺序只有 index 9 应出现该提示。此前机械审计没有检查跨方法提示逐字相等，所以曾报告通过；新增检查后明确报告失败，不能覆盖这项偏差。

三次多余提示没有改变题目正文、base commit、评分器或实际记忆文件，但可能影响对应任务。进一步检查显示，两个 No Memory 任务不携带跨题记忆，Jaccard 偏差发生在最后一题，未观察到经显式记忆进入后续题目的通道。保留完整原始记录，未重跑。已向用户提出第 4 项待答问题：是否接受披露偏差后的 R=1 并补充共同未受影响前缀，或先讨论重跑范围。后续源代码已修复为先恢复实际上一阶段，再判断当前是否需要发仓库切换提示；2 项离线测试通过，覆盖全部 19 个恢复位置与真实上游顺序，并复现三处旧逻辑问题。

修复前，六条 Pi 流的原始运行文件已逐一与其冻结 config_hash 对齐，保存在私有 runtime-source 中，公开校验回执见 [pi-frozen-runtime-snapshots.json](records/pi-frozen-runtime-snapshots.json)。结果和模型上下文没有被“补正”。Database 跨方法的官方问题和隐藏答案一致，隐藏值及其可枚举哈希均未导出。

## 待决定恢复的保全证据

Hermes 第 10 题超时后的状态卷已只读封存，确认主会话 22 条消息、已固定的正确业务提交和未完成 review 都在。快照里的 `running` 是进程停止前的历史状态，不能当当前仍在执行或成功 NOOP；见 [hermes-maintenance-checkpoint.json](records/hermes-maintenance-checkpoint.json)。

Codex 的真实 Database canary 还完成了一项离线交接核对：首题已提交的 `memory_summary.md` 中 9 条非标题长文本，在第二题业务提交前的实际模型请求中可见；两题 session ID 不同。时间筛选排除了业务结束后才发出的提取/整合请求，避免把 writer 读取误称为求解时读取。它说明原生记忆确实进入新题上下文，不证明模型依赖该记忆，也不补齐第二题失败的维护。见 [codex-real-memory-handoff.json](records/codex-real-memory-handoff.json)。

## 本次停点

Claude Database 已完整完成并通过当前机械审计：**32/40，187 QUERY，8,838,994 tokens，370 个请求的用量完整**。迁移前 17/20，迁移后 15/20。七条完整流合计 217 题；Hermes 另有 9 题完成业务与屏障，第 10 题业务已固定但维护未完成，所以正式结果行总数为 226。三处 Codebase 提示偏差仍在审计中明确报错。

共享门当前 active=0、历史 peak=8、ceiling=50；未创建自动唤醒或监控。原生服务保持可恢复状态，不会自行发起下一批模型请求。版本锁与 [idle-checkpoint.json](records/idle-checkpoint.json) 已更新。

尚待用户答复的四项：原生 Codebase 最终 JSON 处理；Codex 保留原生 235,929 压缩阈值或修改源码；维护等待是否随输出预算从 600 秒扩展；保留有披露的 Codebase R=1 与诊断子集，或先讨论重跑。前两项决定原生流的准入配置，第三项决定如何恢复未完成维护，第四项决定已执行 Codebase 结果的接纳口径。没有把尚未答复视为批准。详见 [pending-decisions.json](records/pending-decisions.json)。

## 用户后续修订：统一 64k 输出，保留未受截断影响的旧结果

用户确认原生 Codebase 接受官方动作格式，Codex 与其他组对齐到总窗口 256k，模型单次输出上限统一为 65,536。按本项目总窗口包含输入和输出预留的约定，输入压缩触发为 `262144 - 65536 = 196608`。Codex 的实际公式为 `min(config_limit, 90% × window)`，因此 `min(196608,235929)=196608`；只修改任务生成的 `config.toml`，不需要改其 Rust 压缩源码或运行因此触发的整仓测试。

原 16k 自动增额合同保存在 `config/experiment-v1-16k.json` 与 `records/execution-authorization-v1-16k.json`；原准入记录在 `records/compatibility-v1-16k.json`。新的共同上限为固定 65,536，不再自行超过该值。Pi 求解及压缩入口、原生主/子 agent 设置和三种协议网关均已准备相应预算映射；20 项离线测试通过，新的在线准入尚未执行。已运行的历史记录、快照和费用不改写。

用户明确：旧题没有因达到输出上限而失败就保留，只处理确有此类失败的例子。逐实际请求核对结果：226 个已提交正式结果中没有任何 length/max_tokens 截断；正式流唯一截断为 Hermes 第 10 题已答对后的未完成维护。另有 Codex 验收第 2 题整合截断，以及已排除的早期 8k Pi 验收截断。前两处只需处理未完成维护，不重做已固定的业务提交；早期 8k 验收不重跑。详情见 [output-cap-impact-audit.json](records/output-cap-impact-audit.json)。

600 秒表示业务提交后等待记忆处理完成的时长，并非模型 token 数或金额。用户目前询问其含义，尚未批准将该值提高。Codebase 多余换仓库提示来自恢复阶段判断错误，已修复并保留原始证据；没有将这一问题归因为输出上限，也没有因新的输出授权擅自重跑这些业务题。

## 最新完成：维护耗时诊断与三题授权重跑

用户随后明确授权三道提示偏差题重跑，并要求先排查维护为何慢。诊断使用既有原始请求、原生快照和实际镜像源码，零新增模型调用。Hermes 前 9 题维护中位数 32.765 秒；第 10 题存在 196 秒后返回的流内 500，以及 213 秒的异常 `skill_manage` 参数重复：990 字符的同一段补丁完整重复 54 次，耗尽 16,384 输出。该版本原生重复检测对工具调用提前返回，未覆盖工具参数。最后一个 32k 上限请求只用了 1,906 tokens，但发起时 600 秒窗口仅剩 16.47 秒，完整返回晚于截止。并发门等待为零；1.3 秒辅助调用实为会话标题生成。详见 [维护诊断](MAINTENANCE_DIAGNOSIS_AND_RERUNS.md)。未修改原生 writer、恢复策略或等待时限。

三道重跑均从原本的题前记忆和官方 base commit 开始，未带入该题旧答案/反馈，使用 high 与 65,536 实际输出上限：No Memory 第 14 题通过/9 步，第 17 题未通过/5 步，Jaccard 第 19 题通过/4 步。第 17 题由原先通过变为未通过，照实采用新结果，不挑选高分、不继续重采样。三次合计 23 个请求、162,573 tokens，全部 usage 完整；单列 targeted_rerun 费用类别。

原始 full-run JSON 未改写，3 条新结果通过 [选择清单](records/code-result-selection.json) 纳入当前比较。修正视图的 Codebase 结果是 No Memory 15/19、338 步，Notepad 16/19、293 步，Jaccard 17/19、205 步。原历史审计仍保留三处提示偏差；针对重跑的独立校验已验证提示修正、题前记忆、新 session、实际参数、评分、屏障和原始文件哈希不变。统计见 [corrected-efficiency-analysis.json](records/corrected-efficiency-analysis.json)，当前主报告已更新。

## 继续执行：原生恢复和 64k 验收

用户要求“那就继续吧，有问题就修”。已补齐原生流的持久化边界续跑、保留业务提交的维护恢复，以及最终 JSON 动作经锁定官方 parser 进入同一计数控制器的路径。Codebase 最终回复不合法时使用官方失败入口，不从自然语言补造提交，不增加语义修复模型调用。新 Codebase 原生提示附带官方 schema 指令；仍保留原生工具循环、writer 和评分器。

14 项离线测试及两个实际隔离容器的快照恢复测试通过。第一次恢复遇到根目录由 broker 拥有、普通 uid 无法恢复目录元数据的问题；在模型调用前失败，已改为保留普通文件及其内容、由容器重建目录，并以含根目录项的真实快照复测。旧原始快照不覆盖。网关已在空闲时重载，实际新请求统一 65,536 输出。

Hermes 正式 Database 第 10 题的原生技能维护已恢复并持久化，原业务提交及查询记录哈希不变，恢复约 111 秒。Codex 验收第 2 题的原生两阶段记忆流水线也已恢复。两处都没有重做业务，没有修改 writer 提示或重复检测策略，也没有延长 600 秒等待。恢复证据见 [native-maintenance-recovery.json](records/native-maintenance-recovery.json)。

Hermes Database 已通过新配置验收并继续正式流；Codex Database 和三个原生 Codebase 组分别验收，各自通过即可继续。Codebase 验收从空记忆开始，两个环境不共享状态。当前仍是原先 R=1 矩阵，旧的已完成结果保留；新配置的模型、窗口、输出和屏障逐真实请求核对，验收记录见 `records/*-64k-acceptance.json`。

## 2026-10-05 14:42–15:00 HKT：用量核对与用户暂停 Codex

用户询问近期 token 消耗来源。按 14:12:24–14:42:24 HKT 内发起的请求归窗、14:48:52 读取已返回 usage：已知总量 10,177,255，其中输入 9,990,817（含缓存输入 8,723,968），输出 186,438；2 个失败请求 usage 未知，不能填零。晚返回请求补齐后比初步实时统计略高。Codex 原生 `memory_consolidation` 标签对应 119 次请求、4,349,511 tokens，占全窗口已知用量 42.74%；阶段一提取不是主要来源。Codex Code 第 7 题的整合包含 24 次请求、1,066,246 tokens，其中输出仅 16,617。证据及可复算脚本见 [用量归因](records/token-hotspots-20261005-1442.json)、`diagnose_token_hotspots.py`。这些是实验 API 用量，不含桌面上本聊天的用量；不等于账户实际扣费。

源码和构建补丁核对确认：固定 Codex 0.160.0 默认源会话最短空闲 6 小时，全局整合成功后冷却 6 小时；实验按方案取消二者，逐题触发并等待记忆完成。补丁另把 exec 来源纳入资格，并限定当前已完成业务 thread，未修改原生 writer 提示/整合算法。原生阶段一逐会话提取，阶段二统一整合选中的提取结果和既有记忆；固定版本每次 startup 默认最多新认领 2 段，当前在线官方文档则写 16，不能混为同一版本。空闲满 6 小时是资格条件，不是定时器到点必跑。各题分别强制整合会提高短时间的维护频率，当前测得开销不能当作默认 Codex 使用成本；同轨迹下换成默认节奏或默认模型后的成本没有对照证据。见 [调度与用量审计](records/codex-memory-scheduling-cost-audit.json)。本次诊断未改变 writer、调度或预算，也没有新增付费对照。

随后用户明确要求暂停所有 Codex 流。已禁用 Codex 请求路由、退出其运行器、保存现场，并让一次性监督器跳过暂停流；其他方法的监督继续。Codex Database 完成 8/40，下一题业务已提交、维护未完成；Codex Codebase 完成 7/19，下一题业务已提交、维护未完成。两处提交和状态快照均保留，确认没有未结束的 provider attempt。除非用户明确恢复，不重新启动 Codex。暂停证据见 [native-user-pause.json](records/native-user-pause.json)。

## 2026-10-05：按用户新规则恢复 Codex 批次整合

用户随后明确要求 Database 每 10 题整合一次、Codebase 每 5 题整合一次，旧题不重跑并继续。范围限定 Codex；逐题提取保留，按整流绝对题号计数，Codebase 第 19 题收尾整合。单次输出 65,536、总窗口 262,144、维护等待 600 秒不变。旧结果与新结果包含不同整合频率，逐题索引记录实际 schedule，不能将整条 Codex 流宣称为统一批次配置。

固定源码只新增实验环境变量控制的阶段二 defer 开关，原生 writer 提示与算法不变。构建 `c611ed13…f79e13` 经 `just fmt`、50 项 `codex-memories-write` 测试通过；9 项 Python 检查覆盖批次题号、最终不足一批、旧失败 job 延后、新 writer 越界启动、未提交或遗漏提取源等。真实二进制在一次性容器中完成 3 条本地 mock 集成路径：复用已完成提取不发模型请求；新提取后不启动阶段二；批次点恰好派发一个全局整合任务。共 4 个模拟回复、0 外部模型调用。首次夹具用错原始预分配会话 ID，修正为原生实际 thread ID 后通过；正式配置使用持久化边界中的实际 ID，未因此重跑业务。

恢复前保留两份原始故障快照，将可见 memory 工作区还原为上一成功屏障的完整文件与 Git 基线；提取数据库、业务会话和源轨迹逐字节保留。这样不会把中断整合留下的半成品提前注入下一题。Database 第 9 题、Codebase 第 8 题直接复用已完成提取，业务提交和 action 哈希保持不变，按新规则完成 staged 屏障后继续。原快照、过渡快照及验证见 [过渡记录](records/codex-batch-transition.json)、[集成检查](records/codex-batch-native-fixture.json)。监督器继续处理本轮已授权范围内的故障恢复。

在线验证随后通过：两个环境都完成第 10 题后的原生全局整合，各覆盖 10 份非空提取源；已观察到的非批次题没有发出阶段二请求。原先 15 个完整 Codex 结果逐行等于各自持久化的 prepared-result，未重写成绩。见 [在线批次审计](records/codex-batch-online-audit.json)。后续继续遵循同一批次规则。

Hermes Database 第 38 题另遇到模型工具参数重复 `content` 字段，最后值为 null，官方 `DatabaseAction` 字符串校验失败。官方数据库任务没有格式错误记零后跳题的入口，因此保留停点，没有擅自算失败。用户明确批准后，使用相同 session、原生会话历史和原数据库状态续接，保留已返回的工具错误；不替模型选择重复字段值，不重放前两条查询。该题已结束，官方判错，共 11 次 QUERY；前两条已完成查询没有在新动作中重复执行。恢复耗时单列、原端到端耗时仍未知，费用和失败输出都保留。授权仅覆盖这个停点，见 [恢复证据](records/hermes-db-invalid-tool-stop.json)。

Hermes Database 随后完成全部 40 题：24 题正确、195 次 QUERY，已知 8,510,254 tokens，3 次请求 usage 未知。上述数值包含其已完成正式题中的失败尝试；不代表真实账单。完整原生流的配对统计已更新，R=1 不支持把差异全部归因于记忆。

## Hermes Codebase：仅中止第 16 题，继续第 17–19 题

第 16 题主会话反复通过 native terminal 等待本地 `/testbed`，而业务容器经 `CLBENCH_ACTION` 访问；后台 review 已返回，原生主循环上限为 `sys.maxsize`。未注入解题提示或环境提醒。用户先选择停止，执行者误解为停止整流；用户随即澄清只中止该题、后面三题继续，已按澄清修正。

已保留 15 个完整结果，第 16 题的 native-state、14 个业务动作和两份未执行的脚本。旧的异常处理将 native quiesce 和业务容器保留放在同一个 try 中；原代理的 UID 0 没有 CAP_KILL，quiesce 异常后跳过业务容器保留，finally 清理删除了原容器。因此不声称保存了原完整文件系统：已记录的 `/testbed` 命令均为读取，另有失败的无网络 pip download；两份脚本写在仓库外，从日志原文恢复且没有执行。主流程已把业务容器保留移到 native quiesce 之前，避免后续发生同类丢失；原生代理同 UID 停止修复另已登记。

单题中止采用独立 `user_interrupted_unscored` 记录，correct/reward 均为 null，不写入 scored results，也不伪造维护成功。14 个已执行业务步骤单列保留在官方状态恢复的全局计数中；下一题仍是官方索引 16（第 17 题）。现场 memory 哈希与第 15 题的已提交版本完全相同，恢复保留 native 历史并使用新 session，第 17 题实际已启动。23 项边界、恢复及记账检查通过。记录见 [授权](records/hermes-code-task16-skip-authorization.json)、[中止与续跑证据](records/hermes-code-user-skip.json)。
