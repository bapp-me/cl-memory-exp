# Pi 与 Hermes 记忆生态补充调研

2026-10-03，香港时间。根据用户要求，补查 Pi 原生扩展生态及 Hermes 第三方 memory provider；同时回答 `pi-agent-core` 与 `pi-coding-agent` 的区别。本轮核对 10 个仓库的 61 个来源文件及 npm 发布元数据，未安装插件、启动服务或调用实验模型。源码与发布版本见 [来源清单](records/source-inventory.json)、[npm 快照](records/npm-snapshot.json)。

**结论：Pi 有现成且值得认真评估的记忆扩展；Hermes 也有正式的第三方 provider 接入体系。Pi coding-agent 完全可以作为实验 Harness。** 上轮“B 优于自行把完整 Hermes 搬进 Pi core”的结论只针对那两个实现方案，不能推出 B 优于所有现成 Pi 记忆扩展，12–21 人日的移植估算也不能套给本轮找到的扩展。

按本项目目标，优先看 **Pi coding-agent＋pi-hermes-memory**（完整、本地、可改）与 **现成 Hindsight 接入**（后端研究证据更充分，但系统成本更复杂）。Mem0 官方 Pi 插件适合作为接入明确的语义记忆候选；Honcho 更偏跨会话用户建模。没有证据支持现在就宣布其中一个在 GLM＋独立任务流上效果最好。

## Pi coding agent 可以用于非编码实验

二者是上下层关系：

```text
pi-ai                 模型与 provider 访问
  ↓
pi-agent-core         模型—工具循环、消息状态、事件
  ↓
pi-coding-agent       会话、压缩、资源/技能发现、扩展生命周期、CLI 和 SDK
  ↓
memory extension      利用 session_start、before_agent_start、agent_end 等 hook
```

