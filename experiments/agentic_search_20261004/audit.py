"""Audit actual evidence, payloads and costs. No scoring labels enter memory."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from memory import digest


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()] if Path(path).exists() else []


def content(message):
    value = message.get("content", "")
    return value if isinstance(value, str) else "".join(c.get("text", "") for c in value if c.get("type") == "text")


def audit_task(folder, archive, config):
    folder = Path(folder)
    commit = read(folder / "commit.json")
    assert commit["config_hash"] == digest(config)
    assert not (folder / "legal-episode.json").exists()
    for name in ("memory-before.json", "memory-after.json"):
        assert digest(read(folder / name)) == archive.library_hash
    assert read(folder / "injected.json") == []
    access = [row for row in rows(folder / "memory-access.jsonl") if row["event"] == "memory_access"]
    ids = set(archive.events)
    for row in access:
        assert row["result_hash"] == digest(row["result"])
        assert row["result"]["library_hash"] == archive.library_hash
        for candidate in row["diagnostics"].get("candidates", []):
            assert candidate["event_id"] in ids
        for target in row["diagnostics"].get("edges", {}):
            assert target in ids
        for item in row["result"]["items"]:
            doc = archive.events[item["event_id"]]
            assert item["source_id"] == doc["source_id"]
            assert item["locator"] == doc["locator"]
            assert item["content_sha256"] == doc["content_sha256"]
            assert item["content"] == doc["text"][item["start_char"]:item["end_char"]]
            assert item["start_utf8_byte"] == len(doc["text"][:item["start_char"]].encode())
            assert item["end_utf8_byte"] == len(doc["text"][:item["end_char"]].encode())
        assert row["returned_utf8_bytes"] <= 12000
        assert row["cumulative_evidence_response_bytes"] <= 48000
    registered = {row["tool_call_id"]: row for row in rows(folder / "memory-results.jsonl")}
    assert len(registered) == len(access)
    for row in access:
        stored = registered[row["tool_call_id"]]
        assert json.loads(stored["serialized"]) == row["result"]
        assert hashlib.sha256(stored["serialized"].encode()).hexdigest() == stored["result_sha256"]
    requests = rows(folder / "requests.jsonl")
    exposures = rows(folder / "memory-exposure.jsonl")
    lookup = {(row["call_id"], row["http_attempt"]): row for row in exposures}
    assert len(lookup) == len(requests)
    initial = read(folder / "input-public.json")
    assert initial["system"] == config["system"]
    visible_counts = []
    for request in requests:
        payload = read(folder / request["artifact"])
        assert payload["model"] == config["model"]["api_id"]
        assert payload["messages"][0]["role"] == "system"
        assert content(payload["messages"][0]) == initial["system"]
        assert content(payload["messages"][1]) == initial["prompt"]
        exposure = lookup[(request["call_id"], request["http_attempt"])]
        assert exposure["actual_body_sha256"] == request["actual_body_sha256"]
        visible = []
        for mapping in exposure["mappings"]:
            assert mapping["tool_call_id"] in registered
            stored = registered[mapping["tool_call_id"]]
            assert mapping["result_sha256"] == stored["result_sha256"]
            assert mapping["ranges"] == stored["ranges"]
            actual = [i for i, message in enumerate(payload["messages"])
                      if message["role"] == "tool" and message.get("tool_call_id") == mapping["tool_call_id"]]
            assert actual == [m["message_index"] for m in mapping["matches"]]
            for index in actual:
                assert content(payload["messages"][index]) == stored["serialized"]
            if actual:
                visible.append(mapping["tool_call_id"])
        # A response can only be exposed after its own tool callback, never an unregistered foreign result.
        for message in payload["messages"]:
            if message["role"] == "tool":
                try:
                    result = json.loads(content(message))
                except (ValueError, TypeError):
                    continue
                if isinstance(result, dict) and result.get("memory_version"):
                    assert message["tool_call_id"] in visible
        visible_counts.append(len(visible))
    tool_rows = rows(folder / "tools.jsonl")
    starts = [r for r in tool_rows if r["event"] == "tool_start"]
    terminal_ids = {r["tool_call_id"] for r in tool_rows if r["event"] in ("tool_end", "tool_error")}
    assert all(r["tool_call_id"] in terminal_ids for r in starts)
    kinds = Counter(r["name"] for r in starts)
    result = commit["result"] | dict(memory_calls=len(access), search_calls=kinds["MEMORY_SEARCH"],
        read_calls=kinds["MEMORY_READ"], follow_calls=kinds["MEMORY_FOLLOW"], python_calls=kinds["PYTHON"],
        memory_response_bytes=sum(r["returned_utf8_bytes"] for r in access),
        memory_repeated_source_chars=sum(r["repeated_source_chars"] for r in access),
        memory_seconds=sum(r["duration_seconds"] for r in access),
        memory_error_calls=sum(bool(r["result"].get("error")) for r in access),
        maximum_visible_memory_results=max(visible_counts, default=0), audit_passed=True)
    return result


def summarize():
    from run import ROOT, METHODS, check_freeze, run_folder, save
    config, archive = check_freeze()
    records = []
    for method in METHODS:
        for index in range(48, 96):
            folder = run_folder(method, index)
            if (folder / "commit.json").exists():
                records.append(audit_task(folder, archive, config) | dict(index=index))
    summary = {}
    for method in METHODS:
        group = [r for r in records if r["method"] == method]
        eligible = [r for r in group if r.get("scorable")]
        summary[method] = dict(executed=len(group), eligible=len(eligible), correct=sum(r.get("correct") is True for r in eligible),
            all_task_known_tokens=sum(r["known_usage_subtotal"]["totalTokens"] for r in group),
            eligible_known_tokens=sum(r["known_usage_subtotal"]["totalTokens"] for r in eligible),
            unknown_usage_attempts=sum(r["unknown_usage_http_attempts"] for r in group),
            memory_calls=sum(r["memory_calls"] for r in group), python_calls=sum(r["python_calls"] for r in group),
            memory_response_bytes=sum(r["memory_response_bytes"] for r in group),
            memory_repeated_source_chars=sum(r["memory_repeated_source_chars"] for r in group),
            monetary_cost=None)
    save(ROOT / "records/results.json", dict(complete=len(records) == 144, per_method=summary, tasks=records))
    print(json.dumps(summary))


if __name__ == "__main__":
    summarize()
