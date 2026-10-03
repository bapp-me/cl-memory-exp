"""No paid requests: content preservation, bounded reads, resume isolation and actual Pi payloads."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import uuid

from common_opt import *
from round_runner import check, candidate_module
import run_native as native
from audit_round import audit_task


def run(round_id):
    config, corpus = check(round_id)
    module = candidate_module(round_id)
    CandidateSession, compact_result = module.CandidateSession, module.compact_result
    before = after = calls = 0
    for row in baseline_rows():
        if row["method"] != "native_files":
            continue
        for access in jsonl(REPO / row["source_path"] / "memory-access.jsonl"):
            original = access["result"]
            compact = compact_result(original)
            assert size(compact) <= size(original)
            assert [i["content"] for i in compact["items"]] == [i["content"] for i in original["items"]]
            for old, new in zip(original["items"], compact["items"]):
                for field in ("path", "start_line", "end_line", "start_char", "end_char", "next_line", "next_start_char", "truncated"):
                    assert old.get(field) == new.get(field)
            before += size(original)
            after += size(compact)
            calls += 1
    session = CandidateSession(corpus, config["variant"])
    expected_entry = "memory_summary.md" if config["variant"] == "compact_lazy_index" else "MEMORY.md"
    assert session.prelude() == corpus.files[expected_entry]
    confirmation = None
    if config.get("confirmation_of"):
        prior = candidate_module(config["confirmation_of"]).CandidateSession(corpus, "compact")
        assert session.system() == prior.system() and session.tools == prior.tools
        # Pure codec identity is checked on all historical responses above and below.
        prior_codec = candidate_module(config["confirmation_of"]).compact_result
        for baseline in baseline_rows():
            if baseline["method"] == "native_files":
                for access in jsonl(REPO / baseline["source_path"] / "memory-access.jsonl"):
                    assert compact_result(access["result"]) == prior_codec(access["result"])
        confirmation = "same prompt/tools/codec as " + config["confirmation_of"]
    assert session.call("MEMORY_READ_FILE", dict(path="../../hidden"), "bad").get("error")
    assert session.call("MEMORY_READ_FILE", dict(path="episodes/s048.md"), "complex").get("error")
    query = session.call("MEMORY_GREP", dict(pattern="np.random", literal=True, glob="episodes/s000.md"), "grep")
    assert query["items"]
    session.used_bytes = 47000
    bounded = session.call("MEMORY_READ_FILE", dict(path="raw/s000.json", line_count=400), "budget")
    assert size(bounded) <= 1000 and session.used_bytes <= 48000
    assert digest(session.update(dict(text="COMPLEX_CANARY_NOT_SHARED"))) == corpus.archive.library_hash
    try:
        check("r4")
        raise AssertionError("Fourth round accepted")
    except ValueError:
        pass
    captures = []
    class Mock(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captures.append(payload)
            steps = [("MEMORY_GREP", dict(pattern="random", glob="episodes/s000.md", limit=10)),
                     ("MEMORY_READ_FILE", dict(path="episodes/s000.md", start_line=1, line_count=80)),
                     ("PYTHON", dict(code="print(42)")),
                     ("SUBMIT", dict(code="def task_func():\n    return 42\n"))]
            step = sum(m["role"] == "tool" for m in payload["messages"])
            name, args = steps[step]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            frames = [dict(id="mock-opt", model="glm-5.3-flash", choices=[dict(index=0,
                delta=dict(role="assistant", tool_calls=[dict(index=0, id=f"fixture_{step}", type="function",
                    function=dict(name=name, arguments=json.dumps(args)))]), finish_reason=None)]),
                dict(choices=[dict(index=0, delta={}, finish_reason="tool_calls")]),
                dict(choices=[], usage=dict(prompt_tokens=100, completion_tokens=10, total_tokens=110))]
            for frame in frames:
                self.wfile.write(("data: " + json.dumps(frame) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    eng, _ = native.engine()
    eng.sandbox = lambda *a, **k: dict(returncode=0, stdout="42\n", stderr="")
    eng.grade_code = lambda row, code: dict(correct=code == "def task_func():\n    return 42\n", scorable=True, tests_run=1, checks_executed=1)
    fixture_config = json.loads(json.dumps(config))
    fixture_config["model"]["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
    prefix = "optimization-fixture-" + uuid.uuid4().hex
    try:
        eng.run_task(fixture_config, "native_files", "codeeval", 999,
            dict(category="fixture", id="fixture", problem="Return42. Synthetic interface check."),
            corpus.archive.snapshot(), "fixture-not-secret", run_prefix=prefix,
            adapter=CandidateSession(corpus, config["variant"]))
        result = audit_task(native.run_folder("native_files", 999, prefix), corpus, fixture_config)
        assert result["correct"] is True and result["maximum_visible_memory_results"] >= 2
    finally:
        server.shutdown()
        server.server_close()
    corpus.verify()
    check(round_id)
    value = dict(passed=True, paid_model_calls=0, mock_http_requests=len(captures),
        replayed_original_calls=calls, original_bytes=before, compact_bytes=after,
        byte_reduction_fraction=1 - after / before,
        exact_content_and_read_navigation_preserved=True, source_only=True, fourth_round_rejected=True,
        fixture_folder=native.run_folder("native_files", 999, prefix).relative_to(REPO).as_posix(),
        freeze_hash=sha(ROOT / "rounds" / round_id / "freeze.json"))
    value["confirmation_equivalence"] = confirmation
    save(ROOT / "rounds" / round_id / "fixtures.json", value)
    print(json.dumps(value))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("round_id")
    args = parser.parse_args()
    run(args.round_id)
