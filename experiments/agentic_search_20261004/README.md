# 从 48 道简单题历史中自主找证据：三版只读记忆检索系统

日期：2026-10-04（香港时间）。当前状态：已获用户确认，正式 3 × 48 题全部完成并审计；原口径正确率为 24/46、21/46、25/46。用户随后追加的两种原生访问模式也已完成，见 [五模式完整报告](../agentic_native_20261004/五种记忆访问方式实验报告.md)。

本次直接任务是调研、做三版、补齐观测并跑复杂题。研究计划作为背景；它先前“仅更新文档”“下一步只做 P0”的范围不覆盖用户本次新授权，也不自动增加其他 benchmark、重复或在线记忆写入。

## 一个具体例子

简单题历史 `s000` 保存了一次生成正态分布样本的执行：agent 先比较 `np.random.seed` 与 `default_rng` 的输出，再画图并提交代码。库保留了题目、当时执行的代码、输出和最终提交；它没有隐藏测试结论，因此提交过的代码不等于正确答案。

以后求解另一道题时，agent 可以搜索 `numpy random normal`，看到事件 ID，再阅读相关原文。第二版会连同来源题目和成对的操作/输出返回，第三版还可以沿共同代码符号查其他简单题。agent 必须自行判断当时的随机数方法是否适用于当前任务。当前题的搜索过程和新代码仅保存为审计日志，下一道复杂题访问的仍然是同一份简单题库。

## 调研与取舍

以下是官方文档/仓库在本次调研时描述的设计，不把产品自己的性能宣传当作本实验结论。

