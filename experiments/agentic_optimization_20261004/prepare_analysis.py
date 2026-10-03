"""A0/A1 full census and immutable GLM evidence packets. No model requests."""
from collections import Counter, defaultdict
import re
import statistics
import subprocess

from common_opt import *


def prepare():
    from run import check_freeze
    from run_native import check as check_native
    from audit import audit_task
    from audit_native import audit_task as audit_native
    initial_config, archive = check_freeze()
    native_config, corpus = check_native()
    rows = sorted(baseline_rows(), key=lambda r: (r["index"], METHODS.index(r["method"])))
    assert len(rows) == 240 and len({(r["method"], r["index"]) for r in rows}) == 240
    plan = subprocess.check_output(["git", "show", PLAN_REVISION + ":Agent_Memory_Research_Plan_CN_v1.0_Final.md"], cwd=REPO).decode("utf-8")
    section = plan[plan.index("## 07."):plan.index("## 08.")]
    (ROOT / "records").mkdir(parents=True, exist_ok=True)
    (ROOT / "records/v1.5-section7.md").write_text(section, encoding="utf-8")
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    source_index = {r["id"]: i for i, r in enumerate(assets[:48])}
    source_library = archive.snapshot()
    source_hashes = {}
    d0, cases = [], []
    known_contracts = read(REPO / "experiments/section7_analysis_20261003/records/priority-16-adjudication.json")

    def tracked(path):
        source_hashes[Path(path).relative_to(REPO).as_posix()] = sha(path)
        return read(path)

    for row in rows:
        folder = REPO / row["source_path"]
        audited = audit_native(folder, corpus, native_config) if row["method"].startswith("native_") else audit_task(folder, archive, initial_config)
        assert audited["correct"] == row["correct"] and audited["usage"] == row["usage"]
        identity = "review-" + digest(["five-agentic-v1", row["method"], row["index"]])[:14]
        pi = tracked(folder / "pi-result.json")
        evaluation = tracked(folder / "evaluator.json")
        initial = tracked(folder / "input-public.json")
        actual_memory = jsonl(folder / "memory-results.jsonl")
        access = [r for r in jsonl(folder / "memory-access.jsonl") if r["event"] == "memory_access"]
        requests = jsonl(folder / "requests.jsonl")
        exposure = jsonl(folder / "memory-exposure.jsonl")
        tool_starts = [r for r in jsonl(folder / "tools.jsonl") if r["event"] == "tool_start"]
        for filename in ("memory-access.jsonl", "memory-results.jsonl", "requests.jsonl", "memory-exposure.jsonl", "tools.jsonl", "call-ledger.json", "commit.json", "memory-before.json", "memory-after.json"):
            path = folder / filename
            if path.exists():
                source_hashes[path.relative_to(REPO).as_posix()] = sha(path)
        source = source_index[assets[row["index"]]["id"]]
        source_folder = LEGACY / "runs/full-codeeval-glm-no_memory" / f"{source:03d}"
        source_evaluation = tracked(source_folder / "evaluator.json")
        source_episode = json.loads(source_library[source]["text"])
        response_bytes = sum(len(r["serialized"].encode()) for r in actual_memory)
        content_bytes = 0
        for response in actual_memory:
            for item in json.loads(response["serialized"]).get("items", []):
                for field in ("content", "stderr"):
                    if isinstance(item.get(field), str):
                        content_bytes += len(json.dumps(item[field], ensure_ascii=False)[1:-1].encode())
        static_bytes = sum(sum(m["utf8_bytes"] for m in b["matches"]) for r in requests for b in r.get("blocks", []))
        dynamic_bytes = sum(sum(m["utf8_bytes"] for m in b["matches"]) for r in exposure for b in r["mappings"])
        memory_first = next((i for i, t in enumerate(tool_starts) if t["name"].startswith("MEMORY_")), None)
        python_first = next((i for i, t in enumerate(tool_starts) if t["name"] == "PYTHON"), None)
        queries = [r["args"].get("query", r["args"].get("pattern", r["args"].get("command", ""))) for r in access]
        nonempty_queries = [q for q in queries if q]
        repeat_queries = sum(n - 1 for n in Counter(nonempty_queries).values() if n > 1)
        record = dict(case_id=identity, method=row["method"], index=row["index"], task_id=row["task_id"],
            result_status=result_status(row), correct=row["correct"], scorable=row["scorable"], source_index=source,
            source_quality_direct=source_evaluation.get("correct"), source_scorable=source_evaluation.get("scorable"),
            usage=row["usage"], calls=row["calls"], http_attempts=row["http_attempts"],
            unknown_usage_attempts=row["unknown_usage_http_attempts"], seconds=row["seconds"],
            python_calls=row["python_calls"], memory_calls=row["memory_calls"], tool_metrics=row["tool_metrics"],
            no_active_memory_call=not access, memory_before_first_python=memory_first is not None and (python_first is None or memory_first < python_first),
            memory_response_bytes=response_bytes, quoted_content_bytes=content_bytes,
            non_content_response_bytes=response_bytes - content_bytes,
            non_content_response_fraction=(response_bytes - content_bytes) / response_bytes if response_bytes else None,
            startup_memory_bytes=row.get("startup_memory_bytes", 0), repeated_startup_payload_bytes=static_bytes,
            accumulated_dynamic_memory_payload_bytes=dynamic_bytes,
            request_payload_bytes=sum(r["bytes"] for r in requests),
            duplicate_query_or_command_calls=repeat_queries,
            exact_repeated_source_chars=row.get("memory_repeated_source_chars"),
            truncated_response_calls=sum(bool(r["result"].get("packing_truncated")) for r in access),
            empty_search_calls=sum(r["result"].get("total_matches") == 0 for r in access),
            memory_error_calls=row["memory_error_calls"],
            corresponding_source_exposed=row.get("corresponding_source_exposed"),
            corresponding_source_opened=row.get("corresponding_source_opened"),
            query_or_command_sequence=queries, budget_response_bytes_at_end=access[-1].get("cumulative_memory_bytes_including_startup", access[-1].get("cumulative_evidence_response_bytes")) if access else 0,
            source_path=row["source_path"], write_admission="not_applicable_frozen_archive", update_retention="not_applicable_no_writeback",
            true_recall="unavailable_no_relevance_gold", real_forgetting="not_applicable_frozen_archive",
            per_memory_tokens="unavailable", per_memory_cache="unavailable")
        d0.append(record)
        sections = []
        def add(name, value, note=None):
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
            # Hide implementation names while retaining observable tool signatures and behavior.
            for method in METHODS:
                text = text.replace(method, "anonymous_profile")
            sections.append(dict(id=name, text=text, truncated=False, note=note))
        add("target_prompt", assets[row["index"]]["problem"])
        add("target_visible", visible(pi["messages"]))
        add("target_startup_memory", initial.get("memory_blocks", []), "Only these blocks were supplied before dynamic access; not the whole library")
        add("target_evaluation_offline", evaluation, "Never seen by solver, no score changes allowed")
        add("target_contract_reference_offline", dict(reference_solution=assets[row["index"]]["solution"], tests=assets[row["index"]]["test_code"]), "Research-only; reference is not stronger than the task's explicit requirements")
        add("corresponding_source_original", source_episode, "Benchmark correspondence for offline opportunity audit, NOT gold source or evidence that it was retrieved")
        add("source_evaluation_offline", source_evaluation, "Research-only; a passing source does not validate every historical statement")
        diagnostics = [dict(tool_call_id=r["tool_call_id"], name=r["name"], args=r["args"],
                            truncated=r["result"].get("packing_truncated"), error=r["result"].get("error"),
                            returned_source_ids=sorted({s for item in r["result"].get("items", [])
                                for s in ([item["source_id"]] if "source_id" in item else item.get("source_ids", []))}),
                            candidate_count=len(r.get("diagnostics", {}).get("candidates", [])),
                            total_matches=r["result"].get("total_matches")) for r in access]
        add("retrieval_and_packing", diagnostics)
        add("exposure_summary", dict(exact_actual_payload_mapping_passed=True, startup_bytes=static_bytes,
             dynamic_bytes=dynamic_bytes, source_exposed=record["corresponding_source_exposed"],
             source_opened=record["corresponding_source_opened"],
             limitation="Shell file opens do not establish exact source content exposure; all actual memory tool results are in target_visible"))
        add("mechanical_metrics", {k: v for k, v in record.items() if k not in ("method", "source_path", "query_or_command_sequence")})
        contract = next((r for r in known_contracts["records"] if r["index"] == row["index"]), None)
        if contract:
            add("previous_contract_candidate", dict(status=contract["contract_status"], category=contract["diagnostic_category"],
                 limits="Previous AI audit candidate, not human truth; independently check present task and evaluator evidence"))
        packet = dict(case_id=identity, result_status=result_status(row), evidence=sections,
            global_rules="All 48 no-memory simple histories are legal and immutable; target traces never enter shared memory. No writer, no update or retention experiment. This is development data, R=1.",
            unavailable="No semantic recall gold, no hidden thinking, no causal use labels, no exact per-memory token/cache attribution")
        path = ROOT / "packets/initial" / (identity + ".json")
        if path.exists():
            assert read(path) == packet, "Review packet must not change after preparation"
        else:
            save(path, packet)
        cases.append(dict(case_id=identity, method=row["method"], index=row["index"], task_id=row["task_id"],
                          result_status=result_status(row), packet_sha256=sha(path), packet_bytes=path.stat().st_size,
                          packet=path.relative_to(ROOT).as_posix()))
    groups = {}
    for method in METHODS:
        group = [r for r in d0 if r["method"] == method]
        valid = [r for r in group if r["scorable"]]
        def aggregate(selected):
            totals = {key: sum(r[key] for r in selected) for key in ("calls", "python_calls", "memory_calls", "memory_response_bytes", "quoted_content_bytes", "non_content_response_bytes", "repeated_startup_payload_bytes", "accumulated_dynamic_memory_payload_bytes", "duplicate_query_or_command_calls", "truncated_response_calls", "empty_search_calls", "memory_error_calls")}
            return dict(tasks=len(selected), correct=sum(r["correct"] is True for r in selected),
                total_tokens=sum(r["usage"]["totalTokens"] for r in selected),
                no_active_memory_tasks=sum(r["no_active_memory_call"] for r in selected),
                non_content_fraction=totals["non_content_response_bytes"] / totals["memory_response_bytes"] if totals["memory_response_bytes"] else None,
                status_counts=dict(Counter(r["result_status"] for r in selected)), **totals)
        groups[method] = dict(all_48=aggregate(group), eligible_46=aggregate(valid))
    save(ROOT / "records/d0-initial.json", dict(tasks=d0, summary=groups, mechanical_tasks=240, new_model_calls=0))
    save(ROOT / "records/review-manifest-initial.json", dict(cases=cases, model="glm-5.3-flash", total=240,
         scope="User requested detailed analysis of all five new methods; initial full D1 census, not repeated each optimization round",
         source_files=source_hashes, max_packet_bytes=max(c["packet_bytes"] for c in cases)))
    print(json.dumps(dict(prepared=240, max_packet_bytes=max(c["packet_bytes"] for c in cases), summary=groups)))


if __name__ == "__main__":
    prepare()
