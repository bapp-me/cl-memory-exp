"""Post-run only. Audit all 144 runs and compare paired quality/efficiency without model calls."""
from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime
import json
import statistics
import re

from audit import audit_task, rows
from memory import METHODS, Session, digest
from run import ROOT, REPO, OBS, PREFIX, check_freeze, engine, read, run_folder, save, sha


def metrics_function():
    path = REPO / "experiments/section7_analysis_20261003/analyze_d0.py"
    node = next(n for n in ast.parse(path.read_text(encoding="utf-8")).body
                if isinstance(n, ast.FunctionDef) and n.name == "tool_metrics")
    namespace = dict(json=json, re=re, Counter=Counter, digest=digest)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["tool_metrics"]


def summary(records):
    usage = {k: sum(r["known_usage_subtotal"][k] for r in records)
             for k in ("input", "output", "cacheRead", "cacheWrite", "totalTokens")}
    times = [r.get("seconds", r.get("solver_seconds")) for r in records]
    times = [x for x in times if x is not None]
    return dict(tasks=len(records), scorable=sum(r["scorable"] is True for r in records),
        correct=sum(r["correct"] is True for r in records), known_usage=usage,
        unknown_usage_attempts=None if any(r.get("unknown_usage_http_attempts") is None for r in records)
            else sum(r["unknown_usage_http_attempts"] for r in records),
        python_calls=sum(r.get("python_calls", r.get("tools_by_name", {}).get("PYTHON", r.get("working_tool_calls", 0))) for r in records),
        memory_calls=sum(r.get("memory_calls", 0) for r in records),
        search_calls=sum(r.get("search_calls", 0) for r in records),
        read_calls=sum(r.get("read_calls", 0) for r in records),
        follow_calls=sum(r.get("follow_calls", 0) for r in records),
        tasks_with_memory_calls=sum(r.get("memory_calls", 0) > 0 for r in records),
        tasks_with_visible_memory=sum(r.get("maximum_visible_memory_results", 0) > 0 or r.get("injected_bytes", 0) > 0 for r in records),
        corresponding_source_exposed=sum(r.get("corresponding_source_exposed", r.get("corresponding_source_injected", False)) for r in records),
        memory_response_bytes=sum(r.get("memory_response_bytes", 0) for r in records),
        repeated_source_chars=sum(r.get("memory_repeated_source_chars", 0) for r in records),
        memory_error_calls=sum(r.get("memory_error_calls", 0) for r in records),
        identical_working_arguments=sum(r.get("tool_metrics", {}).get("same_working_arguments_excess", 0) for r in records),
        observations_with_error_signals=sum(r.get("tool_metrics", {}).get("observations_with_error_signals", 0) for r in records),
        solver_seconds_sum=sum(times), solver_seconds_median=statistics.median(times) if times else None,
        money=None)


def pairs(new, old):
    old_by_id = {r["task_id"]: r for r in old}
    result = []
    for row in new:
        reference = old_by_id[row["task_id"]]
        assert row["scorable"] == reference["scorable"]
        old_python = reference.get("python_calls", reference.get("tools_by_name", {}).get("PYTHON", reference.get("working_tool_calls", 0)))
        result.append(dict(task_id=row["task_id"], index=row["index"], scorable=row["scorable"],
            old_correct=reference["correct"], new_correct=row["correct"],
            tokens_delta=row["known_usage_subtotal"]["totalTokens"] - reference["known_usage_subtotal"]["totalTokens"],
            python_delta=row["python_calls"] - old_python,
            memory_calls=row["memory_calls"], source_exposed=row["corresponding_source_exposed"]))
    eligible = [p for p in result if p["scorable"]]
    same_quality = [p for p in eligible if p["new_correct"] == p["old_correct"]]
    return dict(rows=result, eligible_tasks=len(eligible),
        success_gains=[p["task_id"] for p in eligible if p["new_correct"] and not p["old_correct"]],
        success_losses=[p["task_id"] for p in eligible if p["old_correct"] and not p["new_correct"]],
        eligible_tokens_delta=sum(p["tokens_delta"] for p in eligible),
        eligible_python_delta=sum(p["python_delta"] for p in eligible),
        lower_token_tasks=sum(p["tokens_delta"] < 0 for p in eligible),
        same_observed_quality_tasks=len(same_quality),
        same_observed_quality_tokens_delta=sum(p["tokens_delta"] for p in same_quality),
        warning="R=1 paired descriptive deltas; same observed correctness is not proven quality equivalence")