| 系统 | 官方设计中的重点 | 本次借鉴 | 明确没有复现的部分 |
| --- | --- | --- | --- |
| [Letta / MemGPT](https://docs.letta.com/v1-sdk/memory/archival-memory) | 上下文内存与按需查询的长期存储分开；agent 通过工具自主搜索，支持标签和分页。文档另区分 curated archival memory 与原始 conversation search。 | 自主 search/read、分页、原文可回查；本文语料更接近原始历史搜索 | Letta 完整 agent、语义向量存储、写入和压缩生命周期 |
| [Mem0](https://docs.mem0.ai/core-concepts/memory-operations/search) | 查询时限定用户/会话范围；检索可结合语义、关键词、实体信号并解释排序；MCP 支持主动搜索 | 固定语料范围、结构化来源、排序分量观测 | Mem0 的事实提炼、embedding、reranker、更新/删除机制 |
| [Hindsight](https://hindsight.vectorize.io/developer/retrieval) | 语义、BM25、图、时间等多路召回，RRF 融合后再排序；按读取预算交付 | 多路排序融合、保留每路得分、预算内提供相关上下文 | 神经语义检索、cross-encoder、事实抽取和 reflect；字符相似度不能冒称语义检索 |
| [Graphiti / Zep](https://github.com/getzep/graphiti) | 实体和关系连接到来源 episode，结合关键词、语义和图遍历；时间信息用于事实有效期 | 有类型的可追溯边，以及 agent 按需继续展开 | 通用知识图、LLM 实体归一、事实有效期、冲突消解和 Zep 托管服务 |

选择这些系统是因为它们分别展示了按需访问、混合召回、结构导航这三种设计方向；这里没有做流行度排名。实现名称不使用产品名，结果不能写成“击败/复现 Mem0、Letta 或 Graphiti”。

## 三版实际差异

| 方法 | 搜索与返回方式 | 工具 | 要检验的假设及可能代价 |
| --- | --- | --- | --- |
| `lexical` | 对原始事件做 BM25；每页最多 5 个命中，返回有界片段；可以继续读原文 | `MEMORY_SEARCH`、`MEMORY_READ` | 简单关键词访问是否已足够；可能需要多次补读前提或工具结果 |
| `hybrid_context` | BM25 与字符 trigram TF-IDF cosine 各取 top-40，再以 `1/(60+rank)` 融合；同页去重，并补来源题目与相邻成对操作/观察 | 同上 | 标识符近似匹配及成组交付能否少走一次查找；也可能弱匹配增多、返回更多字节 |
| `graph_walk` | 与第一版相同的 BM25 起点；返回代码符号及链接数量，agent 可按时间相邻、操作—观察、共同符号继续查 | 前两项加 `MEMORY_FOLLOW` | 当前事件是否能引导找到其他相关证据；也可能增加不必要的探索 |

三版是**系统层面的差异比较**。第二版同时改变排序和上下文包装，第三版新增导航入口；首轮成绩不能独立归因于某一个机制。必要消融另行申请，不自动增加实验。

共同规则：不预先注入历史、不强制查询、无额外 reader/writer 模型、无 embedding API、无跨复杂题学习。空 query 可按页列出整个库；所有版本都能通过事件 ID 逐段阅读所有合法历史。`MEMORY_READ` 的字符偏移是 Python Unicode code points，另返回 UTF-8 byte 范围、全文哈希、来源路径和后续偏移。

图中的共同符号用确定性 qualified-identifier 匹配取得，只连接出现在 2–24 个事件中的符号。边表达“相邻/配对/共同出现”，不表达事实等价或经过验证的推理；`task_func` 等泛化名称不构成跨题配对键。

## 数据和访问边界

- 唯一语料是 [已有冻结简单题库](../section7_frozen_jaccard_20261004/records/simple-library.json)：48 个 no-memory 来源、279 个事件。来源库 canonical hash 为 `dac0179536ec6d1316507b86d7bdbd542345209c5c52492e4b60ef61f0882914`。
- `prepare` 逐条用旧简单题 `pi-result.json` 的可见 text/toolCall/toolResult 重建并核对；排除 reasoning、隐藏测试、评分、对应复杂题 ID 和研究批注。不按成功分数筛选来源。
- 复用 AgentCL codeeval 的复杂题索引 48–95，每个方法 48 题、R=1，总共 144 次。原有评分资格保留为每版 46 题，全部 48 题均计成本。
- 每次运行创建独立 Pi 进程、工具服务、工作目录、Session 阅读集合和日志目录。三版/144 题仅共享只读索引；无 insert/update 工具、无复杂题 memory episode 文件、无搜索日志回灌。
- solver 的 PYTHON 在既有 WSL namespace 沙箱中，只挂当前题工作目录；其他工作目录、库文件、审计日志、评分资产和网络不可访问。隐藏测试在提交后的独立评分沙箱引入。
- 模型看到的 source ID 只表示简单题档案位置，未暴露源与复杂题的配对映射。当前题自己的正常上下文可以保留。

## Observability 是否够用

旧日志能支持新旧质量、原生工具动作和总 usage 的描述性比较，但不能从旧的静态注入日志还原自主查询行为。新加的观测如下，验收证据在 [fixtures.json](records/fixtures.json)。

| 观测 | 旧底座 | 本轮实现 |
| --- | --- | --- |
| 来源、配置、版本、评分资格 | 有状态哈希与分数 | 增加逐条来源重建、279 事件索引哈希、源文件和实现依赖冻结 |
| 搜索/阅读/展开 | 原来只有任务前选取 | `memory-access.jsonl` 保存参数、全量可观测候选/得分、图边、空命中、范围、截断、耗时、错误 |
| 实际可见证据 | 原来只映射静态 system 注入 | `memory-results.jsonl` 留存实际工具结果；`memory-exposure.jsonl` 将其关联每次真实 provider request 的 message index 和 body hash，并检验内容未变 |
| 重复与上下文移除 | 旧记录不能直接回答动态阅读 | 记录重复 source 字符范围；每次 payload 标识哪些已返回结果可见/不在该 payload 中。当前不启用额外压缩 |
| 之后的行动 | 有原生工具与提交 | memory tool_call_id → generation/call_id → PYTHON/SUBMIT → 隔离评分可串联；不要求或用隐藏思维链判断需求 |
| 延迟 | 有请求、工具大类时间 | 加搜索耗时、每次工具 HTTP 往返、sandbox 排队/执行、首个观察到的 stream body/text/tool delta 时间 |
| 成本与失败 | 记录原始 provider usage、重试尝试和角色 | 复用；503 与成功但缺 usage 均保留 unknown，所有尝试计入；无 writer/embedding 调用，货币成本无已验证价格时仍为 unknown |

因此，新日志足够回答“搜了什么、实际读了什么、之后干了什么、用了多少可观测资源”的 D0 问题。**仍不能直接推出**：模型真正使用了哪条记忆、没有返回的证据不存在、一次检索具有因果增益、每个片段的精确 token/缓存归因、同样结果可稳定复现。语义解释和反事实干预另列，不把 `repeated_source_chars` 当 token，也不把 relevance score 当正确率。

历史缺失的原始请求、失败 usage 或流式时间不能补造；新采集解决的是本轮和未来的可观测性。

## 已确认的正式配置（冻结原准备记录）

完整配置：[proposed-config.json](records/proposed-config.json)。

| 项目 | 拟沿用/新增的限制 |
| --- | --- |
| Solver | GLM `glm-5.3-flash`，reasoning high，每轮最多输出 8192 tokens；temperature/seed 省略；模型为可变别名 |
| 总范围 | 3 × 48 复杂题，R=1；不增加无记忆/Jaccard 重跑，不做性能失败重试 |
| 并发 | 先每版第 48 号目标各 1 题做接入 canary，这 3 题计入 144；通过观测验收后全局最多 48 个独立任务，8 个本机执行/评分沙箱 |
| 每题预算 | 18 模型轮、15 次 PYTHON、600 秒；单次响应 180 秒；请求最多 320,000 UTF-8 bytes |
| 记忆预算 | 最多 12 次 memory 调用；含证据的响应累计 ≤48,000 UTF-8 bytes，单次 ≤12,000；读取也消耗上述 18 轮。预算拒绝消息单独计日志/模型 tokens，不隐含无限证据 |
| 请求重试 | 每次生成最多额外 2 次 SDK 传输重试；正常答错、不查询、格式失败、预算耗尽不重试 |
| 总额边界 | 最多 2,592 次生成、7,776 次 HTTP 尝试；没有已核验价格，不能把 token 数冒称金额或承诺报价。是否采用额外货币/总 token 硬上限需另行明确实现 |
| 停止 | 来源、隔离、可见性审计、基础设施或评分失败，或出现未知 usage，停止新增分发，保留在途尝试；不自动扩大范围 |

48 个历史来源的 137,698 tokens 单列为既有语料生成成本，不重复当本轮支出；本轮索引构造是确定性本机计算，耗时单独记录。新增检索与求解的全部请求才是本轮模型成本。

## 复现与交付入口

准备和 fixture 均无付费调用：

```powershell
python -X utf8 experiments/agentic_search_20261004/run.py prepare
python -X utf8 experiments/agentic_search_20261004/fixtures.py --sandbox
python -X utf8 experiments/agentic_search_20261004/run.py check
```

复用既有 Pi 安装、AgentCL cache 和 WSL sandbox/broker，依赖说明见仓库 [REPRODUCING](../../docs/REPRODUCING.md)。服务未启动时先启动已有 `section7_observability_20261002/broker.py`；启动 broker 不调用模型。所有凭据仅通过现有本地机制读取，不提交到 Git。

用户确认已写入 `records/approval.json`，包含 `approved: true`、配置 hash 和用户授权原文/时间。正式入口依次为 `run.py canary`、`run.py remaining`，随后 `audit.py` 全量审计并汇总；这三个步骤本轮均已完成。审批文件不存在或 hash 不匹配时不会读取凭据或发出模型请求。

主要代码：[memory.py](memory.py)、[run.py](run.py)、[recorder.mjs](recorder.mjs)、[audit.py](audit.py)。原始新运行位于旧 runtime 下独立的 `agentic-search-20261004-v1-codeeval-*` 命名空间；完成后应归档原始日志及 hash 清单，再报告逐题配对的质量、PYTHON、memory calls、tokens/cache、延迟、重复读取和未知项。旧实验输出不改写。
