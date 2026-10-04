# 配置映射与兼容性决定

2026-10-04。以下是配置合同和待本地落实的原生字段，不是已经验收的部署文件。`config/experiment.json` 是本项目声明式格式，不能原样传给 clbench 或某个 CLI。原生片段中的占位路径、endpoint 和模型必须在私有运行配置中解析，不能把密钥提交 Git。

## 1. 最新版的明确含义

启动适配时选择官方最新非预发布发行；没有正式发行则使用官方推荐安装渠道解析的 commit。若仅 main 上的修复满足本轮契约，可以采用较新的 main SHA并注明原因；不默认回退旧版本。解析一次后固定整批运行，不边跑边更新。

| 组件 | 本次查询可见的最新正式发行/快照 | 本地必须再登记 |
|---|---|---|
| Codex | `0.160.0` / `rust-v0.160.0`，2026-10-01 发布 | 实际二进制版本、来源 tag/commit、补丁、模型目录 |
| Claude Code | `2.1.289`，2026-10-03 UTC 发布 | 实际包/二进制哈希；关闭自动更新；不混用旧 2.1.119 解析假设 |
| Pi coding-agent | `1.0.2`，2026-10-04 UTC 发布 | coding-agent、pi-ai、agent-core 同一依赖锁；不是只升级 core |
| Hermes | `v2026.9.24` / 产品版本 `0.21.5` | 最新 release 或为必要功能选定的更新 main SHA；实际依赖与 schema |
| CL-Bench | main `5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26` | 实际 commit、两环境数据/顺序/预算/镜像摘要 |

以上是调研时点，不是“本地已安装版本”。本次检查的 Codex/Hermes/Pi 部分源码来自更晚的 main，和 release 不是同一 revision；滚动文档支持的键也必须核对实际版本。原始来源见 [S1、S6–S12、S16](SOURCES.md)。

## 2. GLM 路由

主模型优先沿用现有 `glm-5.3-flash` 与主求解 high 设置；用户本轮没有授权换成旗舰、Claude/GPT 或混合模型。所有推理角色实际使用同一 GLM 模型身份：solver、压缩、提取、整合、review、子 agent、标题等；无法关闭的辅助角色也登记。辅助 reasoning 可保留原生设置并报告，不假装所有角色算力完全相同。

优先选同一账户服务提供的三种协议入口：Codex 用 Responses，Claude Code 用 Anthropic Messages，Pi/Hermes 用所选官方兼容接口。不得把国内 BigModel 与国际 Z.AI 端点、API key 或订阅权限当作互通。某端点不支持 Flash 时，先记录，再考虑同一上游模型的透明协议桥接；不能只让这一组换模型。

