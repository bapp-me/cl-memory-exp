"""Audit compact public results against full private source mappings and actual payloads."""
from collections import Counter
import hashlib

from common_opt import *
from audit import content


def audit_task(folder, corpus, config):
    from round_runner import candidate_module
    module = candidate_module(config["round_id"])
    CandidateSession, compact_result = module.CandidateSession, module.compact_result
    folder = Path(folder)
    commit = read(folder / "commit.json")
    assert commit["config_hash"] == digest(config)
    session = CandidateSession(corpus, config["variant"])
    initial = read(folder / "input-public.json")
    assert initial["system"] == session.system()
    assert not (folder / "legal-episode.json").exists()
    for filename in ("memory-before.json", "memory-after.json"):
        assert digest(read(folder / filename)) == corpus.archive.library_hash
    access = jsonl(folder / "memory-access.jsonl")
    for row in access:
        full = row["full_result"]
        assert row["result"] == compact_result(full)
        assert row["result_hash"] == digest(row["result"])
        assert full["library_hash"] == corpus.archive.library_hash and full["corpus_hash"] == corpus.hash
        assert row["returned_utf8_bytes"] <= 12000
        assert row["cumulative_memory_bytes_including_startup"] <= 48000
        for item in full["items"]:
            relative = corpus.resolve(item["path"])
            lines = corpus.files[relative].splitlines(keepends=True)
            text = "".join(lines[item["start_line"] - 1:item["end_line"]])
            assert item["content"] == text[item["start_char"]:item["end_char"]]
            assert item["file_sha256"] == corpus.hashes[relative]
    registered = {r["tool_call_id"]: r for r in jsonl(folder / "memory-results.jsonl")}
    assert len(registered) == len(access)
    for row in access:
        stored = registered[row["tool_call_id"]]
        assert json.loads(stored["serialized"]) == row["result"]
        assert hashlib.sha256(stored["serialized"].encode()).hexdigest() == stored["result_sha256"]
    exposures = {(r["call_id"], r["http_attempt"]): r for r in jsonl(folder / "memory-exposure.jsonl")}
    requests = jsonl(folder / "requests.jsonl")
    assert len(exposures) == len(requests)
    max_visible = 0
    for request in requests:
        payload = read(folder / request["artifact"])
        assert content(payload["messages"][0]) == session.system()
        assert content(payload["messages"][1]) == initial["prompt"]
        assert payload["model"] == config["model"]["api_id"] and request["all_injected_blocks_mapped"]
        exposure = exposures[(request["call_id"], request["http_attempt"])]
        assert exposure["actual_body_sha256"] == request["actual_body_sha256"]
        visible = set()
        for mapping in exposure["mappings"]:
            stored = registered[mapping["tool_call_id"]]
            assert stored["result_sha256"] == mapping["result_sha256"] and stored["ranges"] == mapping["ranges"]
            matches = [i for i, message in enumerate(payload["messages"])
                       if message["role"] == "tool" and message.get("tool_call_id") == mapping["tool_call_id"]]
            assert matches == [m["message_index"] for m in mapping["matches"]]
            for i in matches:
                assert content(payload["messages"][i]) == stored["serialized"]
                visible.add(mapping["tool_call_id"])
        for message in payload["messages"]:
            if message["role"] == "tool":
                value = json.loads(content(message))
                if isinstance(value, dict) and value.get("memory_version"):
                    assert message["tool_call_id"] in visible
        max_visible = max(max_visible, len(visible))
    tools = jsonl(folder / "tools.jsonl")
    starts = [r for r in tools if r["event"] == "tool_start"]
    ends = {r["tool_call_id"] for r in tools if r["event"] in ("tool_end", "tool_error")}
    assert all(r["tool_call_id"] in ends for r in starts)
    counts = Counter(r["name"] for r in starts)
    return commit["result"] | dict(audit_passed=True, memory_calls=len(access), python_calls=counts["PYTHON"],
        glob_calls=counts["MEMORY_GLOB"], grep_calls=counts["MEMORY_GREP"], read_calls=counts["MEMORY_READ_FILE"],
        startup_memory_bytes=len(session.prelude().encode()), maximum_visible_memory_results=max_visible,
        memory_response_bytes=sum(r["returned_utf8_bytes"] for r in access),
        full_backend_response_bytes=sum(r["full_backend_response_bytes"] for r in access),
        memory_error_calls=sum(bool(r["result"].get("error")) for r in access))
