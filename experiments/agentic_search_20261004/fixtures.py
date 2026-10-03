"""Zero paid calls: corpus, adversarial isolation, real Pi + mock provider, and WSL checks."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import subprocess
import threading
import uuid

from audit import audit_task, rows
from memory import Archive, METHODS, Session, digest
from run import ROOT, OBS, SOURCE, SYSTEM, check_freeze, engine, read, run_folder, save, sha


def unit_checks(archive):
    source = archive.snapshot()
    checks = []
    for method in METHODS:
        s = Session(archive, method)
        result = s.call("MEMORY_SEARCH", {"query": "normal random numpy"}, "search")
        assert result["items"] and result["total_matches"] > 0
        assert all(x["event_id"] in archive.events for x in result["items"])
        empty = s.call("MEMORY_SEARCH", {"query": "QZXZXYQ_UNIQUE_ABSENT_555"}, "missing")
        if method != "hybrid_context":
            assert not empty["items"]
        # Hybrid character overlap may produce weak candidates; never call it semantic truth.
        rejected = s.call("MEMORY_READ", {"event_id": "../../other-target/trace.json"}, "traversal")
        assert rejected.get("error") and not rejected["items"]
        complex_id = s.call("MEMORY_READ", {"event_id": "s048:e001"}, "foreign")
        assert complex_id.get("error")
        wrong_scope = s.call("MEMORY_SEARCH", {"query": "numpy", "source_id": "s048"}, "scope")
        assert wrong_scope.get("error")
        extra = s.call("MEMORY_READ", {"event_id": "s000:e000", "path": "secret"}, "unknown-param")
        assert extra.get("error")
        for page in (0, 1):
            out = s.call("MEMORY_SEARCH", {"query": "", "page": page}, "list" + str(page))
            assert len(out["items"]) >= 5
        checks.append(method + ":search_paging_scope_traversal")
    long_source = archive.snapshot()
    long_episode = json.loads(long_source[0]["text"])
    long_episode["trajectory"].append(dict(type="text", text="UTF8中文🙂 long event " * 3000))
    long_source[0]["text"] = json.dumps(long_episode, ensure_ascii=False)
    long_archive = Archive(long_source)
    s = Session(long_archive, "lexical", max_calls=100)
    eid = max(long_archive.events, key=lambda i: len(long_archive.events[i]["text"]))
    first = s.call("MEMORY_READ", {"event_id": eid, "max_chars": 8000}, "long")
    assert first["items"][0]["next_start_char"] is not None
    start = first["items"][0]["next_start_char"]
    second = s.call("MEMORY_READ", {"event_id": eid, "start_char": start, "max_chars": 8000}, "continue")
    assert first["items"][0]["end_char"] == second["items"][0]["start_char"]
    s.call("MEMORY_READ", {"event_id": eid, "max_chars": 8000}, "repeat")
    assert s.records[-1]["repeated_source_chars"] > 0
    for i in range(30):
        s.call("MEMORY_READ", {"event_id": eid, "max_chars": 8000}, "budget" + str(i))
    assert s.returned_bytes <= 48000 and s.records[-1]["result"].get("error")
    limited = Session(archive, "lexical", max_calls=1)
    limited.call("MEMORY_SEARCH", {"query": "numpy"}, "one")
    assert limited.call("MEMORY_SEARCH", {"query": "numpy"}, "two").get("error")
    graph = Session(archive, "graph_walk")
    paired = graph.call("MEMORY_FOLLOW", {"event_id": "s000:e001", "relation": "action_result"}, "pair")
    assert [r["event_id"] for r in paired["items"]] == ["s000:e002"]
    graph.call("MEMORY_FOLLOW", {"event_id": "s000:e001", "relation": "symbol"}, "symbol")
    assert all(i["event_id"] in archive.events for i in graph.records[-1]["result"]["items"])
    assert Session(archive, "lexical").call("MEMORY_FOLLOW", {"event_id": "s000:e001", "relation": "symbol"}, "disabled").get("error")
    poisoned = source + [{"sequence": 48, "text": "COMPLEX_TRAJECTORY_CANARY"}]
    try:
        Archive(poisoned)
        raise AssertionError("Mixed source accepted")
    except ValueError:
        pass
    try:
        graph.restore_checkpoint(None, poisoned)
        raise AssertionError("Mixed checkpoint accepted")
    except ValueError:
        pass
    assert graph.update(poisoned[-1]) == source
    # Concurrent readers share no counters/ranges/results; no target text can become a candidate.
    def independent(i):
        local = Session(archive, METHODS[i % 3])
        local.call("MEMORY_READ", {"event_id": "s000:e001"}, str(i))
        assert local.calls == 1 and local.records[-1]["repeated_source_chars"] == 0
        assert local.update(dict(text="COMPLEX_TRAJECTORY_CANARY_" + str(i))) == source
        return True
    with ThreadPoolExecutor(max_workers=48) as pool:
        assert all(pool.map(independent, range(96)))
    assert archive.snapshot() == source and digest(source) == archive.library_hash
    checks += ["long_event_resume", "repeated_ranges", "memory_budgets", "graph_relations", "unknown_tool_denied",
               "complex_ingestion_denied", "checkpoint_mutation_denied", "writeback_discarded", "96_independent_readers"]
    return checks


def pi_checks(archive, config):
    captures = []
    class Mock(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captures.append(payload)
            graph = any(t["function"]["name"] == "MEMORY_FOLLOW" for t in payload["tools"])
            choices = [("MEMORY_SEARCH", dict(query="numpy random normal")),
                       ("MEMORY_READ", dict(event_id="s000:e001", max_chars=1200))]
            if graph:
                choices += [("MEMORY_FOLLOW", dict(event_id="s000:e001", relation="action_result"))]
            choices += [("PYTHON", dict(code="print(42)")), ("SUBMIT", dict(code="def task_func():\n    return 42\n"))]
            step = sum(m["role"] == "tool" for m in payload["messages"])
            name, args = choices[step]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            frames = [dict(id="mock-only", model="glm-5.3-flash", choices=[dict(index=0,
                delta=dict(role="assistant", tool_calls=[dict(index=0, id=f"fixture_call_{step}", type="function",
                    function=dict(name=name, arguments=json.dumps(args)))]), finish_reason=None)]),
                dict(choices=[dict(index=0, delta={}, finish_reason="tool_calls")]),
                dict(choices=[], usage=dict(prompt_tokens=100 + step, completion_tokens=10, total_tokens=110 + step))]
            for frame in frames:
                self.wfile.write(("data: " + json.dumps(frame) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    eng, _ = engine()
    eng.sandbox = lambda *a, **k: dict(returncode=0, stdout="42\n", stderr="")
    eng.grade_code = lambda row, code: dict(correct=code == "def task_func():\n    return 42\n", scorable=True, tests_run=1, checks_executed=1)
    fixture_config = json.loads(json.dumps(config))
    fixture_config["model"]["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
    prefix = "agentic-fixture-" + uuid.uuid4().hex
    results = []
    try:
        for method in METHODS:
            task = dict(category="fixture", id="fixture", problem="Submit a function task_func returning 42. Mock-only interface check.")
            eng.run_task(fixture_config, method, "codeeval", 999, task, archive.snapshot(), "fixture-not-secret",
                         run_prefix=prefix, adapter=Session(archive, method))
            folder = run_folder(method, 999, prefix)
            audited = audit_task(folder, archive, fixture_config)
            assert audited["correct"] is True and audited["unknown_usage_http_attempts"] == 0
            assert audited["maximum_visible_memory_results"] >= 2
            assert audited["python_calls"] == 1
            assert audited["memory_calls"] == (3 if method == "graph_walk" else 2)
            assert rows(folder / "stream-timing.jsonl")
            results.append(dict(method=method, passed=True, mock_requests=audited["http_attempts"],
                                folder=folder.relative_to(ROOT.parents[1]).as_posix()))
    finally:
        server.shutdown()
        server.server_close()
    return dict(passed=True, paid_model_calls=0, mock_http_requests=len(captures), methods=results)


def sandbox_checks():
    eng, _ = engine()
    folder = OBS / ".runtime/sandbox-canary" / ("agentic-" + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    code = """import os,json,socket
