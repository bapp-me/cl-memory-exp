"""Read-only final audit and five-mode comparison. No model calls or reruns."""
from collections import Counter
from datetime import datetime
import json

from native_memory import ROOT, BASE, METHODS, NativeSession
from run_native import REPO, OBS, check, engine, run_folder, save, read, sha
from audit_native import audit_task
from audit import rows
import analyze as first_analysis


def summary(group):
    copied = [dict(row, memory_repeated_source_chars=row.get("memory_repeated_source_chars") or 0,
                   corresponding_source_exposed=row.get("corresponding_source_exposed", row.get("corresponding_source_injected", False)) or False)
              for row in group]
    result = first_analysis.summary(copied)
    if any(row.get("memory_repeated_source_chars") is None for row in group):
        result["repeated_source_chars"] = None
    if any(row.get("method") == "native_shell" for row in group):
        result["corresponding_source_exposed"] = None
    result.update(glob_calls=sum(r.get("glob_calls", 0) for r in group),
                  grep_calls=sum(r.get("grep_calls", 0) for r in group),
                  shell_calls=sum(r.get("shell_calls", 0) for r in group),
                  startup_memory_bytes=sum(r.get("startup_memory_bytes", 0) for r in group),
                  terminal_nonzero_calls=sum(r.get("terminal_nonzero_calls", 0) for r in group))
    return result


def main():
    config, corpus = check()
    eng, _ = engine()
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    source_map = {r["id"]: i for i, r in enumerate(assets[:48])}
    metric = first_analysis.metrics_function()
    missing = [(m, i) for m in METHODS for i in range(48, 96) if not (run_folder(m, i) / "commit.json").exists()]
    if missing:
        raise RuntimeError(f"Incomplete: {missing}")
    tasks, intervals, models, statuses = [], [], Counter(), Counter()
    for method in METHODS:
        for index in range(48, 96):
            folder = run_folder(method, index)
            row = audit_task(folder, corpus, config)
            initial = read(folder / "input-public.json")
            assert initial["prompt"] == assets[index]["problem"]
            assert initial["tools"] == [*eng.CODE_TOOLS, *NativeSession(corpus, method).tools]
            ledger = read(folder / "call-ledger.json")
            attempts = [a for call in ledger for a in call["http_attempts"]]
            used = [eng.normalized_usage(a["raw_usage"]) for a in attempts]
            known = {k: sum(u[k] for u in used if u is not None) for k in eng.USAGE_FIELDS}
            assert known == row["known_usage_subtotal"]
            assert sum(u is None for u in used) == row["unknown_usage_http_attempts"]
            for a in attempts:
                models[str(a["provider_model"])] += 1
                statuses[str(a["status"])] += 1
                for key, sign in (("started_at", 1), ("finished_at", -1)):
                    intervals.append((datetime.fromisoformat(a[key].replace("Z", "+00:00")).timestamp(), sign))
            access = rows(folder / "memory-access.jsonl")
            detailed_sources, opened_sources = set(), set()
            for request in rows(folder / "memory-exposure.jsonl"):
                for mapping in request["mappings"]:
                    if not mapping["matches"]:
                        continue
                    for item in mapping["ranges"]:
                        if item.get("path", "").startswith(("/memory/episodes/", "/memory/raw/")):
                            detailed_sources.update(item["source_ids"])
                        elif item.get("kind") == "terminal_output":
                            opened_sources.update(item["source_ids"])
            corresponding = f"s{source_map[assets[index]['id']]:03d}"
            timeline = rows(folder / "controller-events.jsonl")
            row.update(index=index, source_path=folder.relative_to(REPO).as_posix(),
                corresponding_source_id=corresponding, corresponding_source_exposed=corresponding in detailed_sources if method == "native_files" else None,
                corresponding_source_opened=corresponding in opened_sources,
                detailed_source_ids=sorted(detailed_sources), shell_opened_source_ids=sorted(opened_sources),
                tool_metrics=metric(read(folder / "pi-result.json")),
                access_commands=[dict(name=r["name"], args=r["args"], returncode=r["result"].get("returncode"),
                                      error=r["result"].get("error")) for r in access],
                task_start_unix_ns=next(r["at_unix_ns"] for r in timeline if r["event"] == "task_start"),
                task_commit_unix_ns=next(r["at_unix_ns"] for r in timeline if r["event"] == "task_commit"))
            tasks.append(row)
    active = peak = 0
    for _, delta in sorted(intervals):
        active += delta
        peak = max(peak, active)
    assert active == 0 and peak <= 48
    previous = read(BASE / "records/analysis.json")
    legacy = read(REPO / "experiments/section7_analysis_20261003/records/d0-tasks.json")
    groups = {"historical_no_memory": [r for r in legacy if r["method"] == "no_memory" and r["benchmark"] == "codeeval" and r["index"] >= 48],
              "frozen_jaccard": read(REPO / "experiments/section7_frozen_jaccard_20261004/records/results.json")["rows"]}
    groups.update({method: [r for r in previous["rows"] if r["method"] == method] for method in first_analysis.METHODS})
    groups.update({method: [r for r in tasks if r["method"] == method] for method in METHODS})
    scopes = dict(all_48=lambda r: True, original_scored_46=lambda r: r["scorable"] is True,
        diagnostic_45_exclude_316=lambda r: r["scorable"] is True and r["task_id"] != "new:BigCodeBench/316",
        diagnostic_44_exclude_316_954=lambda r: r["scorable"] is True and r["task_id"] not in ("new:BigCodeBench/316", "new:BigCodeBench/954"))
    summaries = {scope: {method: summary([r for r in group if keep(r)]) for method, group in groups.items()} for scope, keep in scopes.items()}
    paired = {method: {reference: first_analysis.pairs(groups[method], group) for reference, group in groups.items() if reference != method} for method in METHODS}
    result = dict(status="all_96_native_and_144_initial_completed", native_tasks=96, total_new_tasks=240,
        source_only_invariant_passed=True, corpus_hash=corpus.hash, logical_calls=sum(r["calls"] for r in tasks),
        http_attempts=sum(r["http_attempts"] for r in tasks), unknown_usage_attempts=sum(r["unknown_usage_http_attempts"] for r in tasks),
        provider_models=dict(models), http_statuses=dict(statuses), observed_peak_http_attempts=peak,
        terminal_states=dict(Counter(r["terminal_state"] for r in tasks)),
        all_task_known_usage={k: sum(r["known_usage_subtotal"][k] for r in tasks) for k in eng.USAGE_FIELDS},
        summaries=summaries, paired=paired, rows=tasks,
        remaining_window_seconds=(max(r["task_commit_unix_ns"] for r in tasks if r["index"] != 48) - min(r["task_start_unix_ns"] for r in tasks if r["index"] != 48)) / 1e9,
        limits=previous["limits"] + ["Native startup index differs across file and shell modes",
            "Shell opened files do not prove exact source content exposure; repeated source chars unknown"],
        money=None, analysis_source_hash=sha(__file__))
    save(ROOT / "records/analysis.json", result)
    print(json.dumps(dict(status=result["status"], calls=result["logical_calls"], peak=peak,
                         unknown_usage=result["unknown_usage_attempts"], summaries=summaries["original_scored_46"])))


if __name__ == "__main__":
    main()
