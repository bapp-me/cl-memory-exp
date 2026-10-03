"""Full round cost/quality audit, pre-registered decision, and bounded GLM follow-up selection."""
import argparse
from collections import Counter
import copy
from datetime import datetime

from common_opt import *
from round_runner import check, folder
from audit_round import audit_task
import run_native


def summarize(rows):
    return dict(tasks=len(rows), correct=sum(r["correct"] is True for r in rows),
        tokens=sum(r["known_usage_subtotal"]["totalTokens"] for r in rows),
        input_tokens=sum(r["known_usage_subtotal"]["input"] for r in rows),
        cache_read_tokens=sum(r["known_usage_subtotal"]["cacheRead"] for r in rows),
        output_tokens=sum(r["known_usage_subtotal"]["output"] for r in rows),
        python_calls=sum(r["python_calls"] for r in rows), memory_calls=sum(r["memory_calls"] for r in rows),
        solver_calls=sum(r["calls"] for r in rows), memory_response_bytes=sum(r["memory_response_bytes"] for r in rows),
        full_backend_response_bytes=sum(r.get("full_backend_response_bytes", r["memory_response_bytes"]) for r in rows),
        errors=sum(r["memory_error_calls"] for r in rows),
        no_memory_call_tasks=sum(not r["memory_calls"] for r in rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("round_id", choices=["r1", "r2", "r3"])
    args = parser.parse_args()
    rid = args.round_id
    config, corpus = check(rid)
    hypothesis = read(ROOT / "rounds" / rid / "hypothesis.json")
    reference_round = hypothesis.get("reference_round")
    reference_rows = read(ROOT / "rounds" / reference_round / "analysis.json")["rows"] if reference_round else [
        r for r in baseline_rows() if r["method"] == "native_files"]
    baseline = {r["index"]: r for r in reference_rows}
    eng, _ = run_native.engine()
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    result, intervals = [], []
    for index in range(48, 96):
        directory = folder(rid, index)
        row = audit_task(directory, corpus, config)
        initial = read(directory / "input-public.json")
        assert initial["prompt"] == assets[index]["problem"]
        assert row["scorable"] == baseline[index]["scorable"]
        ledger = read(directory / "call-ledger.json")
        attempts = [a for c in ledger for a in c["http_attempts"]]
        used = [eng.normalized_usage(a["raw_usage"]) for a in attempts]
        assert sum(u is None for u in used) == row["unknown_usage_http_attempts"]
        assert {k: sum(u[k] for u in used if u is not None) for k in eng.USAGE_FIELDS} == row["known_usage_subtotal"]
        for attempt in attempts:
            for key, delta in (("started_at", 1), ("finished_at", -1)):
                intervals.append((datetime.fromisoformat(attempt[key].replace("Z", "+00:00")).timestamp(), delta))
        old = baseline[index]
        row.update(index=index, round_id=rid, source_path=directory.relative_to(REPO).as_posix(),
            baseline_correct=old["correct"], baseline_tokens=old["known_usage_subtotal"]["totalTokens"],
            tokens_delta=row["known_usage_subtotal"]["totalTokens"] - old["known_usage_subtotal"]["totalTokens"],
            python_delta=row["python_calls"] - old["python_calls"],
            result_status=result_status(row))
        result.append(row)
    active = peak = 0
    for _, change in sorted(intervals):
        active += change
        peak = max(peak, active)
    assert active == 0 and peak <= 48
    eligible = [r for r in result if r["scorable"]]
    reference_rows = list(baseline.values())
    scopes = {"all48": (result, reference_rows),
              "scored46": (eligible, [r for r in reference_rows if r["scorable"]]),
              "diagnostic45": ([r for r in eligible if r["index"] != 49], [r for r in reference_rows if r["scorable"] and r["index"] != 49]),
              "diagnostic44": ([r for r in eligible if r["index"] not in (49, 56)], [r for r in reference_rows if r["scorable"] and r["index"] not in (49, 56)])}
    summaries = {name: dict(candidate=summarize(new), reference=summarize(old)) for name, (new, old) in scopes.items()}
    acceptance = hypothesis["acceptance"]
    checks = dict(quality=summaries["scored46"]["candidate"]["correct"] >= acceptance["min_quality_correct_of46"],
        tokens_all48=summaries["all48"]["candidate"]["tokens"] <= summaries["all48"]["reference"]["tokens"] * (1-acceptance["min_total_token_reduction_fraction"]),
        tokens_scored46=summaries["scored46"]["candidate"]["tokens"] <= summaries["scored46"]["reference"]["tokens"] * (1-acceptance["min_total_token_reduction_fraction"]),
        python_all48=summaries["all48"]["candidate"]["python_calls"] <= acceptance["max_python_calls_all48"],
        python_scored46=summaries["scored46"]["candidate"]["python_calls"] <= acceptance["max_python_calls_scored46"],
        all_source_and_payload_audits=True, unknown_usage_absent=all(not r["unknown_usage_http_attempts"] for r in result))
    decision = dict(round_id=rid, hypothesis_sha256=sha(ROOT / "rounds" / rid / "hypothesis.json"),
        reference=reference_round or "original_native_files",
        result="passes_preregistered_screen" if all(checks.values()) else "does_not_pass_preregistered_screen",
        checks=checks, summaries=summaries,
        gains=[r["task_id"] for r in eligible if r["correct"] and not r["baseline_correct"]],
        losses=[r["task_id"] for r in eligible if r["baseline_correct"] and not r["correct"]],
        peak_http_attempts=peak, logical_calls=sum(r["calls"] for r in result), unknown_usage_attempts=sum(r["unknown_usage_http_attempts"] for r in result),
        no_stability_or_strict_causal_claim=True, rows=result)
    save(ROOT / "rounds" / rid / "analysis.json", decision)
    if hypothesis.get("post_round_review_max_independent_targets") == 0:
        save(ROOT / "records" / f"review-manifest-{rid}.json", dict(cases=[], total=0,
            reason="Final-round stop: offline analysis only, no additional reviewer calls"))
        print(json.dumps({k:decision[k] for k in ("round_id", "result", "checks", "summaries", "gains", "losses", "logical_calls")}))
        return
    # Fixed selection rule: up to six changed outcomes, three unchanged successes and three unchanged failures.
    groups = [[r for r in eligible if r["correct"] != r["baseline_correct"]],
              [r for r in eligible if r["correct"] and r["baseline_correct"]],
              [r for r in eligible if not r["correct"] and not r["baseline_correct"]]]
    selected = []
    for group, count in zip(groups, (6, 3, 3)):
        selected += sorted(group, key=lambda r: digest(["round-review-v1", rid, r["index"]]))[:count]
    used_indices = {r["index"] for r in selected}
    selected += sorted([r for r in eligible if r["index"] not in used_indices],
                       key=lambda r: digest(["round-review-v1", rid, r["index"]]))[:12-len(selected)]
    initial_manifest = read(ROOT / "records/review-manifest-initial.json")
    cases = []
    for row in selected:
        old = next(c for c in initial_manifest["cases"] if c["method"] == "native_files" and c["index"] == row["index"])
        packet = copy.deepcopy(read(ROOT / old["packet"]))
        cid = "review-" + digest([rid, row["index"]])[:14]
        packet["case_id"], packet["result_status"] = cid, row["result_status"]
        directory = REPO / row["source_path"]
        access = jsonl(directory / "memory-access.jsonl")
        replace = dict(target_visible=visible(read(directory / "pi-result.json")["messages"]),
            target_startup_memory=read(directory / "input-public.json")["memory_blocks"],
            target_evaluation_offline=read(directory / "evaluator.json"),
            retrieval_and_packing=[dict(name=r["name"], args=r["args"], truncated=r["result"].get("packing_truncated"),
                error=r["result"].get("error"), full_bytes=r["full_backend_response_bytes"], actual_bytes=r["returned_utf8_bytes"])
                for r in access],
            exposure_summary=dict(exact_actual_payload_mapping_passed=True,
                full_private_metadata_preserved=True, compact_results_verified_against_source=True),
            mechanical_metrics={k:v for k,v in row.items() if k not in ("source_path", "run_id", "attempt_id", "method")})
        for section in packet["evidence"]:
            if section["id"] in replace:
                section["text"] = json.dumps(replace[section["id"]], ensure_ascii=False, indent=2)
        packet["evidence"].append(dict(id="reference_execution_metrics", truncated=False,
            text=json.dumps({k:baseline[row["index"]][k] for k in ("correct", "scorable", "known_usage_subtotal", "python_calls", "memory_calls", "memory_response_bytes")}, ensure_ascii=False, indent=2),
            note="Original native-file reference, historical R=1; not proof of stable counterfactual effect"))
        path = ROOT / "packets" / rid / (cid + ".json")
        save(path, packet)
        cases.append(dict(case_id=cid, method=rid, index=row["index"], task_id=row["task_id"], result_status=row["result_status"],
                          packet=path.relative_to(ROOT).as_posix(), packet_sha256=sha(path), packet_bytes=path.stat().st_size))
    save(ROOT / "records" / f"review-manifest-{rid}.json", dict(cases=cases, total=len(cases),
        selection="SHA256 round-review-v1; 6 changed/3 unchanged success/3 unchanged failure, deterministic fill; <=12 independent targets"))
    print(json.dumps({k:decision[k] for k in ("round_id", "result", "checks", "summaries", "gains", "losses", "logical_calls")}))


if __name__ == "__main__":
    main()
