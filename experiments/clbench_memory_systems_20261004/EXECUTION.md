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
