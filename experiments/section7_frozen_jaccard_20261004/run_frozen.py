"""Authorized R=1 Jaccard top-3 replay from immutable No Memory source episodes."""
from __future__ import annotations
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import copy
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import types

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OBS = REPO / "experiments/section7_observability_20261002"
PREFLIGHT = REPO / "experiments/section7_common_source_20261003"
PREFIX = "section7-frozen-source-20261004-v2"
RUN_ID = PREFIX + "-codeeval-episodic_retrieval"
RUNS = OBS / ".runtime/runs" / RUN_ID
METHOD = "episodic_retrieval"
SANDBOX_SLOTS = threading.BoundedSemaphore(8)
SANDBOX_LOG_LOCK = threading.Lock()
PATCHES = [
    (" Previous episodes below are your own fallible observations, not verified answers. Use only relevant experience.\\n",
     " Previous episodes below are archived fallible observations from independent No Memory source tasks, not verified answers. Use only relevant experience.\\n"),
    ("    save(out / 'legal-episode.json', episode)",
     "    # Frozen source replay: do not persist the complex-task episode as a memory artifact."),
]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def engine():
    """Use the frozen v2 engine without editing any historical source files."""
    path = OBS / "engine.py"
    source = path.read_text(encoding="utf-8")
    for old, new in PATCHES:
        assert source.count(old) == 1
        source = source.replace(old, new)
    module = types.ModuleType("frozen_jaccard_engine")
    module.__file__ = str(path)
    exec(compile(source, str(path) + "[frozen-source-overlay]", "exec"), module.__dict__)
    native_sandbox = module.sandbox

    def limited_sandbox(work, command, timeout=120):
        queued = time.monotonic()
        with SANDBOX_SLOTS:
            entered = time.monotonic()
            try:
                return native_sandbox(work, command, timeout)
            finally:
                span = {"work": str(work), "queue_seconds": entered - queued,
                        "execution_seconds": time.monotonic() - entered, "limit": 8}
                with SANDBOX_LOG_LOCK:
                    directory = ROOT / ".runtime"
                    directory.mkdir(parents=True, exist_ok=True)
                    with (directory / "sandbox-spans.jsonl").open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(span) + "\n")

    module.sandbox = limited_sandbox
    return module, hashlib.sha256(source.encode()).hexdigest()


class FrozenSource:
    def __init__(self, eng, library):
        self.eng = eng
        self.serialized = json.dumps(library, ensure_ascii=False)
        self.expected_hash = eng.digest(library)
        self.state = {"episode_count": 48}
        self.out = None
        self.identity = None

    def snapshot(self):
        return json.loads(self.serialized)

    def task(self, out, identity):
        self.out, self.identity = out, identity

    def retrieve(self, prompt):
        selected, retrieval = self.eng.retrieval_record(self.snapshot(), METHOD, prompt)
        assert all(0 <= candidate["history_index"] < 48 for candidate in retrieval["observable_candidates"])
        return selected, retrieval

    def update(self, _discarded_complex_episode):
        # The argument is not retained, serialized, appended, or indexed.
        before = self.snapshot()
        self.eng.record_memory_change(self.out, before, self.snapshot(), "noop", [],
                                      reason="Frozen simple-source library; complex-task writeback prohibited", readonly=True)
        return self.snapshot()

    def restore_checkpoint(self, _out, state):
        assert self.eng.digest(state) == self.expected_hash