def main():
    config, archive = check_freeze()
    eng, _ = engine()
    metric = metrics_function()
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    source_map = {r["id"]: i for i, r in enumerate(assets[:48])}
    tasks, interval_events, provider_models, statuses = [], [], Counter(), Counter()
    missing = [(m, i) for m in METHODS for i in range(48, 96) if not (run_folder(m, i) / "commit.json").exists()]
    if missing:
        raise RuntimeError(f"Incomplete batch: {missing}")
    for method in METHODS:
        for index in range(48, 96):
            folder = run_folder(method, index)
            row = audit_task(folder, archive, config)
            initial = read(folder / "input-public.json")
            assert initial["prompt"] == assets[index]["problem"]
            assert initial["tools"] == [*eng.CODE_TOOLS, *Session(archive, method).tools]
            ledger = read(folder / "call-ledger.json")
            attempts = [a for call in ledger for a in call["http_attempts"]]
            usages = [eng.normalized_usage(a["raw_usage"]) for a in attempts]
            known = {k: sum(u[k] for u in usages if u is not None) for k in eng.USAGE_FIELDS}
            assert known == row["known_usage_subtotal"]
            assert row["unknown_usage_http_attempts"] == sum(u is None for u in usages)
            for attempt in attempts:
                statuses[str(attempt["status"])] += 1
                provider_models[str(attempt["provider_model"])] += 1
                for key, delta in (("started_at", 1), ("finished_at", -1)):
                    interval_events.append((datetime.fromisoformat(attempt[key].replace("Z", "+00:00")).timestamp(), delta))
            exposed = set()
            for request in rows(folder / "memory-exposure.jsonl"):
                for mapping in request["mappings"]:
                    if mapping["matches"]:
                        exposed.update(r["source_id"] for r in mapping["ranges"])
            access = [r for r in rows(folder / "memory-access.jsonl") if r["event"] == "memory_access"]
            controller = rows(folder / "controller-events.jsonl")
            start = next(r["at_unix_ns"] for r in controller if r["event"] == "task_start")
            end = next(r["at_unix_ns"] for r in controller if r["event"] == "task_commit")
            row.update(index=index, source_path=folder.relative_to(REPO).as_posix(),
                corresponding_source_id=f"s{source_map[assets[index]['id']]:03d}",
                corresponding_source_exposed=f"s{source_map[assets[index]['id']]:03d}" in exposed,
                exposed_source_ids=sorted(exposed), tool_metrics=metric(read(folder / "pi-result.json")),
                search_queries=[r["args"]["query"] for r in access if r["name"] == "MEMORY_SEARCH"],
                task_start_unix_ns=start, task_commit_unix_ns=end)
            tasks.append(row)
    active = peak = 0
    for _, delta in sorted(interval_events):
        active += delta
        peak = max(peak, active)
    assert active == 0 and peak <= config["max_parallel_tasks"]
    legacy = read(REPO / "experiments/section7_analysis_20261003/records/d0-tasks.json")
    no_memory = [r for r in legacy if r["method"] == "no_memory" and r["benchmark"] == "codeeval" and r["index"] >= 48]
    jaccard = read(REPO / "experiments/section7_frozen_jaccard_20261004/records/results.json")["rows"]
    groups = {"historical_no_memory": no_memory, "frozen_jaccard": jaccard}
    groups.update({method: [r for r in tasks if r["method"] == method] for method in METHODS})
    scopes = dict(all_48=lambda r: True, original_scored_46=lambda r: r["scorable"] is True,
                  diagnostic_45_exclude_316=lambda r: r["scorable"] is True and r["task_id"] != "new:BigCodeBench/316",
                  diagnostic_44_exclude_316_954=lambda r: r["scorable"] is True and r["task_id"] not in ("new:BigCodeBench/316", "new:BigCodeBench/954"))
    summaries = {scope: {name: summary([r for r in group if keep(r)]) for name, group in groups.items()} for scope, keep in scopes.items()}
    paired = {method: {reference: pairs(groups[method], groups[reference]) for reference in groups if reference != method} for method in METHODS}
    final = dict(status="all_144_completed_and_audited", config_hash=digest(config),
        tasks=144, observed_peak_http_attempts=peak, provider_models=dict(provider_models), http_statuses=dict(statuses),
        logical_calls=sum(r["calls"] for r in tasks), http_attempts=sum(r["http_attempts"] for r in tasks),
        unknown_usage_attempts=sum(r["unknown_usage_http_attempts"] for r in tasks),
        terminal_states=dict(Counter(r["terminal_state"] for r in tasks)),
        all_task_known_usage={k: sum(r["known_usage_subtotal"][k] for r in tasks) for k in eng.USAGE_FIELDS},
        summaries=summaries, paired=paired, rows=tasks, source_only_invariant_passed=True,
        shared_historical_source_tokens=config["historical_source_tokens"], new_writer_embedding_calls=0,
        canary_window_seconds=(max(r["task_commit_unix_ns"] for r in tasks if r["index"] == 48) - min(r["task_start_unix_ns"] for r in tasks if r["index"] == 48)) / 1e9,
        remaining_window_seconds=(max(r["task_commit_unix_ns"] for r in tasks if r["index"] != 48) - min(r["task_start_unix_ns"] for r in tasks if r["index"] != 48)) / 1e9,
        money=None, price_status="unknown; no verified invoice or price manifest",
        limits=["R=1, development tasks already seen historically", "Variable GLM model alias; historical reference not randomized contemporaneous control",
                "316 scoring-shadow and historical 954 infrastructure caveats retained", "Memory exposure is not proof of semantic use or causal benefit",
                "No exact per-memory token/cache attribution", "Three system designs, not isolated component ablation"],
        analysis_source_hash=sha(__file__))
    save(ROOT / "records/analysis.json", final)
    print(json.dumps(dict(status=final["status"], logical_calls=final["logical_calls"], peak=peak,
                         unknown_usage=final["unknown_usage_attempts"], scores=summaries["original_scored_46"])))


if __name__ == "__main__":
    main()