当前实验直接 `new Agent(...)`，自己安排工具和状态，所以不会自动加载 coding-agent 扩展。**改用 `createAgentSession()` SDK 就能使用正式扩展宿主，不必运行交互终端。** 新版 SDK 明确提供 `agentDir`、`resourceLoader`、`sessionManager`、`tools`、`excludeTools`、`noTools`、`customTools` 和事件订阅。可只启用 PYTHON/SUBMIT 或 ACTION 加指定 memory 工具，使用隔离目录和明确资源清单；“coding”这个产品名不限制任务一定是代码题。[SDK 文档](https://github.com/earendil-works/pi/blob/a276dabe57911253350bffb93cb7d7aff6a73261/packages/coding-agent/docs/sdk.md)、[实现](https://github.com/earendil-works/pi/blob/a276dabe57911253350bffb93cb7d7aff6a73261/packages/coding-agent/src/core/sdk.ts#L44)

用户指出“既然能接受复杂 Hermes，Pi coding 也行，观测多改一点”是成立的。不能为了保留旧 runner 而排除完整 Pi 宿主。主要新增工作是四类共同适配，而不是重写记忆算法：

| 适配 | 为什么不能漏 | Pi 与 Hermes 的共同性 |
| --- | --- | --- |
| 请求与角色观测 | 主循环订阅不能自动捕获插件自己调用 SDK、子进程和服务端抽取/反思 | 两者都要补全角色 transport/usage |
| 工具与资源隔离 | 文件、bash、自动发现的 skills、旧 sessions 可能越过实验数据边界 | 两者都要明确 whitelist 和不可读资产 |
| 任务与记忆生命周期 | 新任务应新前台会话，但保留合法记忆；后台写入结束后再进入下一题 | 两者都要有完成屏障、快照与恢复 |
| 同底座 N/J | prompt、压缩、工具调度和 API 参数可能随宿主改变 | 旧 Pi-core 成绩不能直接当新宿主同期对照 |

这使 **Pi coding-agent＋现成扩展** 成为独立第三条路线 C，与“Pi core＋自行移植 Hermes”路线 A 分开比较。它可能减少工作，但本轮未实际接线，不给未经验证的精确人日数。

## Pi 的主要候选

下表版本是本轮 npm registry 实际返回的 latest，不以搜索引擎缓存或 README 自称版本代替。宿主当前 npm 为 `@earendil-works/pi-coding-agent 1.0.0`。

| 方案 | Pi 接入与核心机制 | 效果证据 | 对本项目的判断 |
| --- | --- | --- | --- |
| **pi-hermes-memory 0.9.10** | 社区 TypeScript 原生扩展；笔记、global/project、SQLite FTS、session search、Pi skills、后台 review、压缩/退出 flush | 有测试与启动耗时脚本；本轮未发现对 GLM 独立任务流的质量/全成本对照 | **最贴近完整本地闭环需求，建议首先做有界接入验收** |
| **@mem0/pi-agent-plugin 0.3.2** | Mem0 官方仓库；每次 response 前 project recall，`agent_end` 自动 capture，主动工具与 project/session/global scope | Mem0 论文与 Pi schema-migration demo；不等于本插件的充分独立评测 | 官方维护优势清楚，默认云后端；适合语义记忆候选 |
| **@abix5/pi-hindsight 0.5.1** | 社区原生 Pi 扩展；project bank、可选 user bank、自动 recall、后台 memorize、retain/recall/reflect 工具 | Hindsight 后端有论文/评测，插件本身未核验同类性能 | 若接受后台服务和额外模型，值得作为研究型候选 |
| **@agney/pi-honcho-memory 0.1.0** | Honcho 官方文档列出的社区集成；缓存用户/项目上下文，turn 后上传 user/assistant，主动 search/chat/remember | Honcho 后端公开长期对话 benchmark；不证明 Pi 插件的下游任务收益 | 用户偏好、用户模型更合适，环境工具经验需另外验收 |
| **pi-memctx 0.13.1** | 本地 Markdown packs、自动上下文检索/注入和写入，qmd 可选、无 qmd 可 fallback | 作者公开工具量/延迟/质量对照及 synthetic runner | **效率导向的简单强对照**；预制 pack 不能当作自动跨任务学习证据 |

来源：[pi-hermes-memory](https://github.com/chandra447/pi-hermes-memory)、[Mem0 官方 Pi 文档](https://docs.mem0.ai/integrations/pi-agent)、[abix5 Pi Hindsight](https://github.com/abix5/pi-hindsight)、[Honcho 的 Pi 社区集成页](https://honcho.dev/docs/v3/guides/community/pi-honcho-memory)、[pi-memctx](https://github.com/weauratech/pi-memctx)。

### pi hermes memory 是已有实现而不是原生 Hermes 的等价移植

这是本轮最值得补进候选池的一项：不用从零搬运 Hermes，已经有 Pi 原生代码。固定源为 `c93e2885e57e79ae907cf3d718f9633d066b0217`，MIT；peer 声明 `@earendil-works/pi-coding-agent >=0.80.6`，`better-sqlite3` 是需要核验 Node ABI 的 native dependency。

但不能仅因名字而称“与 c8301ea6 Hermes 行为一致”：

- 默认 **policy-only**：常规记忆按需搜索；与 Hermes 常驻冻结笔记的默认行为不同，`legacy-inject` 才恢复完整笔记注入。
- review 默认是 `pi-ai/compat.completeSimple()` 侧调用，失败时可 fallback 到 Pi 子进程；不是复用 Python `AIAgent` fork。[实际代码](https://github.com/chandra447/pi-hermes-memory/blob/c93e2885e57e79ae907cf3d718f9633d066b0217/src/handlers/review-memory-ops.ts#L740)
- review 有 10 个 `turn_end` 或 15 个工具调用阈值，另外要求至少 **3 个用户 turn**；退出/压缩 flush 默认至少 **6 个用户 turn**。独立单 turn 任务不能假设都会自动形成后台经验；前台工具仍可写入。[触发代码](https://github.com/chandra447/pi-hermes-memory/blob/c93e2885e57e79ae907cf3d718f9633d066b0217/src/handlers/background-review.ts#L196)
- 退出时后台 review 会取消，并有有限等待；这是交互产品的生命周期策略，实验须核对哪些写入已完成、哪些中止，不能把 promise 启动算提交。
- 主会话订阅不能完整记录这个 `completeSimple()` 侧调用和 fallback 子进程。观测需要覆盖它们，而不只是改主 runner。

本轮只读源码，没有安装或验证 Pi 1.0.0＋该插件＋GLM。package 的 semver 范围只是兼容声明，不能替代运行验收。没有使用 README 中“732 tests”作为性能证据。

### Mem0 官方 Pi 插件需要以当前源码为准

固定 `mem0ai/mem0@abb81c88e1f738a8117d8293530fbc31a5ef8fd9`：插件源和 npm 都是 0.3.2；README/文档仍写 0.3.0。当前 entry 使用 `MemoryClient({apiKey})`；自动 recall 在 `before_agent_start`，capture 在 `agent_end`，project scope；主要上传 user/assistant 文本。不是直接复用我们旧 Mem0 classic 实验配置，也不能把旧配置失败推广为它无效。[entry](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/integrations/pi-agent-plugin/src/entry.ts)、[capture](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/integrations/pi-agent-plugin/src/capture/index.ts)

官方六月宣传文章还提到 dream consolidation；当前 README 的六命令、六 skills 和已读 entry 未暴露该流程，因此本轮**不把广告中的 dream 列为当前插件已核验能力**。官方 Pi 默认云路线与 Mem0 引擎本身可自托管是不同层次；不能从后者推断这个插件直接支持所有 OSS 配置。

### Hindsight 和 Honcho 要区分后端与具体适配器

`@abix5/pi-hindsight` 是社区适配器，不是 Hindsight 团队的官方原版 Pi 插件；其 manifest 把 Pi 包放在 dependencies 并约束 `^0.80.3`，不包含 1.0.0，下一步须明确兼容宿主或修接口。另有名为 `runchr-works/pi-hindsight` 的本地反思插件，**不是同一个 Hindsight memory service 接入**，不能混为一个产品。

Hindsight 官方还介绍了 **oh-my-pi 的深度集成**，包含 bank scope、写入队列和自动 recall。但 oh-my-pi 是 fork，不是原版 Pi 加一个 npm extension；它证明已有可借鉴实现，不证明原版 Pi 插件已获同等验证。[官方集成说明](https://hindsight.vectorize.io/blog/2026/06/08/oh-my-pi-hindsight-memory)

Honcho 官方 community 页面指向 `@agney/pi-honcho-memory`。另核对了 `acsezen/pi-memory-honcho 0.3.3`，也是社区项目；两者 manifest 仍使用旧 `@mariozechner` 包命名。本轮没有将“官方文档收录”说成官方作者维护或当前 Pi 1.0 已验证。Agney 的源码还会跳过超出 `maxMessageLength` 的消息，需避免长工具经验消失后仍把该轮标为已完整捕获。

## 效果好到什么程度

| 证据 | 能支持什么 | 不能支持什么 |
| --- | --- | --- |
| Hindsight 论文 | 作者报告 LongMemEval 91.4%、LoCoMo 89.61%；同 20B backbone 的对比从 full-context 39% 到 83.6%，有结构化长期记忆能力证据 | Pi/Hermes 插件＋GLM 的在线任务质量与全成本，或它在所有后端中排名第一 |
| Honcho 官方评测 | 作者报告 LongMemEval S 90.4%、LoCoMo 89.9%，提供按 commit 的结果仓库；页面注明 deriver、dreamer、dialectic 使用不同模型 | 全角色固定 GLM 时仍能取得同样结果；不能与另一论文异模型分数直接排序 |
| Mem0 论文和 Pi demo | 长期对话记忆有公开研究；Pi demo 使用独立进程展示项目约定迁移 | 一个 demo 不能证明广泛稳定收益；论文数字不是 Pi 插件测分 |
| pi-hermes-memory | 现成代码、回归测试、机制与启动性能脚本可审 | 尚无本轮核验的完整任务性能证据 |
| pi-memctx | 作者报告真实 pack 对照平均工具 27.2→1.36、provider tokens 34,385→6,614；提供另一套可复跑 synthetic fixture | 预制 pack 不是在线自产记忆；并非全部质量项改善，也未核验完整构建/维护成本 |

来源：[Hindsight 论文](https://arxiv.org/abs/2512.12818)、[Honcho 评测和模型口径](https://honcho.dev/evals/)、[Honcho 原始结果入口](https://github.com/plastic-labs/honcho-benchmarks)、[Mem0 论文](https://arxiv.org/abs/2504.19413)、[Pi demo](https://mem0.ai/library/coding-agents/giving-pi-agent-project-memory-with-mem0-a-practical-schema-migration-demo)。这些均为公开作者结果，本轮没有复跑。

对 pi-memctx 还需保留反向证据：真实 pack 中两组质量下降（48/50→45/50、44/45→38/45）；公开 synthetic 表的 provider tokens 是 **2450→2615，增加而非降低**，虽然工具调用和延迟下降。其 `setup.sh` 预先写好了知识 pack，`run.sh` 以关键事实命中评分，usage 缺失还有填零口径，不能直接沿用为我们全成本/正确性协议。[固定 README](https://github.com/weauratech/pi-memctx/blob/18e838957c13af0b8c6fe3e2fbc3608935a60c6f/README.md#L139)、[fixture](https://github.com/weauratech/pi-memctx/blob/18e838957c13af0b8c6fe3e2fbc3608935a60c6f/benchmark/setup.sh)

因此，本轮能推荐“有研究依据或工程价值，值得做下一步验收的候选”，不能给出“哪一个已在我们的任务上更有效”的结论。云后端或自托管后端都会发生抽取、embedding、反思、索引及存储成本；自托管不等于推理免费。

## Hermes 有成熟的第三方 provider 接口

**有，而且并非只能挂一个普通 MCP 工具。** 固定 Hermes `c8301ea6` 已有 `MemoryProvider`、`MemoryManager` 和 discovery，负责初始化、context/prefetch、turn sync、session end/switch、pre-compress、记忆写入镜像及 shutdown；具体 provider 可以只实现其中一部分。默认在内置 MEMORY/USER 旁边增加一个外部 provider，**同时最多一个外部 provider**。启用 Hindsight 等后，不能仍把实验条件命名成“纯外部后端”而忽略原生笔记与 skills。[官方说明](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers)、[接口](https://github.com/NousResearch/hermes-agent/blob/c8301ea6c9b797184df16a9c5dd462400b264ff4/agent/memory_provider.py)

| Provider | 当前接入形态 | 主要能力与适合方向 |
| --- | --- | --- |
| **Hindsight** | catalog 安装；vectorize-io 官方仓库维护 Hermes provider | retain/recall/reflect、实体/时间关系、多路检索；最值得优先研究的外部后端之一 |
| **Honcho** | catalog 安装；Plastic Labs 官方仓库维护 Hermes provider | 用户与 agent peers、representation、会话摘要及 dialectic reasoning；偏用户建模 |
| **Mem0** | 此固定 Hermes 仍内置 adapter；Mem0 官方另有 standalone plugin | fact extraction、semantic recall，Cloud/self-hosted server/in-process OSS 三种后端 |
| **OpenViking** | 此固定 Hermes 内置 adapter | 文件系统式知识层次、abstract/overview/full 分层读取；文档/环境知识管理值得保留 |
| **Holographic** | 此固定 Hermes 内置 adapter | 本地 SQLite/FTS、trust/entity 与可选 HRR 检索；轻量候选 |
| **RetainDB** | 此固定 Hermes 内置 adapter | 云端 vector＋BM25＋reranking |
| **ByteRover** | 此固定 Hermes 内置 adapter | 结构化 context tree、本地优先、可选同步 |
| **Supermemory** | 官方文档列为 catalog provider | 跨会话检索及知识服务；本轮只核对接入文档，未做后端代码审计 |

**本轮确认五个内置 adapter 加三个 catalog provider，不声称生态只有八个。** 源码还支持用户/项目插件目录及 Python entry point。上述维护身份分别以框架收录、后端作者官方插件、社区适配器区分；“内置 adapter”不等于 Hermes 团队维护整个后端。

两个实际接入细节比产品名称更重要：

1. **Mem0 重名迁移。** Mem0 官方 standalone README 明确提醒：仍内置 Mem0 的 Hermes 优先使用 bundled provider，安装同名外部插件不会自动替换。我们的 c8301ea6 正是这一情况，不能以为“已安装最新版”就实际调用它。其自动 capture 默认每条消息 450 字符、后台忙时可能跳过、没有 durable queue；需核查实际生效 adapter 与配置。[官方插件说明](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/integrations/hermes-plugin-mem0/README.md)
2. **Hindsight 的服务器端完成。** Hermes 插件有后台 writer，服务端 retain 默认也可异步。客户端已返回/线程已结束不必然等于记忆已可 recall；原生适配已有可见性相关逻辑，但实验仍须登记服务器 operation 完成、bank snapshot/恢复和服务端 LLM 成本。[官方 Hermes 集成](https://hindsight.vectorize.io/sdks/integrations/hermes)、[插件源码](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-integrations/hermes/__init__.py)

## 对当前选型的建议

**把 Pi coding-agent＋pi-hermes-memory 正式放回候选，不因它比 core 复杂而排除。** 它最贴近“完整可修改系统、少造轮子、本地状态可审计”的要求。下一步若继续选型，优先做一次有界无模型接入验收：Pi 1.0/GLM 参数与扩展 API、全角色计费点、单 turn 新会话的写入条件、状态隔离和恢复。先回答“完整机制能否忠实运行”，而不是开始多套大矩阵。

若更看重已有记忆算法的公开性能证据并接受服务端复杂度，优先审查 **Hindsight**；从已有维护归属看，Hermes 的后端作者官方 provider 比本轮找到的社区原版 Pi adapter 更直接，但这不预先决定效果。OpenViking 可作层次化环境知识的后备，Honcho 可作用户建模后备；不建议现在并行实现全部。

本轮是补充调研与候选建议，**没有修改前轮 `base-system-decision.json` 的历史决定，也没有把新候选写成已经通过 S0 验收**。没有安装、接入、性能重复、付费 canary 或更换模型授权；前轮完整报告和成本估计继续保留其原适用范围。