def prepare():
    eng, overlay_hash = engine()
    prior = read(PREFLIGHT / "records/preflight.json")
    for relative, expected in prior["input_hashes"].items():
        assert sha(REPO / relative) == expected, relative
    sys.path.insert(0, str(PREFLIGHT))
    import preflight
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    library = [preflight.episode("no_memory", i, assets[i]["problem"]) for i in range(48)]
    assert len(json.dumps(library, ensure_ascii=False).encode()) == 241220
    assert all(set(entry) == {"sequence", "text"} for entry in library)
    for entry in library:
        assert set(json.loads(entry["text"])) == {"task", "trajectory"}
    common = read(OBS / "records/confirmed-config-v1.json")
    config = {
        "config_id": PREFIX, "run_id": RUN_ID, "status": "user_authorized",
        "user_instruction": "只跑一个Jaccard 原样 top-3；以简单题库记忆为起点；复杂题轨迹不保存进记忆，agent始终只能读简单题库",
        "date_hong_kong": "2026-10-04", "method": METHOD, "benchmark": "codeeval",
        "source": "existing No Memory raw-task legal episodes, all 48, no hidden-score filtering",
        "ordered_target_indices": list(range(48, 96)),
        "ordered_target_ids": [row["category"] + ":" + row["id"] for row in assets[48:]],
        "source_library_hash": eng.digest(library), "source_library_bytes": 241220,
        "memory_policy": "immutable simple library; no complex episode persistence/indexing/writeback",
        "retrieval": "original lowercase word-set Jaccard on prompt and full episode.text; top-3; newer tie break; chronological injection; 48000 UTF-8 byte FIFO cap",
        "model": common["model"], "budgets": common["budgets"]["code"],
        "repetitions": 1, "target_tasks": 48, "writer_calls": 0,
        "performance_retry": False, "transport_extra_retries": 2,
        "max_parallel_tasks": 48, "initial_task_gate": 48,
        "api_concurrency_ceiling": 48, "historical_user_api_concurrency_ceiling": 50,
        "max_parallel_sandboxes": 8,
        "concurrency_amendment": "User explicitly requested high concurrency before any model execution; v1 eight-task preparation superseded. Semaphore applies before broker requests and queue time is recorded.",
        "token_or_money_hard_limit": None,
        "budget_basis": "User authorized the single 48-target branch with existing per-task limits; no extra arms/repeats. Money unknown without verified pricing/invoice.",
        "audit_policy": "Retain sanitized requests, responses, tools and scoring outside all agent sandboxes/retrieval; no legal-episode.json for complex tasks",
        "scoring": "unchanged original mask: execute 48, score 46; 316 scoring-shadow caveat separate",
        "historical_source_tokens": 137698,
        "engine_overlay": [{"old": old, "new": new} for old, new in PATCHES],
        "overlay_sha256": overlay_hash,
        "stop": "After initial gate, stop dispatching on infrastructure/memory/evaluator failure or unknown usage; retain in-flight results, no task regeneration",
    }
    paths = [Path(__file__), OBS / "engine.py", OBS / "pi_runner_v2.mjs", OBS / "recorder_v2.mjs",
             OBS / "broker.py", OBS / ".runtime/sandbox.sh", OBS / "records/scorer-issues.json",
             PREFLIGHT / "preflight.py", REPO / "experiments/agent_memory_plan_20261002/core.py"]
    freeze = {"config_hash": eng.digest(config), "source_hash": eng.digest(library),
              "files": {path.relative_to(REPO).as_posix(): sha(path) for path in paths},
              "preflight_input_hashes": prior["input_hashes"]}
    for path, value in [(ROOT / "records/config.json", config), (ROOT / "records/simple-library.json", library),
                        (ROOT / "records/freeze.json", freeze)]:
        if path.exists():
            assert read(path) == value, f"Refuse to alter prepared experiment: {path}"
        else:
            save(path, value)
    manifest = []
    for index in range(48, 96):
        selected, retrieval = FrozenSource(eng, library).retrieve(assets[index]["problem"])
        old = next(row for row in prior["target_selections"]["jaccard_full_episode_top3"] if row["target_index"] == index)
        assert [entry["sequence"] for entry in selected] == old["selected_indices"]
        assert len(selected) == 3 and retrieval["injected_utf8_bytes"] <= 48000
        manifest.append({"index": index, "task_id": config["ordered_target_ids"][index-48],
                         "source_indices": [entry["sequence"] for entry in selected],
                         "injected_hash": eng.digest(selected), "retrieval": retrieval})
    save(ROOT / "records/injection-manifest.json", manifest)
    check_freeze()
    print(json.dumps({"prepared": True, "targets": 48, "library_episodes": 48,
                      "source_library_hash": eng.digest(library), "new_model_calls": 0}))


def check_freeze():
    eng, overlay_hash = engine()
    config, library, frozen = [read(ROOT / "records" / name) for name in ("config.json", "simple-library.json", "freeze.json")]
    assert eng.digest(config) == frozen["config_hash"]
    assert eng.digest(library) == frozen["source_hash"] == config["source_library_hash"]
    assert overlay_hash == config["overlay_sha256"]
    for relative, expected in {**frozen["files"], **frozen["preflight_input_hashes"]}.items():
        assert sha(REPO / relative) == expected, relative
    return eng, config, library


def fixtures(with_sandbox=False):
    eng, config, library = check_freeze()
    fixture = ROOT / ".runtime/fixtures"
    fixture.mkdir(parents=True, exist_ok=True)
    adapter = FrozenSource(eng, library)
    adapter.task(fixture, {"attempt_id": "model-free-fixture"})
    original = adapter.snapshot()
    disposable = adapter.snapshot()
    disposable.append({"sequence": 48, "text": "COMPLEX_CANARY_MUST_NOT_ENTER_MEMORY"})
    assert adapter.snapshot() == original
    assert adapter.update(disposable[-1]) == original
    assert adapter.state["episode_count"] == 48
    selected, retrieval = adapter.retrieve("COMPLEX_CANARY_MUST_NOT_ENTER_MEMORY")
    assert len(retrieval["observable_candidates"]) == 48
    assert all(entry in library for entry in selected)
    rejected = False
    try:
        adapter.restore_checkpoint(fixture, disposable)
    except AssertionError:
        rejected = True
    assert rejected
    result = {"passed": True, "model_calls": 0, "immutable_copy": True, "writeback_discarded": True,
              "complex_candidate_absent": True, "mutated_checkpoint_rejected": True,
              "all_48_retrievals_match_original": True, "sandbox_checked": False}
    if with_sandbox:
        probe = OBS / ".runtime/sandbox-canary/frozen-jaccard-20261004"
        probe.mkdir(parents=True, exist_ok=True)
        code = """import json,os,socket
import numpy,pandas,scipy,matplotlib,sklearn
assert not os.path.exists('/mnt/d/campus_re')
assert not os.path.exists('/home/fucak')
assert not os.getenv('EXPERIMENT_API_KEY')
s=socket.socket();s.settimeout(1)
try:
    s.connect(('1.1.1.1',443))
    raise AssertionError('sandbox network unexpectedly available')
except OSError:
    pass
print(json.dumps({'isolated':True,'deps':True}))
"""
        (probe / "probe.py").write_text(code, encoding="utf-8")
        sandbox = eng.sandbox(probe, ["/usr/bin/python3", "/work/probe.py"])
        assert sandbox["returncode"] == 0, sandbox
        assert json.loads(sandbox["stdout"].strip())["isolated"] is True
        result.update(sandbox_checked=True, sandbox=sandbox)
    save(ROOT / "records/fixtures.json", result)
    print(json.dumps(result))


