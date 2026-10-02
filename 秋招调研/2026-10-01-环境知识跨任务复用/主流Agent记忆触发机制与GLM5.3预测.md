# 主流 Agent 的记忆触发机制与 GLM 5.3 场景预测

核查日期：2026-10-01。对象为 Codex、Claude Code、Hermes Agent、OpenClaw、Cursor。问题是：谁决定保存什么，什么事件触发写入，后续任务如何获得记忆，以及固定 GLM-5.3 后 a/b/c 实验可能出现什么结果。

**主要判断：这些产品没有统一的“任务结束必写、下一题必搜”协议。** 常见实现是程序安排处理机会，模型判断内容价值；读取既可能是启动时固定加载，也可能由模型调用工具，还可能有程序自动召回。它们的默认开关、会话类型、异步等待和知识保存位置，足以显著改变实验结果。

**预测：在当前有明确 g1/g2 表名的单位题上，首先拉开差距的更可能是记忆的形成与可见性；在有效记忆已经进入上下文后，b 的探索成本可能下降，而 c 不一定发生稳定负迁移。** 这是机制推断，不能当作 GLM-5.3 实测成绩或框架排名。

本轮未安装或运行这些 Agent，未请求任何模型 API。核对了官方文档和固定提交源码；47 份抓取文件的 URL、版本和 SHA256 见 [来源核查](框架记忆机制来源核查.json)，脚本为 [audit_framework_memory.py](audit_framework_memory.py)。Cursor 另以当前官方页面与有日期的历史发布记录核查，其闭源内部实现未取得。

## 阅读这些结果时需要的边界

- **源码确认**表示指定提交包含该逻辑，不保证当前任意安装包都已发布这一提交。
- **官方说明**表示产品承诺或文档描述，没有在本机验证触发成功率。
- **预测**是在写明配置和任务条件后，对可能行为的推断，不填造百分比。
- 人工规则文件、同会话上下文、自动提炼的经验、历史会话检索和 Skill 是不同路径；都可能帮助任务，但应分别归因。
- 本机 npm Codex 包为 0.128.0，仅用于确认本地可见包版本，不能替代桌面宿主版本，也不代表其他框架已安装。

源码快照：Codex `57ac6f51639f7cad705a48ac4bd8073034a2f150`；Hermes `357f51c49106f47136caf9b01015467b7b633fe8`；OpenClaw `4d1890a3cdc3b8f31ac70bb63e19723fee0cc6a9`。

## Codex

### 写入由什么触发