import numpy,pandas,scipy,matplotlib,sklearn
assert not os.path.exists('/mnt/d/campus_re')
assert not os.path.exists('/home/fucak')
assert not os.path.exists('/work/../runs')
assert not os.getenv('EXPERIMENT_API_KEY')
s=socket.socket();s.settimeout(1)
try:
    s.connect(('1.1.1.1',443))
    raise AssertionError('Network unexpectedly available')
except OSError:
    pass
print(json.dumps({'isolated':True,'deps':True}))
"""
    (folder / "probe.py").write_text(code, encoding="utf-8")
    result = eng.sandbox(folder, ["/usr/bin/python3", "/work/probe.py"])
    assert result["returncode"] == 0 and '"isolated": true' in result["stdout"], result
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", action="store_true")
    args = parser.parse_args()
    config, archive = check_freeze()
    checks = unit_checks(archive)
    pi = pi_checks(archive, config)
    recorder = subprocess.run(["node", str(ROOT / "recorder_fixture.mjs")], capture_output=True, text=True, encoding="utf-8", timeout=60)
    if recorder.returncode:
        raise RuntimeError(recorder.stderr)
    recorder_check = json.loads(recorder.stdout.strip())
    assert recorder_check["passed"]
    result = dict(passed=True, new_paid_model_calls=0, checks=checks, pi=pi,
                  recorder=recorder_check, sandbox_checked=args.sandbox, freeze_hash=sha(ROOT / "records/freeze.json"))
    if args.sandbox:
        result["sandbox"] = sandbox_checks()
    check_freeze()
    save(ROOT / "records/fixtures.json", result)
    print(json.dumps(result))