def verify_task(index, eng, library):
    folder = RUNS / f"{index:03d}"
    commit = read(folder / "commit.json")
    before, after = [read(folder / name) for name in ("memory-before.json", "memory-after.json")]
    assert before == after == library
    assert commit["before_hash"] == commit["after_hash"] == eng.digest(library)
    assert not (folder / "legal-episode.json").exists()
    expected = next(row for row in read(ROOT / "records/injection-manifest.json") if row["index"] == index)
    assert eng.digest(read(folder / "injected.json")) == expected["injected_hash"]
    assert read(folder / "retrieval.json") == expected["retrieval"]
    requests = [json.loads(line) for line in (folder / "requests.jsonl").read_text(encoding="utf-8").splitlines()]
    assert requests and all(request["all_injected_blocks_mapped"] for request in requests)
    initial = read(folder / "input-public.json")
    expected_system = 'Complete the current task using the declared tools. Submit once.' + PATCHES[0][1].replace('\\n', '\n') + json.dumps(read(folder / "injected.json"), ensure_ascii=False)
    assert initial["system"] == expected_system
    for request in requests:
        payload = read(folder / request["artifact"])
        assert payload["model"] == "glm-5.3-flash"
        messages = payload["messages"]
        assert messages[0]["role"] == "system" and messages[0]["content"] == expected_system
        assert messages[1]["role"] == "user" and messages[1]["content"] == initial["prompt"]
    return commit["result"]


def run(stage):
    eng, config, library = check_freeze()
    fixture = read(ROOT / "records/fixtures.json")
    assert fixture["passed"] and fixture["sandbox_checked"]
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    selected_indices = [48] if stage == "first" else list(range(49, 96))
    if stage == "remaining":
        first = verify_task(48, eng, library)
        assert first["terminal_state"] == "completed" and first["unknown_usage_http_attempts"] == 0
    RUNS.mkdir(parents=True, exist_ok=True)
    save(RUNS / "manifest.json", config)
    api_key = eng.secret()

    def one(index):
        check_freeze()
        adapter = FrozenSource(eng, library)
        after, record = eng.run_task(config, METHOD, "codeeval", index, assets[index], adapter.snapshot(),
                                     api_key, run_prefix=PREFIX, adapter=adapter)
        assert after == library
        return verify_task(index, eng, library)

    completed = [verify_task(index, eng, library) for index in range(48, 96) if (RUNS / f"{index:03d}/commit.json").exists()]
    pending = iter(index for index in selected_indices if not (RUNS / f"{index:03d}/commit.json").exists())
    errors = []
    stopped = False
    workers = 1 if stage == "first" else config["max_parallel_tasks"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        active = {}

        def dispatch():
            for index in pending:
                active[pool.submit(one, index)] = index
                return True
            return False

        for _ in range(workers):
            if not dispatch():
                break
        while active:
            finished, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in finished:
                index = active.pop(future)
                try:
                    record = future.result()
                    completed.append(record)
                    if record["terminal_state"] != "completed" or record["unknown_usage_http_attempts"]:
                        stopped = True
                        errors.append({"index": index, "terminal_state": record["terminal_state"], "unknown_usage": record["unknown_usage_http_attempts"]})
                except Exception as error:
                    stopped = True
                    errors.append({"index": index, "error": type(error).__name__ + ": " + str(error)})
            if not stopped:
                while len(active) < workers and dispatch():
                    pass
            progress = {"stage": stage, "planned": 48, "committed": len(completed), "stopped_dispatch": stopped,
                        "errors": errors, "known_tokens": sum(row["known_usage_subtotal"]["totalTokens"] for row in completed),
                        "results": sorted(completed, key=lambda row: row["task_id"])}
            save(ROOT / "records/progress.json", progress)
    check_freeze()
    print(json.dumps({"stage": stage, "committed": len(completed), "stopped": stopped, "errors": errors}))
    if stopped:
        raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "fixtures", "first", "remaining"])
    parser.add_argument("--sandbox", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    elif args.mode == "fixtures":
        fixtures(args.sandbox)
    else:
        run(args.mode)
