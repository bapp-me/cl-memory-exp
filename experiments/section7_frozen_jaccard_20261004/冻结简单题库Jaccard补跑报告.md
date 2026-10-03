# 冻结 No Memory 简单题库的 Jaccard top-3 补跑结果

本次完成 48 道复杂题、每题一次；原评分口径正确 27/46。有效目标已知总 token 为 468,934，相对历史在线 Jaccard 的变化为 -105,175（-18.3%）。这是一组改变源轨迹和写入策略的补充对照，不能把差异归因于单一因素或宣称稳定提升。

## 配置和隔离

固定已有 No Memory 的全部 48 道简单题合法轨迹，Jaccard 原样全文 top-3；复杂题只读，不保存为记忆或加入索引。仍用 GLM-5.3-Flash high、Pi 及原执行预算。没有 ICL、top-1、压缩、writer 或额外 reviewer 调用。源隐藏评分不参与筛选。

全部 48 题的 memory-before/after 都等于同一源库；实际候选、注入和每个请求 payload 已校验。48/48 对应源进入三条注入。源库 hash：`dac0179536ec6d1316507b86d7bdbd542345209c5c52492e4b60ef61f0882914`。复杂 legal-episode.json 均不存在；审计轨迹只在隔离日志保留。

## 原评分口径：46 个有效复杂目标

| 条件 | 正确 /46 | 总 tokens | 输入含缓存 | 输出含 reasoning | PYTHON | SUBMIT |
|---|---:|---:|---:|---:|---:|---:|
| 历史 No Memory | 18 | 162,418 | 101,830 | 60,588 | 52 | 51 |
| 历史在线 Jaccard | 27 | 574,109 | 520,604 | 53,505 | 52 | 46 |
| 本次冻结简单题库 Jaccard | 27 | 468,934 | 417,361 | 51,573 | 48 | 46 |

本次 token 仍为历史 No Memory 的 2.89 倍。与历史 Jaccard 相比费用量下降、工作工具减少且总正确数相同，只是本批观察；逐题有得有失，不能称全面效率提升或已证明质量非劣。

## 48 道实际执行的费用范围

| 条件 | 目标 tokens（含不可评分题） | 工作工具 | SUBMIT |
|---|---:|---:|---:|
| 历史 No Memory | 172,965 | 55 | 53 |
| 历史在线 Jaccard | 601,793 | 54 | 48 |
| 本次冻结简单题库 Jaccard | 504,199 | 51 | 48 |

本次新执行费用为上述 48 题费用。既有 No Memory 简单库的历史构建成本为 137,698 tokens，复用时没有新增调用；若报告从零构建的一轮部署成本，应再加这一项。本次共有 99 HTTP attempts，未知 usage 0 条，原始 provider usage 已逐请求重算。缓存是输入子集，reasoning 已含在输出，均不重复加总。金额没有可靠价格/账单，保持未知。

## 逐题变化与评分边界

相对历史 No Memory，原 46 题中由失败转成功 9 题、由成功转失败 0 题；总 token 下降 2/46。

- 转成功：new:BigCodeBench/559、new:BigCodeBench/394、new:BigCodeBench/954、new:BigCodeBench/311、new:BigCodeBench/699、new:BigCodeBench/739、new:BigCodeBench/767、new:BigCodeBench/928、new:BigCodeBench/198
- 转失败：无

相对历史在线 Jaccard，原 46 题中由失败转成功 2 题、由成功转失败 2 题；总 token 下降 41/46。

- 转成功：new:BigCodeBench/559、new:BigCodeBench/394
- 转失败：new:BigCodeBench/43、new:BigCodeBench/983

316 的原测试会重定义提交函数，954 的历史 No Memory 有工具传输故障；原分数与 mask 不变，诊断视图如下，不能把这些差异全当能力变化。

| 诊断视图 | 历史 No Memory | 历史在线 Jaccard | 本次 |
|---|---:|---:|---:|
| 排除 316，45 题 | 17 | 26 | 26 |
| 再排除历史基础设施问题 954，44 题 | 17 | 25 | 25 |

## 并发、接线恢复与复核

按用户追加要求设置最多 48 个独立任务和 8 个本机沙箱槽位，实测 HTTP attempt 峰值 47；后 47 题任务窗口约 92.9 秒。高并发时长含沙箱排队，不与旧串行时间作效率因果比较。

首次提权启动因 Windows 身份不匹配无法解密旧 DPAPI 凭据；普通 Codex 沙箱账户成功加载原密钥，无需用户换 key。凭据失败发生在模型调用前。首题执行后校验器未接受 Pi 的文本块数组，修正被动校验后复核通过；没有重跑首题或改变模型输入。

既有 baseline 7,924 个文件哈希保持不变。新请求、轨迹、usage、提交和评分另行归档；[机器结果](records/results.json)、[冻结协议](PROTOCOL.md)、[接线恢复](records/startup-and-audit-recovery.json)、[原始归档索引](records/raw-archive.json)。

归档仅含本次审计材料，逐成员哈希核验、安全恢复检查和当前 GLM 凭据精确扫描通过；不包含 sandbox-broker.json、凭据或任务工作区。

离线复核先按仓库说明恢复历史资产，再运行 `python experiments/section7_frozen_jaccard_20261004/archive.py --restore` 和 `python experiments/section7_frozen_jaccard_20261004/analyze.py`。不要把 `launch.py first/remaining` 当离线复核入口。
