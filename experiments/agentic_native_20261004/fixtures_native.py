"""Mock provider + real file tools and read-only shell isolation. No paid requests."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import uuid

from native_memory import ROOT, METHODS, NativeSession, digest
from run_native import check, engine, run_folder, shell_call, save, sha
from audit_native import audit_task


def tool_checks(corpus):
    session = NativeSession(corpus, "native_files")
    session.task(ROOT / ".runtime/fixtures", dict(task_id="fixture"))
    session.out.mkdir(parents=True, exist_ok=True)
    glob = session.call("MEMORY_GLOB", dict(pattern="episodes/*.md", limit=100), "glob")
    assert len(glob["paths"]) == 48
    search = session.call("MEMORY_GREP", dict(pattern="np.random", literal=True, glob="episodes/*.md", context=1, limit=20), "grep")
    assert search["items"]
    bad = session.call("MEMORY_GREP", dict(pattern="["), "invalid_regex")
    assert bad.get("error")
    bad_path = session.call("MEMORY_READ_FILE", dict(path="/memory/../../secret"), "bad_path")
    assert bad_path.get("error")
    missing = session.call("MEMORY_READ_FILE", dict(path="episodes/s048.md"), "complex")
    assert missing.get("error")
    empty = session.call("MEMORY_GREP", dict(pattern="XYQ_NOT_IN_THIS_ARCHIVE_777", literal=True), "missing")
    assert not empty["items"] and empty["total_matches"] == 0
    read = session.call("MEMORY_READ_FILE", dict(path="episodes/s000.md", start_line=1, line_count=400), "read")
    assert read["items"]
    # Low remaining budget and long raw lines remain bounded and resumable.
    session.used_bytes = 46900
    limited = session.call("MEMORY_READ_FILE", dict(path="raw/s000.json", line_count=400), "bounded")
    assert len(json.dumps(limited, ensure_ascii=False, separators=(",", ":")).encode()) <= 1100
    assert session.used_bytes <= 48000
    def independent(i):
        s = NativeSession(corpus, "native_files")
        r = s.call("MEMORY_READ_FILE", dict(path="MEMORY.md", line_count=2), str(i))
        assert s.calls == 1 and r["items"]
        assert digest(s.update(dict(text="COMPLEX_CANARY"))) == corpus.archive.library_hash
        return True
    with ThreadPoolExecutor(max_workers=48) as pool:
        assert all(pool.map(independent, range(96)))
    shell = shell_call("printf WRITE_DENIED_CHECK; if printf BAD >> /memory/MEMORY.md 2>/dev/null; then exit 91; fi; "
                       "test ! -e /mnt/d/campus_re; test ! -e /home/fucak; test ! -e /proc; "
                       "test -z \"$EXPERIMENT_API_KEY\"; rg -n 'np.random' episodes/s000.md | head -3; "
                       "echo NATIVE_ISOLATION_OK", dict(task_id="fixture"), 0)
    assert shell["returncode"] == 0 and "NATIVE_ISOLATION_OK" in shell["stdout"]
    assert "/memory/episodes/s000.md" in shell["opened_memory_files"]
    assert shell["trace_present"]
    denied = shell_call("rg 'COMPLEX_CANARY' /memory; test ! -e /audit; "
                       "if timeout 2 bash -c 'echo x >/dev/tcp/1.1.1.1/443'; then exit 92; fi; echo NETWORK_ISOLATED", dict(task_id="fixture"), 1)
    assert denied["returncode"] == 0 and "NETWORK_ISOLATED" in denied["stdout"]
    corpus.verify()
    return dict(passed=True, checks=["48 files", "regex/context/search", "invalid regex", "path scope",
        "complex ID rejected", "empty search", "bounded read", "96 independent sessions", "writeback discarded",
        "OS read-only archive", "host/other-task/credential/proc isolation", "network isolation", "strace source opens"],
        shell_probes=[shell, denied])


def mock_checks(corpus, config):
    captures = []
    class Mock(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captures.append(payload)
            shell = any(t["function"]["name"] == "MEMORY_SHELL" for t in payload["tools"])
            steps = [("MEMORY_SHELL", dict(command="rg -n 'normal distribution' MEMORY.md")),
                     ("MEMORY_SHELL", dict(command="sed -n '1,80p' episodes/s000.md"))] if shell else [
                     ("MEMORY_GLOB", dict(pattern="episodes/*.md", limit=3)),
                     ("MEMORY_GREP", dict(pattern="normal distribution", glob="MEMORY.md", ignore_case=True)),
                     ("MEMORY_READ_FILE", dict(path="episodes/s000.md", start_line=1, line_count=40))]
            steps += [("PYTHON", dict(code="print(42)")), ("SUBMIT", dict(code="def task_func():\n    return 42\n"))]
            step = sum(m["role"] == "tool" for m in payload["messages"])
            name, args = steps[step]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            frames = [dict(id="mock-native", model="glm-5.3-flash", choices=[dict(index=0,
                delta=dict(role="assistant", tool_calls=[dict(index=0, id=f"fixture_{step}", type="function",
                    function=dict(name=name, arguments=json.dumps(args)))]), finish_reason=None)]),
                dict(choices=[dict(index=0, delta={}, finish_reason="tool_calls")]),
                dict(choices=[], usage=dict(prompt_tokens=100, completion_tokens=10, total_tokens=110))]
            for frame in frames:
                self.wfile.write(("data: " + json.dumps(frame) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    eng, _ = engine()
    eng.sandbox = lambda *a, **k: dict(returncode=0, stdout="42\n", stderr="")
    eng.grade_code = lambda row, code: dict(correct=code == "def task_func():\n    return 42\n", scorable=True, tests_run=1, checks_executed=1)
    fixture = json.loads(json.dumps(config))
    fixture["model"]["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
    prefix = "native-fixture-" + uuid.uuid4().hex
    results = []
    try:
        for method in METHODS:
            row = dict(category="fixture", id="fixture", problem="Submit task_func returning 42. Interface fixture only.")
            eng.run_task(fixture, method, "codeeval", 999, row, corpus.archive.snapshot(), "fixture-not-secret",
                         run_prefix=prefix, adapter=NativeSession(corpus, method, shell_call))
            result = audit_task(run_folder(method, 999, prefix), corpus, fixture)
            assert result["correct"] is True and result["unknown_usage_http_attempts"] == 0
            assert result["maximum_visible_memory_results"] >= 2
            results.append(dict(method=method, passed=True, calls=result["calls"],
                                folder=str(run_folder(method, 999, prefix))))
    finally:
        server.shutdown()
        server.server_close()
    return dict(passed=True, methods=results, mock_requests=len(captures), paid_model_calls=0)


if __name__ == "__main__":
    config, corpus = check()
    checks = tool_checks(corpus)
    mock = mock_checks(corpus, config)
    check()
    result = dict(passed=True, paid_model_calls=0, tools=checks, pi=mock, freeze_hash=sha(ROOT / "records/freeze.json"))
    save(ROOT / "records/fixtures.json", result)
    print(json.dumps(dict(passed=True, mock_requests=mock["mock_requests"], paid_model_calls=0)))
