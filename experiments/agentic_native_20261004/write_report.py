"""Generate the human-readable report from audited records only."""
from native_memory import ROOT, BASE
from run_native import read

NAMES = dict(historical_no_memory="历史无记忆", frozen_jaccard="冻结 Jaccard top-3", lexical="关键词事件检索",
             hybrid_context="混合检索＋上下文", graph_walk="图关系导航", native_files="原生文件工具", native_shell="原生终端")


def main():
    native = read(ROOT / "records/analysis.json")
    initial = read(BASE / "records/analysis.json")
    archive = read(ROOT / "records/raw-archive.json")
    scored, all_tasks = native["summaries"]["original_scored_46"], native["summaries"]["all_48"]
    total_tokens = initial["all_task_known_usage"]["totalTokens"] + native["all_task_known_usage"]["totalTokens"]
    lines = ["# 五种记忆访问方式：240 次独立复杂题执行报告", "", "日期：2026-10-04（香港时间）。", "",
        "本轮已经完成：三种检索工具各跑 48 道复杂题，随后按用户要求追加两种更接近原生 agent 的文件访问模式，各跑同样 48 题，共 **240 次，R=1**。所有求解器只能访问同一份 48 道简单题的 No Memory 历史；复杂题不互相学习、不写回记忆。", "",
        "原生两版实际让模型选择文件、搜索表达式和阅读范围；终端版还可自行组合命令。它们保留 GLM + Pi 求解底座，因此结果是这些访问方式的比较，不是 Codex、Claude Code、Mem0 等完整产品的性能排名。", "",
        "## 先看结果与成本", "", "每版执行 48 题，其中原有评分契约允许 46 题进入主评分。下表的 tokens、PYTHON 和记忆调用均只统计这 46 题，便于逐题比较；全部支出另列。", "",
        "| 方法 | 正确 / 46 | 总 tokens | PYTHON 次数 | 主动记忆调用 | 有主动记忆调用的题数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for method, name in NAMES.items():
        r = scored[method]
        lines.append(f"| {name} | {r['correct']}/46 | {r['known_usage']['totalTokens']:,} | {r['python_calls']} | {r['memory_calls']} | {r['tasks_with_memory_calls']} |")
    lines += ["", "Jaccard 在任务前固定注入历史，所以主动记忆调用为 0；这不代表没有看过记忆。原生文件版启动时已看到逐条索引，终端版只看到目录入口；两者即使主动调用为 0，也不等于无记忆。", "",
              "以下逐题差异均以已有冻结 Jaccard 为参照。先看质量变化，再看效率，不将二者混成一个任意加权分数。", ""]
    for method in ("lexical", "hybrid_context", "graph_walk", "native_files", "native_shell"):
        result = initial if method in initial["paired"] else native
        pair = result["paired"][method]["frozen_jaccard"]
        token_delta = pair["eligible_tokens_delta"]
        percent = token_delta / scored["frozen_jaccard"]["known_usage"]["totalTokens"] * 100
        lines.append(f"- **{NAMES[method]}**：{len(pair['success_gains'])} 题从失败变成功、{len(pair['success_losses'])} 题从成功变失败；tokens {token_delta:+,}（{percent:+.1f}%），PYTHON {pair['eligible_python_delta']:+d}。")
    lines += ["", "这些是同题的单次观察，不能证明稳定优劣、统计非劣或某个算法部件的因果效果。历史无记忆与 Jaccard 也不是本轮同时随机化重跑的对照；GLM 使用可变别名。", "",
        "## 两种原生模式，模型到底怎么查", "",
        "文件版不是等待检索器选出 top-k：它开始时拿到 52 行逐条索引，然后可以 Glob 列出路径、用 Grep 自定 regex/glob/上下文行，或按行范围 Read。终端版只拿到一个简短目录说明，真正进入只读 `/memory`，自主调用 `rg`、`cat`、`sed` 和管道。没有预设来源对应关系或目标答案。", "",
        "以同一首题 BigCodeBench/325 为例，实际日志显示：", "",
        "- 文件版自行限定 `episodes/s025.md` 搜索 `random|seed|letters`，随后转到 `s034.md` 搜索 `def |Counter|return`，再用两行上下文搜索 `ascii|choice|join`。",
        "- 终端版先用 `grep` 搜索 `combined_frequency`，再读 `MEMORY.md`，最后自行选择并打开 `episodes/s034.md` 与 `raw/s034.json`。",
        "- 两版这道题最终都没有通过评分。这一例证明发生了自主浏览，**不证明浏览已经带来正确答案或节约成本**。", "",
        "两个模式的初始披露量分别为 6,295 和 486 UTF-8 bytes，都计入每题 48KB 记忆预算。初始索引与工具界面同时有差异，因此不能把分数差单独归因于 Bash 或 Grep。", "",
        "具体设计和官方来源见 [原生访问模式说明](README.md)，前三版见 [设计说明](../agentic_search_20261004/README.md)。", "",
        "## 实际调用与观测", "",
        "| 模式（全部 48 题） | Search/Grep | Read | 图展开 | Glob | Shell | 记忆工具错误 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for method in ("lexical", "hybrid_context", "graph_walk", "native_files", "native_shell"):
        r = all_tasks[method]
        lines.append(f"| {NAMES[method]} | {r.get('grep_calls',0) or r['search_calls']} | {r['read_calls']} | {r['follow_calls']} | {r.get('glob_calls',0)} | {r.get('shell_calls',0)} | {r['memory_error_calls']} |")
    lines += ["", "记忆调用是实际行为结果，没有强制每题先搜索，也不因模型选择不搜索而补跑。错误计数是工具返回 error 的直接事实；终端非零退出另计，其中 `grep` 没命中也可能返回 1，不能全部称为任务失败。", "",
        "全量审计已覆盖：冻结库/索引和配置哈希、真实候选或文件路径、返回范围与截断、工具结果逐字进入哪些 provider 请求、后续 PYTHON/提交/评分、请求尝试和 usage。所有复杂题 memory-before/after 均等于同一简单题库，未生成可检索的复杂题 episode。原生语料的 98 个文件在运行后哈希不变。", "",
        "终端另保存 chroot 外的 strace、原始 stdout/stderr 和命令返回码。**打开文件与向模型展示内容不同**：工具返回的 stdout 是否进入请求可精确核验；脚本转换后究竟引用了哪些源字符不强行推断，终端的重复源字符数为 unknown。相关、命中、可见和模型真正使用也不是同一指标。", "",
        "## 完整支出、并发与来源成本", "", "| 新增方法 | 全部 48 题 tokens | 可评分 46 题 tokens |", "| --- | ---: | ---: |"]
    for method in ("lexical", "hybrid_context", "graph_walk", "native_files", "native_shell"):
        lines.append(f"| {NAMES[method]} | {all_tasks[method]['known_usage']['totalTokens']:,} | {scored[method]['known_usage']['totalTokens']:,} |")
    lines += ["", f"240 次新增执行共 **{total_tokens:,} tokens**，共 {initial['logical_calls'] + native['logical_calls']} 次逻辑生成、{initial['http_attempts'] + native['http_attempts']} 次 HTTP 尝试。未知 usage 为 {initial['unknown_usage_attempts'] + native['unknown_usage_attempts']}。前三版/原生两版实测 API 并发峰值分别为 {initial['observed_peak_http_attempts']}/{native['observed_peak_http_attempts']}，不以新并行墙钟与旧串行时间作因果比较。", "",
        "所有索引/文件转换都是本机确定性处理，没有额外 writer、embedding、reader 模型调用。48 道简单题历史生成成本 137,698 tokens 是既有资产成本，单列、不重复算作本轮支出。金额没有已核验单价/账单，仍为 unknown；token 比不是金额比。", "",
        "每题模型、轮数、工具次数、超时与重试按冻结配置执行；canary 均计入本方法 48 题。正常答错、不读取、无效动作或预算耗尽均没有重试到成功。", "",
        "## 评分边界和复核入口", "",
        "原评分 mask 保持不变，两个既有不可评分目标继续执行并计成本；316 的测试遮蔽疑点、历史无记忆 954 的基础设施失败分别保留诊断视图。以下是去除 316 后的描述性 45 题结果：", "",
        "| 方法 | 正确 / 45 | tokens |", "| --- | ---: | ---: |"]
    for method, name in NAMES.items():
        r = native["summaries"]["diagnostic_45_exclude_316"][method]
        lines.append(f"| {name} | {r['correct']}/45 | {r['known_usage']['totalTokens']:,} |")
    lines += ["", "进一步同时排除 316/954 的 44 题口径以及逐题 gains/losses、token/PYTHON 差值，保存在机器结果中；不覆盖原 46 题分数。", "",
        "- [五模式比较与原生逐题记录](records/analysis.json)",
        "- [前三版逐题记录](../agentic_search_20261004/records/analysis.json)",
        "- [归档清单与逐文件 SHA256](records/raw-archive.json)",
        "- [原始证据归档](artifacts/five-modes-raw.tar.gz)", "",
        f"原始证据共 {archive['files']:,} 个文件、压缩后 {archive['bytes']:,} bytes；SHA256 `{archive['sha256']}`。实际 GLM 凭据精确匹配扫描、逐成员哈希和安全恢复预检均通过；不含凭据文件、task workspaces、缓存或无关个人数据。", "",
        "```powershell", "python -X utf8 experiments/agentic_native_20261004/archive_all.py --verify",
        "# 新 checkout 先按仓库复现文档准备依赖；缺少本轮证据时可恢复归档：",
        "python -X utf8 experiments/agentic_native_20261004/archive_all.py --restore",
        "python -X utf8 experiments/agentic_native_20261004/analyze_native.py", "```", ""]
    (ROOT / "五种记忆访问方式实验报告.md").write_text("\n".join(lines), encoding="utf-8")
    print("Report generated from audited metrics.")


if __name__ == "__main__":
    main()