用户提供的 [BigModel Codex 指南](https://docs.bigmodel.cn/cn/coding-plan/tool/codex) 是国内接入的首选依据。本轮该页正文抓取超时，未核验其国内 endpoint，不猜 URL。已读到 Z.AI 官方同主题指南，确认原生 Responses＋模型目录的路线，国际示例使用 `https://api.z.ai/api/v1`。[S9–S10](SOURCES.md) 这修正了“必须自行转 Chat Completions 才能接 Codex”的假设，但不证明当前账户的 Flash、全部辅助路径已兼容。

在本地据所用账户读取对应官方说明并做一次协议确认。只保存去凭据的实际 model/provider/endpoint 类型与返回版本；禁止将 API key 写入模型目录、日志或受测 agent 可读工作区。沿用既有安全取密钥入口，不再次从聊天或全磁盘搜 key，也不要混淆普通账户模型进程与提权业务 broker。

## 3. 256k 配置映射

共同值：上下文 262144，触发目标 245760，预留 16384；主求解输出目标上限 16384。配置记录上限、框架有效上限、请求实际计量和 provider 接受范围四者，不能只截图 UI。

### Pi coding-agent

自定义模型记录 `contextWindow: 262144`、`maxTokens: 16384`，真实 provider/api/model 与统一 GLM 对齐。会话设置映射：[S8](SOURCES.md)

```json
{
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384,
    "keepRecentTokens": 20000
  }
}
```

使用 coding-agent 原生 compaction，三组共用配置。压缩结果只属于当前 instance，不能通过 resume/branch summary给 pi_none 偷渡前题历史；真实 raw archive 留在审计侧或明确允许的 Jaccard 库。

### Codex

```toml
model = "glm-5.3-flash"
model_provider = "glm_experiment"
model_reasoning_effort = "high"
model_context_window = 262144
model_auto_compact_token_limit = 245760
model_catalog_json = "/ABSOLUTE/PRIVATE/RUN/models.json"

[model_providers.glm_experiment]
name = "GLM experiment"
base_url = "REPLACE_WITH_VERIFIED_RESPONSES_BASE_URL"
env_key = "EXPERIMENT_API_KEY"
wire_api = "responses"

[memories]
generate_memories = true
use_memories = true
extract_model = "glm-5.3-flash"
consolidation_model = "glm-5.3-flash"
disable_on_external_context = false
```

模型目录按提供方官方示例生成，但目录里的 context_window/max_context_window 不得保留 1M；统一本轮值。未在本片段列出的 max-output、feature flag 和模型能力字段，由锁定 schema映射并验证，不编造配置名。允许的 MCP 业务工具不能导致整个轨迹被 external-context 过滤排除。[S6、S9、S11](SOURCES.md)

### Claude Code

用真正的 GLM 自定义 ID，不伪装成 Claude 模型名，不追加 `[1m]`。[S7](SOURCES.md)

```text
ANTHROPIC_MODEL=glm-5.3-flash
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5.3-flash
ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5.3-flash
ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5.3-flash
CLAUDE_CODE_SUBAGENT_MODEL=glm-5.3-flash
CLAUDE_CODE_MAX_CONTEXT_TOKENS=262144
CLAUDE_CODE_AUTO_COMPACT_WINDOW=245760
DISABLE_AUTOUPDATER=1
```

ANTHROPIC_BASE_URL 和认证由安全启动器设置。快模型、fallback、标题等实际路由仍由请求账本确认，不能认为设四个别名就涵盖一切。禁止设置 `DISABLE_COMPACT`。最新文档支持上述自定义窗口，但不同 ID 的解析分支不同，须确认是 GLM 自定义分支。[S7、S10]

显式启用 `autoMemoryEnabled: true`，使用每条流独立 CLAUDE_CONFIG_DIR，并稳定项目路径/autoMemoryDirectory。官方文档说明某些后台/嵌套会话默认禁用 auto memory；受测 CLI 应由外层 runner独立启动，不能因本地操作者也是 Codex/Claude 就错误继承嵌套禁用状态。不允许伪造进程身份绕权限；若官方接口不能启用则列适配阻断。[S12]

### Hermes

```yaml
model:
  context_length: 262144
compression:
  enabled: true
  threshold: 0.9375
memory:
  memory_enabled: true
  user_profile_enabled: true
  write_approval: false
auxiliary:
  compression:
    provider: main
    model: glm-5.3-flash
  background_review:
    enabled: true
    provider: auto
    model: glm-5.3-flash
    defer: never
    max_input_tokens: 2097152
```

这是待合并到真实 provider/default model 配置的片段，不能覆盖已有 model 对象其他字段。压缩 threshold 按原生实际计算校验；后台累计输入保护设 8×256k，避免原生默认累计预算小于一条长上下文导致 review尚未发请求就被阻断。它不是单次上下文扩大，所有开销计入；仍受600秒边界保护。2026-10-04 用户已取消本项目额外设置的32次维护请求上限。[S13–S14]

## 4. 任务边界记忆：具体决定

### Codex：只改 idle 不够

当前配置说明的 `min_rollout_idle_hours` 默认6，最小被钳制到1；直接写0不能声称即时生成。Phase 1 源码还筛选会话来源、锁和候选，并区分 with-output/no-output/failure。[S6、S11]

本轮采用 **memory-ready 调度适配**：真实 benchmark instance结束后，封存合法轨迹；调用原生生成链路处理刚结束的真实 session，等待 Phase 1 与必要的 Phase 2 完成。若最新版本没有公开即时入口，允许范围受限的补丁：只对本 run已完成并注册的 session跳过 idle等待、开放真实 exec来源并暴露完成句柄。保留原生提取、筛选与整合内容机制。

不得改历史时间戳伪装等待，不得将所有用户会话无条件设 eligible，不得让隐藏子任务/评分日志进源库。仅新建下一任务并等后台不够：下一任务可能已经取到了旧记忆快照。完成屏障必须早于其快照和题目输入。空维护会话若被用于驱动入口，要从后续经验源中排除并单独记账。

### Hermes：不设一个不存在的通用 `flush=1`

`flush=1`不是已核实的 Hermes 原生通用开关。原生频率入口是 `memory.nudge_interval` 等；历史 `pi-hermes-memory` 插件使用 `flushMinTurns`，不是本轮 Hermes 组。[S13、E2]

确定的目标是 **每个 benchmark instance结束时至少获得一次针对最终水位的原生记忆 review机会**，而不是每次工具响应都强制写一次：

- runner若把一个 instance映射成一个原生 user turn，可设置 `memory.nudge_interval: 1`，保留前台写入和原生 review内容；同时确认最终反馈已进入被处理水位。
- 若 CL-Bench适配把每次QUERY反馈都映射为新 user turn，不能机械设1，否则变成每步 review。使用终局 boundary hook调用原生 review并去重，记录调度补丁；不得把业务工具调用数当用户轮数。
- 正常任务内技能维护按原生配置保留，不另外把 `skills.creation_nudge_interval` 改成每个工具循环1次。周期 curator不人为快进时钟；如实际触发也计费并纳入屏障。
- 等待已启动的 review/flush/压缩/技能写入完成，再正常 shutdown；不能先 dispose取消后台后称任务完成。没有公开 drain就补最薄的 job registry/await句柄，不用固定 sleep猜测。
- 保留原生审批语义。后台 replace/remove仍可能 staged，`write_approval:false`不保证所有修改自动 committed。记录 staged，与失败和NOOP分开；不自动批准、不无限等待人工批准，也不把 staged内容注入下一题。[S13]

**强制维护机会≠强制非空笔记。** 不改 writer提示为“必须保存”，也不在空结果上重试到写出内容。原始 session应按框架规则持久化；是否形成笔记/skill由原生内容策略决定。

### Claude Code：先确认实际机制，不自行造一个 writer

官方描述主要是会话中主动读写 auto memory，也明确并非每次会话都会保存。不把“auto”自动解释成有后台摘要器。[S12]

启用原生能力、完成正常会话收尾，收集主/子 agent和发现的维护作业。若锁定版本存在后台写入，加入同一屏障；不存在则同步写入和会话持久化完成即可。没有公开机制时不加一个自制总结子 agent冒充原生 memory。未完成不能以“闭源看不到”为理由放行。

## 5. Pi 两种记忆的忠实语义

**Notepad**：复用官方提示和 optional `notepad_update` 的整体替换语义；null不变、空字符串清空。将它作为业务动作封装中的可选字段，在送交 benchmark之前剥离并写入私有notepad。每次模型生成同时看到当前notepad；更改只在下一请求生效。当前任务历史在边界清除，notepad保留；不新增专用反思模型、不开放完整前题轨迹的旁路文件搜索。原生最终feedback的转发/清除语义逐项核对；不得借终局维护把evaluator私有内容交给notepad。没有notepad_update的正常回复不是写入失败。[S3]

**Jaccard**：词集合为小写 `\w+`；分数=交集/并集，空并集为0；并列时较新episode优先；取top-3后按时间排列。每个新instance按其公开任务提示检索一次，不加入隐含reranker或中途agentic search。库只含该配置自己此前已完成任务的合法task/assistant text/业务tool actions/results/许可反馈，不含隐藏reasoning、评分标签、未来任务或其他方法的历史。

记录被选来源、排序与压缩映射。源序列化不递归嵌套旧注入历史、系统提示或审计元数据，避免指数膨胀；这个投影与旧实现差异必须登记。与旧48KB版本命名区分，不用旧成绩替代新对照。原始episode全量保留且不被当前上下文压缩回写破坏。
