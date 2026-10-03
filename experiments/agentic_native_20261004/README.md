# 让模型自己逛记忆文件：新增两种原生访问模式

2026-10-04（香港时间）。用户在前三版运行期间提出：希望接近 Codex / Claude Code 的原生记忆访问，由模型自己决定看什么、怎么看；额外设计两版，运行不再确认配置。本目录记录这项追加任务，共新增 2 × 48 = 96 次复杂题执行，和前三版合计 240 次，均为 R=1。

**已全部完成并审计。** 原生文件版 25/46、原生终端版 24/46；完整成本、逐题比较、访问行为与证据归档见 [五种记忆访问方式实验报告](五种记忆访问方式实验报告.md)。

## 调研得到的区别

前三版已有自主查询和阅读，但接口仍以排序命中、固定大小片段和预设关系作为主要入口。用户要求的方向更接近：给 agent 一个记忆文件目录和普通工具，由它规划浏览、搜索、打开和继续查找的过程。

- [Codex Memories 官方文档](https://learn.chatgpt.com/docs/customization/memories)描述本机 `~/.codex/memories/` 中的摘要、长期条目与来源证据。文档本身不完整规定每一步搜索算法，不能据此声称复现了 Codex 内部检索。
- [OpenAI Sandbox Agents 官方文档](https://developers.openai.com/api/docs/guides/agents/sandboxes)明确描述渐进读取：先提供 `memory_summary.md`，相关时搜索 `MEMORY.md`，有需要再读详细记录；记忆读取需要 shell。它是公开可参考的文件记忆协议，不等同于完整 Codex 产品。
- [Claude Code memory 官方文档](https://code.claude.com/docs/en/memory)描述一个 `MEMORY.md` 索引和分开的详细文件；启动时加载索引的前 200 行或 25KB，详细文件由 agent 使用标准文件工具按需读取。[执行机制说明](https://code.claude.com/docs/en/how-claude-code-works)也将文件、终端和模型反复收集上下文的循环作为底座。

本次借鉴读取方式，继续固定历史来源与保存规则。没有启用两家产品的自动 writer、后台总结、压缩或新模型，也不把 GLM + Pi 称为 Codex/Claude Code 原生效果复现。

## 两种模式

| 模式 | 模型开始时拿到什么 | 模型能自主决定什么 |
| --- | --- | --- |
| `native_files` | 6,295 UTF-8 bytes 的逐条 `MEMORY.md` 索引；每条描述直接摘自简单题题面 | 用 `MEMORY_GLOB` 列文件，`MEMORY_GREP` 选择 regex/glob/上下文行/输出模式，`MEMORY_READ_FILE` 选择文件与行范围；可以跳过、改词、跨文件、续读 |
| `native_shell` | 486 bytes 的 `memory_summary.md`，说明目录和入口 | 在真正的隔离 Bash 中用 `rg`、`find`、`cat`、`sed`、`head`、管道或脚本组织查询；自己决定先读索引还是直接搜全文、如何处理输出、何时停止 |

两版都没有 BM25/向量/top-k、隐藏候选筛选、自动邻域扩展或模型代读。原文完整放在 48 个 `episodes/*.md` 与 48 个 `raw/*.json` 中，加两个索引共 98 个文件。Markdown 将可见历史代码和输出排版为便于阅读的转录，JSON 保留原始合法值；不加入隐藏正确率或人工修正的解法。

**两个模式的启动披露不同**：文件版直接给逐条索引，终端版只给目录入口。这是两种原生访问配置的整体比较，不是仅更换工具名称的消融；索引字节也扣入每题记忆预算，并在实际请求中逐次记录。若需要将界面差异与初始信息差异拆开，须另做受控消融，本轮不追加。

共同语料仍是 canonical hash `dac0179536ec6d1316507b86d7bdbd542345209c5c52492e4b60ef61f0882914` 的 48 道 No Memory 简单题。没有读取其他复杂题日志来构造这些文件，也不按来源成绩筛选。

## 隔离和观测

文件工具只能访问 manifest 中注册的路径，拒绝 `..`、未注册文件和复杂题 ID。终端将同一份语料挂载到只读 `/memory`；`/work` 是该次工具调用的独立临时目录，复杂题业务文件、其他任务、host、凭据和网络不可见。原有 PYTHON/提交/评分环境不变。

终端新增独立 `strace`，跟踪器在 agent 的 chroot 外写日志，agent 不能接触它。记录 command、原始 stdout/stderr、返回码、截断、打开的记忆文件及哈希。读取工具逐段验证文件/行/字符范围；两版都将实际工具返回内容逐字映射到真实模型请求，并继承原有 HTTP、重试、usage、工具与提交评分链。

**文件打开与内容曝光分开记录**：一个命令可能读取全文件但只输出行数，也可能通过脚本转换文本。终端 stdout 是否进入请求可以精确核验；打开文件列表不是全部内容已被模型看到的证明，不能拿它冒充逐行引用或真实 recall。终端的“重复 source 字符数”保留 unknown，不填零。

## 预算与执行

沿用 GLM `glm-5.3-flash`/high、8192 output tokens、每题 18 模型轮/15 PYTHON/600 秒、每响应 180 秒、320KB request guard；每题 12 次记忆工具、包含启动索引在内共 48KB 证据、单响应 12KB。Bash 每命令最多 30 秒、512MiB 虚拟内存；PYTHON 和 memory shell/评分共用 8 个并发沙箱槽，全局最多 48 个独立任务。

每版首题各一次接入 canary 计入该版 48 次，验收通过后跑剩余 94 次。最多额外 2 次传输重试，不重试到成功；未知 usage、隔离/来源/观测或基础设施异常停止新派发。执行 48、主评分 46 的原 mask 保留。模型别名可变，货币费用缺少已验证单价时仍为 unknown。

无付费验收包括 96 个独立文件会话、路径/复杂来源拒绝、regex/分页/长读取预算、真实 readonly mount 写入拒绝、网络/host/凭据隔离，以及真实 Pi 对本地模拟 provider 的 9 个请求。首次 strace 检查发现 `-yy` 将目录 fd 显示成 host mount 路径；已在正式付费前补充路径归一和 unfinished/resumed syscall 拼接，并重做验收。

配置：[config.json](records/config.json)。语料映射：[corpus-provenance.json](records/corpus-provenance.json)。验收：[fixtures.json](records/fixtures.json)。实现：[native_memory.py](native_memory.py)、[shell_broker.py](shell_broker.py)、[run_native.py](run_native.py)、[audit_native.py](audit_native.py)。

```powershell
python -X utf8 experiments/agentic_native_20261004/run_native.py check
# 下列为本次已授权的唯一 96 次运行入口；已提交任务只恢复审计，不重跑。
python -X utf8 experiments/agentic_native_20261004/run_native.py canary
python -X utf8 experiments/agentic_native_20261004/run_native.py remaining
```

首次建立环境需启动既有业务 WSL broker 和本目录的 `shell_broker.py`。新增的 WSL 工具为 ripgrep 14.1.0、strace 6.8；本机文件检索使用已有 Windows ripgrep。raw runtime 和 broker token 不提交；实验结束后保存限定范围的审计归档。