官方说明：本地 memories 默认关闭。开启后，合格旧会话在后台生成记忆，避免处理仍活跃或过短的会话，并非每个任务结束立刻提炼。[Memories](https://learn.chatgpt.com/docs/customization/memories)

固定源码中，非临时、非子 Agent 的根会话启动会安排异步 memory pipeline，还需启用功能且状态数据库可用。流程分为：

1. 从旧会话中选择符合来源、年龄、空闲时间等条件的候选，调用提炼模型。
2. 将阶段一输出交给全局整理流程，生成或更新持久文件。

提炼提示词要求判断内容能否改善未来行为，允许没有值得保留的内容时返回空结果。因此“后台工作执行过”和“保存了价格单位”不是同一件事。[启动源码](https://github.com/openai/codex/blob/57ac6f51639f7cad705a48ac4bd8073034a2f150/codex-rs/memories/write/src/start.rs)、[提炼源码](https://github.com/openai/codex/blob/57ac6f51639f7cad705a48ac4bd8073034a2f150/codex-rs/memories/write/src/phase1.rs)、[提炼提示](https://github.com/openai/codex/blob/57ac6f51639f7cad705a48ac4bd8073034a2f150/codex-rs/memories/write/templates/memories/stage_one_system.md)

当前配置参考给出的 `min_rollout_idle_hours` 默认值为 6，允许范围 1–48；`max_rollouts_per_startup` 默认 16。配额阈值也可能跳过一个生成批次。这意味着 a 结束几秒后运行 b，通常不能假设 a 已经转成可用的自动记忆。[配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)

还有一个自动化实验陷阱：本轮源码允许抽取的 interactive 来源列表包含 CLI、VSCode、atlas、chatgpt，没有列出 Exec。不能默认用一次性 `codex exec` 产生的轨迹就与交互会话拥有相同记忆生成资格；须核对实际记录的 source，而不是伪造 source 来冒充原生行为。[来源白名单](https://github.com/openai/codex/blob/57ac6f51639f7cad705a48ac4bd8073034a2f150/codex-rs/rollout/src/lib.rs#L88)

### 读取由什么触发

当前读路径向 Agent 提供紧凑摘要和记忆访问指导，再由模型按工作区、项目、历史决定等线索检索 `MEMORY.md` 和相关记录。它不是把所有历史全文直接加载，也不是固定每题运行一次向量检索。摘要自动可见与细节被读取是两个事件。

该源码提示还将主对话的显式记忆修改限制为用户要求后的 ad-hoc note；后台提炼是另一条写入路径。不能因为主 Agent 没有主动写 memory 文件，就断言 Codex 不生成记忆。[读路径提示](https://github.com/openai/codex/blob/57ac6f51639f7cad705a48ac4bd8073034a2f150/codex-rs/ext/memories/templates/memories/read_path.md)

### 放到 a/b/c 场景

- 默认关闭或立即进入 b：预计自动经验收益弱或没有，原因可能只是尚未生成。
- 开启、a 来源合格、满足空闲条件且提炼完成后再开新会话：单位知识可能进入摘要或索引；b 再检索细节，可能减少探索。
- c 是否受到影响取决于摘要是否保留 g2 范围、是否被读取及当前证据。没有机制依据断言 c 必降。

## Claude Code

### 写入由什么触发

Auto memory 默认开启。当前官方文档描述模型在会话中决定哪些信息值得供未来会话使用，用户明确要求记住也是触发方式；不是每会话都必须写。

文档列出的内容类型是 user、feedback、project、reference，并明确跳过可从代码或 git 重建的信息与已有 CLAUDE.md 内容。这使其更偏向用户偏好、纠正、外部上下文和不可直接重建的项目知识。数据库单位是否被判为值得保存，仍取决于它是外部环境经验，还是容易从当前材料重新得到的事实。[官方 auto memory 说明](https://code.claude.com/docs/en/memory#auto-memory)

### 读取由什么触发

新会话自动加载 `MEMORY.md` 索引前 200 行或 25KB，取先达到的限制；详细主题文件按需通过文件工具读取。默认按仓库归属共享，worktree 不自动构成独立记忆隔离。CLAUDE.md 等项目指令是另一条加载路径。

因此“一条经验写进主题文件”不等于“b 已看到全文”；它可能只看到索引，需要再读文件。官方页面足以支持模型选择性读写的描述，但未公开每次语义决策的确定性阈值，不能声称发现了一个固定置信度算法。[加载机制](https://code.claude.com/docs/en/memory#how-it-works)

### 放到 a/b/c 场景

- 一次 a 是否写出单位事实：不确定，默认开启不能替代内容检查。
- 若索引和主题文件保留事实，同仓库新会话 b 有明确读取入口，预计更可能节省探索。
- c 与 b 同仓库时也可能获得索引，但 g1/g2 差异并不会被仓库范围自动处理，仍需模型判断事实范围。

## Hermes Agent

### 写入由什么触发

至少有两条原生路径：

- 前台模型主动调用 `memory`，执行 add、replace、remove。工具成功才是持久化；自然语言承诺不算。
- 回合后后台 review，在计数条件满足且没有关闭时运行，让模型判断是否保存或更新 memory/skill。它允许没有内容可保存时退出。

本轮固定源码中，内置 memory nudge 默认每 10 个用户回合触发一次计数门槛；回合成功返回且满足 review 条件后才启动后台流程。这个 10 不是 SQL 查询次数。Skill review 另按工具迭代计数。**一个用户消息完成的短 a，不会仅因“任务完成”就必然触发周期 memory review。**[默认配置](https://github.com/NousResearch/hermes-agent/blob/357f51c49106f47136caf9b01015467b7b633fe8/hermes_cli/config_defaults.py#L1324)、[计数器](https://github.com/NousResearch/hermes-agent/blob/357f51c49106f47136caf9b01015467b7b633fe8/agent/turn_context.py#L718)、[回合结束逻辑](https://github.com/NousResearch/hermes-agent/blob/357f51c49106f47136caf9b01015467b7b633fe8/agent/turn_finalizer.py#L737)

当前前台提示强调：任务相关的程序、陷阱和纠正优先进入 Skill；常驻 memory 用于跨任务稳定事实。后台提示同时允许保存工具特性、项目约定等环境知识。因此价格单位可能进入 MEMORY，也可能进入 Skill 或仅停留在会话历史，不能先假设保存位置。[写入指导](https://github.com/NousResearch/hermes-agent/blob/357f51c49106f47136caf9b01015467b7b633fe8/agent/prompt_builder.py#L195)、[后台判断](https://github.com/NousResearch/hermes-agent/blob/357f51c49106f47136caf9b01015467b7b633fe8/agent/background_review.py#L357)

### 读取由什么触发

内置 `MEMORY.md`、`USER.md` 在会话启动时直接进入 system prompt，冻结快照供本会话使用；默认容量分别为 2,200、1,375 字符。这个小型核心记忆不需要先搜索，也没有单独的 read 操作。新写入的事实不会自动出现在已经运行的另一个会话快照中。

更长历史由 `session_search` 查询；提示要求在用户提到过去对话或模型怀疑存在相关历史时使用。Skill 则有自己的发现与按需加载路径。外部 memory provider 插件可能再增加自动提炼和预取，不应算作纯内置配置。[官方机制](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/)、[历史调用指导](https://github.com/NousResearch/hermes-agent/blob/357f51c49106f47136caf9b01015467b7b633fe8/agent/prompt_builder.py#L238)

### 放到 a/b/c 场景

- **条件判断较强：如果单位事实已经写进核心 MEMORY，之后的新会话 b/c 都能直接看到它，不依赖检索命中。**
- 无法由此倒推出 a 很可能写它；短任务、Skill 优先、容量和后台完成时间都影响结果。
- 若事实保留 g2 范围，b 可能直接复用而 c 正确排除。若压缩丢掉范围，b/c 都暴露于过度泛化；“总是带入”同时增加有用和无关经验的曝光。

## OpenClaw

### 写入由什么触发

当前默认 memory-core 周围存在多种独立机制：

1. 模型按工作区指令主动写 `MEMORY.md` 或每日笔记；明确的“记住”请求也可触发。
2. 临近上下文压缩时，默认开启的 memory flush 安排一个静默回合，提醒模型保存重要信息；写权限不足时跳过。
3. 启用 bundled `session-memory` hook 后，在 `/new`、`/reset`、每日或空闲重置事件保存此前最近若干用户／助手消息；默认 15 条，后台写文件。这是保存记录，不等同于提炼了正确单位。
4. 默认 dreaming 后台整理从候选中按确定性门槛和模型判断逐步提升长期事实；a 的一次新观察不必立即成为长期记忆。

来源：[机制概览](https://docs.openclaw.ai/concepts/memory)、[会话重置 hook](https://github.com/openclaw/openclaw/blob/4d1890a3cdc3b8f31ac70bb63e19723fee0cc6a9/src/hooks/bundled/session-memory/HOOK.md)、[Dreaming](https://docs.openclaw.ai/concepts/dreaming)。

### 读取由什么触发

不能只概括为“模型自行决定搜不搜”。当前存在三层：

- 启动上下文：在适用会话中带入长期记忆等文件；每日笔记在特定新建／重置路径加载，受文件预算及会话范围限制。
- 自动召回：符合资格的交互回合用入站消息匹配可信长期记忆的触发短语；强匹配可自动带入少量片段，不需要主模型先发起搜索。该路径不自动注入每日笔记和普通历史转录。
- 按需深查：主模型可调用 `memory_search`／`memory_get`；工具说明要求涉及过往工作、决定等问题先召回。启用且满足范围条件的 Active Memory 默认使用 `escalate`：存在历史回忆意图且自动路径没有强命中时，才运行深查子 Agent。

Active Memory 不在 headless one-shot、heartbeat、内部 helper 或子 Agent 等所有入口统一运行。不能把一个命令行自动化跑分当作其交互产品记忆行为的完整代表。[Memory search](https://docs.openclaw.ai/concepts/memory-search)、[Active Memory 入口与升级条件](https://docs.openclaw.ai/concepts/active-memory/how-it-works)、[工具提示](https://github.com/openclaw/openclaw/blob/4d1890a3cdc3b8f31ac70bb63e19723fee0cc6a9/extensions/memory-core/src/memory-tool-contract.ts#L114)

### 放到 a/b/c 场景

- 短 a 没有压缩、没主动写、没有启用重置 hook 时，不应期待必然留下经验。
- 保存每日记录、整理为长期事实、创建触发短语和更新检索索引是不同状态。需要检查具体到了哪一步。
- 只给 b 一个新 SQL 问题，不说“根据上次”，未必触发以历史回忆意图为条件的深查；长期核心事实和自动触发召回仍可能提供经验。
- 可能有更充分的召回，也可能多花一次 helper 调用；无法仅凭组件更多就预测最终成绩更高。

## Cursor

必须区分三个产品面，不能把几年前的 Memories 说明直接当当前全部行为。

### 当前可直接核实的 IDE Rules

当前 Rules 文档明确支持：每次都加载、按文件 glob 加载、Agent 根据 description 选择、用户手工 @ 引用。用户可以让 Agent 从对话生成规则，但文档没有保证每次解完 a 都自动把环境事实转成规则。

SQL 数据库中的 g1/g2 表不是两个匹配不同 glob 的源代码文件，因此不能自动假设“按文件规则”就能区分这两个事实范围。[当前 Rules](https://cursor.com/docs/rules)

### 历史 IDE Memories

2025-07-03 的 Cursor 1.2 发布记录证实，后台生成的 Memories 引入了用户批准。旧官方文档的搜索存档描述旁路模型观察对话、以及 Agent 工具写入两条路线；但本轮直接打开旧文档 URL 已重定向，当前实现细节未验证。因此历史 sidecar 仅作为历史机制，不用于肯定当前安装版的自动触发条件，更不能断言它跟随用户选择的 GLM 模型。[有日期的发布记录](https://cursor.com/changelog/1-2)

### 当前 Cloud Automations

当前 Automations 官方文档明确提供默认开启的跨运行 memory 工具；笔记以命名条目保存，默认名 `MEMORIES.md`，在工作文件系统之外，按同一个 automation 复用。Agent 可以读、写、删，但文档未给出足以确认“每次运行必读必写”的内部判定逻辑。

这个产品面有明确跨运行持久状态，却不是把本地 IDE Agent 换成 GLM 就自动得到的能力；需另核实云端支持的模型与权限。[Automations](https://cursor.com/docs/cloud-agent/automations)

### 放到 a/b/c 场景

当前最可靠的判断是条件性的：若 a 没有产生可用规则或持久条目，b 没有跨题收益；若事实进入 Always 规则，b/c 都可见；若按需规则，则取决于选择。对未经核实的当前 IDE 自动 Memories 不给高低排名。

## 固定 GLM 5.3 能不能公平比较

GLM-5.3 本身已有官方模型与集成说明。需要固定完整 model ID、服务端点、推理强度和上下文配置，不能混入 GLM-5.3-Flash。[GLM-5.3](https://docs.z.ai/guides/llm/glm-5.3)

|框架|主模型接入证据|固定同一生成模型仍需处理什么|
|---|---|---|
|Codex|Z.AI 已给出 `glm-5.3` 的 Responses endpoint、模型目录与配置示例|记忆提炼、整理是独立模型配置；不能只修改 `model`|
|Claude Code|Z.AI 提供 Anthropic-compatible 路由及 GLM 模型映射|默认示例可能映射到 Flash；要核实主调用、辅助模型别名与实际请求|
|Hermes|官方提供 `zai` provider；后台 review 默认继承主模型|检查 review、compression、Skill、外部 memory 插件和 fallback 是否另选模型|
|OpenClaw|官方支持 `zai` provider|flush、dreaming、Active Memory 的模型、思考强度及 fallback 都要核查；embedding 另行登记|
|Cursor|Z.AI 提供 IDE custom model 接入方法|不等于所有旁路服务换成 GLM；当前 Cursor BYOK 文档与 Z.AI 示例覆盖范围不同，云端 Automations 接入需另验|

来源：[Codex 接入](https://docs.z.ai/devpack/tool/codex)、[Claude Code 接入](https://docs.z.ai/devpack/tool/claude)、[模型切换与 effort 映射](https://docs.z.ai/devpack/latest-model)、[Hermes providers](https://hermes-agent.nousresearch.com/docs/integrations/providers/)、[OpenClaw Z.AI](https://docs.openclaw.ai/providers/zai)、[Z.AI Cursor 接入](https://docs.z.ai/devpack/tool/cursor)、[Cursor BYOK 范围](https://cursor.com/help/models-and-usage/api-keys)。以上均为文档接入证据，未做调用验证。

Codex 的独立模型配置尤其具体：本轮 provider 基础实现的 memory extraction/consolidation 首选分别为 `gpt-5.6-luna` 和 `gpt-5.6-terra`，允许提供者或配置覆盖。只把解题模型改为 GLM，可能仍有其他模型参与，或因所选 endpoint 不支持这些名称而失败。应核对 `memories.extract_model`、`memories.consolidation_model` 和实际调用日志。[源码](https://github.com/openai/codex/blob/57ac6f51639f7cad705a48ac4bd8073034a2f150/codex-rs/model-provider/src/provider.rs#L128)

由此产生两种不同实验，必须分开命名：

- **固定主模型的产品比较**：解题都使用 GLM-5.3，其余保持各产品机制，逐项披露后台模型及全部成本。
- **固定全部生成模型的框架比较**：解题、提炼、整理、深查等都使用 GLM-5.3；改动相应路由，并检查实际请求。无法控制的闭源旁路不能冒充已固定。

embedding 不属于生成模型，但仍是额外模型与资源。可以在可配置框架间固定同一 embedding；原生比较若保留各自检索器，必须报告差异。相同模型也不能消除工具实现、系统提示、恢复机制和预算差异，因此主比较测的是完整 Agent 系统，而非单独 memory 算法。

## 对 a b c 结果的具体预测

假设：a/b/c 是独立新会话，同一数据环境；g2 价格为美分，g1 为美元；Agent 有正常探索权限；没有人工要求一定记住或一定使用；b/c 从同一份 a 后状态分别启动，互不污染。只预测单位知识这项作用，不预测整道复杂 SQL 题必然成功。

|条件|a 后最可能需要担心什么|b 的预期|c 的预期|信心|
|---|---|---|---|---|
|Codex 默认配置或 a 后立即开 b|未启用、来源不合格、空闲门槛或后台尚未完成|经验收益较弱，可能接近从头探索|没有暴露经验时，也没有这条经验造成的负迁移|触发条件高；实际效应未测|
|Codex memory 开启且处理已完成|提炼是否保留事实、b 是否读到细节|可能减少重复 schema/单位探索|正确范围被保留时，倾向于正确区分 g1/g2|中低|
|Claude Code auto memory|一次 a 的事实可能被视为可重建而不保存|保存并按需读到时可能省探索；否则收益小|索引可见不等于误用；强模型有当前范围线索|中低|
|Hermes 内置路径|事实进入 MEMORY、Skill、历史哪一层；短 a 未到周期门槛|写入核心后可见性较确定；进入其他层则依赖发现／读取|核心事实也会进入 c；保留范围时预计能拒绝，失去范围时才更容易误用|可见性高；写入及效果中低|
|OpenClaw 合格交互路径|是否落盘、索引完成、是否提升为可信长期项；入口与回忆意图是否匹配|可能直接带入，也可能走搜索／深查；成本波动较大|自动召回可能带入相似经验，但范围与当前证据可阻止误用|中低|
|Cursor 本地 IDE|当前自动 Memories 能力未确认；没有自动生成规则的保证|不能预设跨题收益；规则存在后按配置触发|Always 规则都可见，按需规则可能不加载；最终仍由模型判断|低|

**总体上，我不预期这组基础单位题自然形成稳定的“某框架 b 大涨、c 大跌”排序。** 理由有三：

1. 一次 a 可能没有留下对应记忆，测到的是写入或调度差异。
2. 强模型能从当前环境重新确认单位，记忆更多体现为少查几次，而非更高正确率。
3. 写得合格的记忆本来就限定在 `items_g2`；c 明确问 g1，区分条件比较明显。正确拒用时，c 不下降是正常结果。

更可能暴露问题的情况是大量混合经验、异步更新、同一环境中的版本变化、摘要丢失事实范围等。但这些只是下一步待验证的条件，不是为了制造失败而删除真实边界信息的理由。

## 根据调研调整第一轮实验

首轮建议先用 **Hermes + Claude Code + Codex**，分别覆盖常驻小记忆、项目索引加按需读取、异步提炼加检索；OpenClaw 作为入口与召回机制更丰富的第二组。Cursor 先确认具体产品面、版本和实际模型路由，再纳入严格控制组。这个次序依据可观察性和实验接入成本，不是性能排名。

每个框架先检查一组三元组的完整链路：

1. 记录精确版本、模型请求 ID、provider、全部生成角色、思考参数、memory 开关、scope、插件和会话入口。
2. 完成 a，检查它是否真的观察到单位，是否持久化，以及保存为事实、Skill 还是原始历史。实验端审计，不把 gold 或目标标签透露给写入模型。
3. 保留两个时间口径：a 结束即开 b 的即时可用性；等待**实际后台处理完成**后再开 b 的就绪可用性。未产生相关记忆仍保留为结果，不能等到得到想要的事实才宣布就绪。
4. 在框架状态完成持久化后分叉 b/c。程序仍异步写入时先核实快照一致性；不要让 b 新经验进入 c，也不要把三个任务续在同一聊天里冒充跨会话记忆。
5. 无经验对照使用同一完整 Agent 和工具；另加同会话历史、简短带范围事实手册。保留当前任务内正常推理与恢复能力。
6. 看写入内容、实际模型输入和可见工具行为，分别报告保存率、暴露率、适用／不适用任务的配对变化以及总成本。统计文本指标允许语义等价，不要求特定文件名或精确措辞。

两个不能忽略的结论：**没用上不等于记忆无效；c 没退步也不等于系统完成了适用性判断。** 如果它只是不写或不读，必须连同 b 上失去的收益一起报告。

本轮的可交付结论是触发机制与实验边界；下一轮实际 smoke test 才能确认 GLM-5.3 在指定版本上的工具兼容、记忆形成和读取行为。
