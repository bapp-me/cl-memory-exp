"""Hard ceiling: at most three registered 48-task validation rounds, no task retries."""
import argparse
import importlib.util
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from common_opt import *
import run_native as native
from audit_round import audit_task


def folder(round_id, index):
    return native.run_folder("native_files", index, "agentic-opt-20261004-" + round_id)


def candidate_module(round_id):
    path = ROOT / "rounds" / round_id / "code/candidate_memory.py"
    spec = importlib.util.spec_from_file_location("candidate_" + round_id, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(round_id):
    assert_study_open()
    if round_id not in ("r1", "r2", "r3"):
        raise ValueError("Maximum three full validation rounds; round 4 is prohibited")
    hypothesis = read(ROOT / "rounds" / round_id / "hypothesis.json")
    config, corpus = native.check()
    assert hypothesis["status"] == "registered_before_execution"
    ledger = read(ROOT / "records/round-budget.json")
    existing = next((r for r in ledger["rounds"] if r["round_id"] == round_id), None)
    if existing:
        raise RuntimeError("Round already prepared; do not reset state")
    assert len(ledger["rounds"]) < 3 and int(round_id[1:]) == len(ledger["rounds"]) + 1
    assert sum(r["allocated_tasks"] for r in ledger["rounds"]) + 48 <= 144
    current = dict(config)
    current.update(config_id="agentic-opt-20261004-" + round_id, task_count=48, methods=["native_files"],
        variant=hypothesis["variant"], round_id=round_id, target_indices=list(range(48, 96)),
        hypothesis_sha256=sha(ROOT / "rounds" / round_id / "hypothesis.json"),
        max_full_rounds=3, current_round=int(round_id[1:]), complex_writeback=False)
    from candidate_memory import CandidateSession
    candidate = CandidateSession(corpus, current["variant"])
    current["startup_bytes"] = {"native_files": len(candidate.prelude().encode())}
    current["startup_policy"] = {"native_files": hypothesis.get("startup_file", "MEMORY.md")}
    if hypothesis.get("confirmation_of"):
        current["confirmation_of"] = hypothesis["confirmation_of"]
    paths = [ROOT / p for p in ("candidate_memory.py", "round_runner.py", "audit_round.py", "fixtures_round.py", "common_opt.py")]
    snapshots = []
    for path in paths:
        copy = ROOT / "rounds" / round_id / "code" / path.name
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(path.read_bytes())
        snapshots.append(copy)
    frozen = dict(config_hash=digest(current), corpus_hash=corpus.hash,
                  files={p.relative_to(REPO).as_posix(): sha(p) for p in snapshots},
                  execution_sources={p.relative_to(REPO).as_posix(): sha(p) for p in paths},
                  hypothesis_sha256=current["hypothesis_sha256"])
    save(ROOT / "rounds" / round_id / "config.json", current)
    save(ROOT / "rounds" / round_id / "freeze.json", frozen)
    ledger["rounds"].append(dict(round_id=round_id, status="prepared", allocated_tasks=48,
                                 variant=current["variant"], config_hash=digest(current)))
    save(ROOT / "records/round-budget.json", ledger)
    print(json.dumps(dict(round=round_id, allocated_tasks=48, allocated_total=sum(r["allocated_tasks"] for r in ledger["rounds"]))))


def check(round_id, execution=False):
    if round_id not in ("r1", "r2", "r3"):
        raise ValueError("Round limit exceeded")
    config, freeze = [read(ROOT / "rounds" / round_id / name) for name in ("config.json", "freeze.json")]
    assert digest(config) == freeze["config_hash"]
    assert sha(ROOT / "rounds" / round_id / "hypothesis.json") == freeze["hypothesis_sha256"]
    for relative, expected in freeze["files"].items():
        assert sha(REPO / relative) == expected, relative
    if execution:
        for relative, expected in freeze["execution_sources"].items():
            assert sha(REPO / relative) == expected, relative
    _, corpus = native.check()
    assert corpus.hash == freeze["corpus_hash"]
    ledger = read(ROOT / "records/round-budget.json")
    assert len(ledger["rounds"]) <= 3 and sum(r["allocated_tasks"] for r in ledger["rounds"]) <= 144
    return config, corpus


def assert_study_open():
    if read(ROOT / "records/round-budget.json").get("closed"):
        raise RuntimeError("Study closed after three full rounds; offline audit only")


def execute(round_id, stage):
    assert_study_open()  # Before checking runtime dependencies or loading credentials.
    config, corpus = check(round_id, execution=True)
    fixture = read(ROOT / "rounds" / round_id / "fixtures.json")
    assert fixture["passed"] and fixture["freeze_hash"] == sha(ROOT / "rounds" / round_id / "freeze.json")
    ledger = read(ROOT / "records/round-budget.json")
    entry = next(r for r in ledger["rounds"] if r["round_id"] == round_id)
    assert entry["config_hash"] == digest(config)
    if stage == "remaining":
        canary = audit_task(folder(round_id, 48), corpus, config)
        assert canary["terminal_state"] == "completed" and not canary["unknown_usage_http_attempts"]
    entry["status"] = "running"
    save(ROOT / "records/round-budget.json", ledger)
    eng, _ = native.engine()
    key = eng.secret()
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    CandidateSession = candidate_module(round_id).CandidateSession
    def one(index):
        session = CandidateSession(corpus, config["variant"])
        after, _ = eng.run_task(config, "native_files", "codeeval", index, assets[index], session.snapshot(),
                               key, run_prefix="agentic-opt-20261004-" + round_id, adapter=session)
        assert digest(after) == corpus.archive.library_hash
        return audit_task(folder(round_id, index), corpus, config)
    jobs = iter([48] if stage == "canary" else range(49, 96))
    active, complete, errors = {}, [], []
    workers = 1 if stage == "canary" else 48
    with ThreadPoolExecutor(max_workers=workers) as pool:
        def dispatch():
            try:
                index = next(jobs)
            except StopIteration:
                return False
            active[pool.submit(one, index)] = index
            return True
        for _ in range(workers):
            dispatch()
        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                index = active.pop(future)
                try:
                    result = future.result()
                    complete.append(result)
                    if result["terminal_state"] != "completed" or result["unknown_usage_http_attempts"]:
                        errors.append(dict(index=index, status=result["terminal_state"], unknown_usage=result["unknown_usage_http_attempts"]))
                except Exception as error:
                    errors.append(dict(index=index, error=type(error).__name__ + ": " + str(error)))
            if not errors:
                while len(active) < workers and dispatch():
                    pass
            save(ROOT / "rounds" / round_id / f"progress-{stage}.json", dict(committed=len(complete), errors=errors, results=complete))
    check(round_id)
    if errors:
        raise SystemExit(2)
    if stage == "remaining":
        entry["status"] = "completed"
        save(ROOT / "records/round-budget.json", ledger)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("round_id")
    parser.add_argument("mode", choices=["prepare", "check", "canary", "remaining"])
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.round_id)
    elif args.mode == "check":
        check(args.round_id)
        print("Round freeze verified; no model calls.")
    else:
        execute(args.round_id, args.mode)
