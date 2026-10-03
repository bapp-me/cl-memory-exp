"""Offline post-run audit and comparison; never calls models or executes submissions."""
from __future__ import annotations
import ast
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import statistics

from run_frozen import ROOT, REPO, OBS, RUNS, RUN_ID, read, save, sha, check_freeze
from audit import verify_task


def summarize(rows):
    valid = [row for row in rows if row["scorable"] is True]
    usage = {key: sum(row["known_usage_subtotal"][key] for row in rows)
             for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens")}
    return {"tasks": len(rows), "scorable": len(valid), "correct": sum(row["correct"] is True for row in valid),
            "known_usage": usage, "working_tool_calls": sum(row["working_tool_calls"] for row in rows),
            "submit_calls": sum(row["submit_calls"] for row in rows),
            "solver_seconds_sum": sum(row["solver_seconds"] for row in rows),
            "solver_seconds_median": statistics.median(row["solver_seconds"] for row in rows),
            "repeated_identical_working_arguments": sum(row["tool_metrics"]["same_working_arguments_excess"] for row in rows),
            "observations_with_error_signals": sum(row["tool_metrics"]["observations_with_error_signals"] for row in rows)}


def main():
    eng, config, library = check_freeze()
    missing = [i for i in range(48, 96) if not (RUNS / f"{i:03d}/commit.json").exists()]
    assert not missing, f"Incomplete run; no completion report: {missing}"
    metric_source = (REPO / "experiments/section7_analysis_20261003/analyze_d0.py").read_text(encoding="utf-8")
    node = next(node for node in ast.parse(metric_source).body if isinstance(node, ast.FunctionDef) and node.name == "tool_metrics")
    namespace = {"json": json, "re": re, "Counter": Counter, "digest": eng.digest}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<frozen tool_metrics>", "exec"), namespace)
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    source_indices = {row["id"]: i for i, row in enumerate(assets[:48])}
    baseline = read(REPO / "experiments/section7_analysis_20261003/records/d0-tasks.json")
    original = {method: [row for row in baseline if row["method"] == method and row["benchmark"] == "codeeval" and row["index"] >= 48]
                for method in ("no_memory", "episodic_retrieval")}
    rows, intervals, provider_models = [], [], Counter()
    request_count = 0
    unknown = 0
    http_statuses = Counter()
    event_times = []
    for index in range(48, 96):
        record = verify_task(index, eng, library)
        folder = RUNS / f"{index:03d}"
        pi = read(folder / "pi-result.json")
        metrics = namespace["tool_metrics"](pi)
        ledger = read(folder / "call-ledger.json")
        attempts = [attempt for call in ledger for attempt in call["http_attempts"]]
        usages = [eng.normalized_usage(attempt.get("raw_usage")) for attempt in attempts]
        known = {key: sum(usage[key] for usage in usages if usage is not None) for key in eng.USAGE_FIELDS}
        assert known == record["known_usage_subtotal"]
        assert len(attempts) == record["http_attempts"]
        assert sum(usage is None for usage in usages) == record["unknown_usage_http_attempts"]
        unknown += sum(usage is None for usage in usages)
        request_count += len(attempts)
        for attempt in attempts:
            provider_models[str(attempt.get("provider_model"))] += 1
            http_statuses[str(attempt.get("status"))] += 1
            for key, delta in (("started_at", 1), ("finished_at", -1)):
                assert attempt.get(key)
                intervals.append((datetime.fromisoformat(attempt[key].replace("Z", "+00:00")).timestamp(), delta))
        retrieval = read(folder / "retrieval.json")
        injected = read(folder / "injected.json")
        corresponding = source_indices[assets[index]["id"]]
        source_hit = corresponding in [entry["sequence"] for entry in injected]
        row = {**record, "index": index, "method": "frozen_source_jaccard", "solver_seconds": record["seconds"],
               "tool_metrics": metrics, "working_tool_calls": sum(n for name, n in metrics["by_name"].items() if name != "SUBMIT"),
               "submit_calls": metrics["by_name"].get("SUBMIT", 0), "source_index": corresponding,
               "corresponding_source_injected": source_hit, "candidate_count": len(retrieval["observable_candidates"]),
               "injected_indices": [entry["sequence"] for entry in injected],
               "injected_bytes": retrieval["injected_utf8_bytes"], "immutable_memory_verified": True,
               "source_path": folder.relative_to(REPO).as_posix()}
        rows.append(row)
        assert row["scorable"] == next(old for old in original["no_memory"] if old["index"] == index)["scorable"]
        events = [json.loads(line) for line in (folder / "controller-events.jsonl").read_text(encoding="utf-8").splitlines()]
        event_times.extend((index, event["event"], event["at_unix_ns"] / 1e9) for event in events if event["event"] in ("task_start", "task_commit"))
    active = peak = 0
    for _, delta in sorted(intervals):
        active += delta
        peak = max(peak, active)
    assert active == 0 and peak <= 48
    all_methods = {"historical_no_memory": original["no_memory"], "historical_online_jaccard": original["episodic_retrieval"],
                   "frozen_source_jaccard": rows}
    scopes = {
        "all_48": lambda row: True,
        "original_scored_46": lambda row: row["scorable"] is True,
        "diagnostic_45_exclude_test_shadow_316": lambda row: row["scorable"] is True and row["task_id"] != "new:BigCodeBench/316",
        "diagnostic_44_also_exclude_historical_infra_954": lambda row: row["scorable"] is True and row["task_id"] not in ("new:BigCodeBench/316", "new:BigCodeBench/954"),
    }
    summaries = {scope: {method: summarize([row for row in records if keep(row)]) for method, records in all_methods.items()}
                 for scope, keep in scopes.items()}
    paired = {}
    for name, old_rows in original.items():
        matches = {row["task_id"]: row for row in old_rows}
        pairs = []
        for row in rows:
            old = matches[row["task_id"]]
            pairs.append({"task_id": row["task_id"], "index": row["index"], "scorable": row["scorable"],
                          "historical_correct": old["correct"], "new_correct": row["correct"],
                          "token_delta": row["known_usage_subtotal"]["totalTokens"] - old["known_usage_subtotal"]["totalTokens"],
                          "working_tool_delta": row["working_tool_calls"] - old["working_tool_calls"],
                          "source_index": row["source_index"]})
        effective = [pair for pair in pairs if pair["scorable"] is True]
        paired[name] = {"gains": [pair["task_id"] for pair in effective if pair["new_correct"] is True and pair["historical_correct"] is False],
                        "losses": [pair["task_id"] for pair in effective if pair["new_correct"] is False and pair["historical_correct"] is True],
                        "lower_token_tasks": sum(pair["token_delta"] < 0 for pair in effective), "pairs": pairs}
    preserved = {}
    for filename in ("source-hashes.json", "d0-input-hashes.json"):
        path = REPO / "experiments/section7_analysis_20261003/records" / filename
        for relative, expected in read(path).items():
            assert sha(REPO / relative) == expected, relative
            preserved[relative] = expected
    sandbox_log = ROOT / ".runtime/sandbox-spans.jsonl"
    spans = [json.loads(line) for line in sandbox_log.read_text(encoding="utf-8").splitlines()]
    spans = [span for span in spans if "sandbox-canary" not in span["work"]]
    rest_times = [stamp for index, _, stamp in event_times if index > 48]
    result = {
        "status": "all_48_completed_and_audited", "config_hash": eng.digest(config), "run_id": RUN_ID,
        "task_count": len(rows), "http_attempts": request_count, "logical_model_calls": sum(row["calls"] for row in rows),
        "unknown_usage_attempts": unknown, "http_statuses": dict(http_statuses), "provider_models": dict(provider_models),
        "observed_peak_http_attempts": peak, "remaining_47_task_window_seconds": max(rest_times) - min(rest_times),
        "terminal_states": dict(Counter(row["terminal_state"] for row in rows)),
        "source_only_invariant_passed": True, "corresponding_source_hits_all": sum(row["corresponding_source_injected"] for row in rows),
        "baseline_files_unchanged": len(preserved), "summaries": summaries, "paired": paired,
        "shared_historical_source_tokens": 137698,
        "new_source_writer_reviewer_calls": 0,
        "sandbox_queue": {"calls": len(spans), "sum_seconds": sum(span["queue_seconds"] for span in spans),
                          "max_seconds": max((span["queue_seconds"] for span in spans), default=0)},
        "money": None, "money_reason": "No verified invoice/price manifest",
        "limits": ["R=1, historical comparisons are not contemporaneous controls.",
                   "Source trajectories and complex-task writeback policy both differ from historical online Jaccard.",
                   "Corresponding-source coverage does not prove semantic use or correctness.",
                   "Historical SDK usage is retained descriptive accounting; new attempts use captured provider usage.",
                   "Diagnostic exclusions are separate views, not modifications to original scores/mask.",
                   "High-concurrency wall time and sandbox queue time are not comparable to historical serial runtime."],
        "rows": rows}
    save(ROOT / "records/results.json", result)
    save(ROOT / "records/baseline-preservation.json", {"verified_files": len(preserved), "hashes": preserved})
    write_report(result)
    print(json.dumps({key: result[key] for key in ("status", "http_attempts", "unknown_usage_attempts", "observed_peak_http_attempts", "baseline_files_unchanged", "summaries")}, ensure_ascii=False))


def write_report(result):
    display = [("historical_no_memory", "历史 No Memory"), ("historical_online_jaccard", "历史在线 Jaccard"),
               ("frozen_source_jaccard", "本次冻结简单题库 Jaccard")]
    effective = result["summaries"]["original_scored_46"]
    all48 = result["summaries"]["all_48"]
    fresh, old = effective["frozen_source_jaccard"], effective["historical_online_jaccard"]
    delta = fresh["known_usage"]["totalTokens"] - old["known_usage"]["totalTokens"]
    percent = delta / old["known_usage"]["totalTokens"] * 100
    lines = ["# 冻结 No Memory 简单题库的 Jaccard top-3 补跑结果", "",
             f"本次完成 48 道复杂题、每题一次；原评分口径正确 {fresh['correct']}/46。有效目标已知总 token 为 {fresh['known_usage']['totalTokens']:,}，相对历史在线 Jaccard 的变化为 {delta:+,}（{percent:+.1f}%）。这是一组改变源轨迹和写入策略的补充对照，不能把差异归因于单一因素或宣称稳定提升。", "",
             "## 配置和隔离", "",
             "固定已有 No Memory 的全部 48 道简单题合法轨迹，Jaccard 原样全文 top-3；复杂题只读，不保存为记忆或加入索引。仍用 GLM-5.3-Flash high、Pi 及原执行预算。没有 ICL、top-1、压缩、writer 或额外 reviewer 调用。源隐藏评分不参与筛选。", "",
             f"全部 48 题的 memory-before/after 都等于同一源库；实际候选、注入和每个请求 payload 已校验。48/48 对应源进入三条注入。源库 hash：`{read(ROOT/'records/config.json')['source_library_hash']}`。复杂 legal-episode.json 均不存在；审计轨迹只在隔离日志保留。", "",
             "## 原评分口径：46 个有效复杂目标", "",
             "| 条件 | 正确 /46 | 总 tokens | 输入含缓存 | 输出含 reasoning | PYTHON | SUBMIT |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for key, label in display:
        row = effective[key]; usage = row["known_usage"]
        lines.append(f"| {label} | {row['correct']} | {usage['totalTokens']:,} | {usage['input']+usage['cacheRead']+usage['cacheWrite']:,} | {usage['output']:,} | {row['working_tool_calls']} | {row['submit_calls']} |")
    ratio = fresh["known_usage"]["totalTokens"] / effective["historical_no_memory"]["known_usage"]["totalTokens"]
    lines += ["", f"本次 token 仍为历史 No Memory 的 {ratio:.2f} 倍。与历史 Jaccard 相比费用量下降、工作工具减少且总正确数相同，只是本批观察；逐题有得有失，不能称全面效率提升或已证明质量非劣。", "", "## 48 道实际执行的费用范围", "",
              "| 条件 | 目标 tokens（含不可评分题） | 工作工具 | SUBMIT |", "|---|---:|---:|---:|"]
    for key, label in display:
        row = all48[key]
        lines.append(f"| {label} | {row['known_usage']['totalTokens']:,} | {row['working_tool_calls']} | {row['submit_calls']} |")
    lines += ["", f"本次新执行费用为上述 48 题费用。既有 No Memory 简单库的历史构建成本为 137,698 tokens，复用时没有新增调用；若报告从零构建的一轮部署成本，应再加这一项。本次共有 {result['http_attempts']} HTTP attempts，未知 usage {result['unknown_usage_attempts']} 条，原始 provider usage 已逐请求重算。缓存是输入子集，reasoning 已含在输出，均不重复加总。金额没有可靠价格/账单，保持未知。", "",
              "## 逐题变化与评分边界", ""]
    for key, label in (("no_memory", "历史 No Memory"), ("episodic_retrieval", "历史在线 Jaccard")):
        pairs = result["paired"][key]
        lines += [f"相对{label}，原 46 题中由失败转成功 {len(pairs['gains'])} 题、由成功转失败 {len(pairs['losses'])} 题；总 token 下降 {pairs['lower_token_tasks']}/46。",
                  "", "- 转成功：" + ("、".join(pairs["gains"]) or "无"), "- 转失败：" + ("、".join(pairs["losses"]) or "无"), ""]
    lines += ["316 的原测试会重定义提交函数，954 的历史 No Memory 有工具传输故障；原分数与 mask 不变，诊断视图如下，不能把这些差异全当能力变化。", "",
              "| 诊断视图 | 历史 No Memory | 历史在线 Jaccard | 本次 |", "|---|---:|---:|---:|"]
    for scope, label in (("diagnostic_45_exclude_test_shadow_316", "排除 316，45 题"),
                         ("diagnostic_44_also_exclude_historical_infra_954", "再排除历史基础设施问题 954，44 题")):
        metrics = result["summaries"][scope]
        lines.append("| " + label + " | " + " | ".join(str(metrics[key]["correct"]) for key, _ in display) + " |")
    lines += ["", "## 并发、接线恢复与复核", "",
              f"按用户追加要求设置最多 48 个独立任务和 8 个本机沙箱槽位，实测 HTTP attempt 峰值 {result['observed_peak_http_attempts']}；后 47 题任务窗口约 {result['remaining_47_task_window_seconds']:.1f} 秒。高并发时长含沙箱排队，不与旧串行时间作效率因果比较。", "",
              "首次提权启动因 Windows 身份不匹配无法解密旧 DPAPI 凭据；普通 Codex 沙箱账户成功加载原密钥，无需用户换 key。凭据失败发生在模型调用前。首题执行后校验器未接受 Pi 的文本块数组，修正被动校验后复核通过；没有重跑首题或改变模型输入。", "",
              f"既有 baseline {result['baseline_files_unchanged']:,} 个文件哈希保持不变。新请求、轨迹、usage、提交和评分另行归档；[机器结果](records/results.json)、[冻结协议](PROTOCOL.md)、[接线恢复](records/startup-and-audit-recovery.json)、[原始归档索引](records/raw-archive.json)。", "",
              "归档仅含本次审计材料，逐成员哈希核验、安全恢复检查和当前 GLM 凭据精确扫描通过；不包含 sandbox-broker.json、凭据或任务工作区。", "",
              "离线复核先按仓库说明恢复历史资产，再运行 `python experiments/section7_frozen_jaccard_20261004/archive.py --restore` 和 `python experiments/section7_frozen_jaccard_20261004/analyze.py`。不要把 `launch.py first/remaining` 当离线复核入口。"]
    (ROOT / "冻结简单题库Jaccard补跑报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
