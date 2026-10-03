"""Exact file fragments and terminal output exposure audit for the native modes."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from native_memory import NativeSession, digest, ROOT
from run_native import read
from audit import rows, content


def audit_task(folder, corpus, config):
    folder = Path(folder)
    commit = read(folder / "commit.json")
    assert commit["config_hash"] == digest(config)
    identity = read(folder / "identity.json")
    method = identity["method"]
    session = NativeSession(corpus, method)
    initial = read(folder / "input-public.json")
    assert initial["system"] == session.system()
    assert not (folder / "legal-episode.json").exists()
    assert read(folder / "injected.json") == []
    for filename in ("memory-before.json", "memory-after.json"):
        assert digest(read(folder / filename)) == corpus.archive.library_hash
    access = rows(folder / "memory-access.jsonl")
    seen, repeated = defaultdict(set), 0
    for row in access:
        result = row["result"]
        assert digest(result) == row["result_hash"]
        assert result["library_hash"] == corpus.archive.library_hash and result["corpus_hash"] == corpus.hash
        assert row["returned_utf8_bytes"] <= 12000
        assert row["cumulative_memory_bytes_including_startup"] <= 48000
        for item in result["items"]:
            if "path" in item:
                relative = corpus.resolve(item["path"])
                lines = corpus.files[relative].splitlines(keepends=True)
                selected = "".join(lines[item["start_line"] - 1:item["end_line"]])
                assert item["content"] == selected[item["start_char"]:item["end_char"]]
                assert item["file_sha256"] == corpus.hashes[relative]
                base = len("".join(lines[:item["start_line"] - 1]))
                chars = set(range(base + item["start_char"], base + item["end_char"]))
                repeated += len(chars & seen[relative])
                seen[relative].update(chars)
            else:
                assert item["kind"] == "terminal_output"
                diagnostic = row["diagnostics"]
                assert diagnostic["stdout"].startswith(item["content"])
                assert diagnostic["stderr"].startswith(item["stderr"])
                assert diagnostic["trace_present"]
                path = (ROOT / diagnostic["audit_relative_path"] / "access.strace").resolve()
                assert path.is_relative_to((ROOT / ".runtime/shell-audit").resolve())
                text = path.read_text(encoding="utf-8", errors="replace")
                assert hashlib.sha256(text.encode()).hexdigest() == diagnostic["trace_sha256"]
                assert item["opened_memory_files"] == diagnostic["opened_memory_files"]
                assert all(corpus.resolve(p) in corpus.files for p in item["opened_memory_files"])
                assert all(sid in corpus.archive.by_source for sid in item["source_ids"])
    registered = {r["tool_call_id"]: r for r in rows(folder / "memory-results.jsonl")}
    assert len(registered) == len(access)
    for row in access:
        registered_result = registered[row["tool_call_id"]]
        assert json.loads(registered_result["serialized"]) == row["result"]
        assert hashlib.sha256(registered_result["serialized"].encode()).hexdigest() == registered_result["result_sha256"]
    exposures = {(r["call_id"], r["http_attempt"]): r for r in rows(folder / "memory-exposure.jsonl")}
    requests = rows(folder / "requests.jsonl")
    assert len(exposures) == len(requests)
    max_visible = 0
    for request in requests:
        payload = read(folder / request["artifact"])
        assert payload["model"] == config["model"]["api_id"]
        assert content(payload["messages"][0]) == initial["system"]
        assert content(payload["messages"][1]) == initial["prompt"]
        assert request["all_injected_blocks_mapped"]
        assert request["blocks"][0]["content_sha256"] == hashlib.sha256(session.prelude().encode()).hexdigest()
        mapping = exposures[(request["call_id"], request["http_attempt"])]
        assert mapping["actual_body_sha256"] == request["actual_body_sha256"]
        visible = set()
        for block in mapping["mappings"]:
            stored = registered[block["tool_call_id"]]
            assert stored["result_sha256"] == block["result_sha256"] and stored["ranges"] == block["ranges"]
            matches = [i for i, m in enumerate(payload["messages"]) if m["role"] == "tool" and m.get("tool_call_id") == block["tool_call_id"]]
            assert matches == [m["message_index"] for m in block["matches"]]
            for i in matches:
                assert content(payload["messages"][i]) == stored["serialized"]
                visible.add(block["tool_call_id"])
        for message in payload["messages"]:
            if message["role"] == "tool":
                value = json.loads(content(message))
                if isinstance(value, dict) and value.get("memory_version"):
                    assert message["tool_call_id"] in visible
        max_visible = max(max_visible, len(visible))
    tools = rows(folder / "tools.jsonl")
    starts = [r for r in tools if r["event"] == "tool_start"]
    ended = {r["tool_call_id"] for r in tools if r["event"] in ("tool_end", "tool_error")}
    assert all(r["tool_call_id"] in ended for r in starts)
    counts = Counter(r["name"] for r in starts)
    return commit["result"] | dict(audit_passed=True, memory_calls=len(access), python_calls=counts["PYTHON"],
        glob_calls=counts["MEMORY_GLOB"], grep_calls=counts["MEMORY_GREP"], read_calls=counts["MEMORY_READ_FILE"],
        shell_calls=counts["MEMORY_SHELL"], memory_response_bytes=sum(r["returned_utf8_bytes"] for r in access),
        startup_memory_bytes=len(session.prelude().encode()),
        memory_repeated_source_chars=repeated if method == "native_files" else None,
        memory_error_calls=sum(bool(r["result"].get("error")) for r in access),
        maximum_visible_memory_results=max_visible,
        terminal_nonzero_calls=sum(r["result"].get("returncode", 0) != 0 for r in access),
        shell_exact_source_span_status="not_inferred_from_transformed_stdout" if method == "native_shell" else "exact_file_ranges")
