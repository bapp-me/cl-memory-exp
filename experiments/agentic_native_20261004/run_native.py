"""Two additional source-frozen native memory modes, authorized directly by user steering."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from urllib.request import Request, urlopen
import uuid

from native_memory import ROOT, BASE, METHODS, Corpus, NativeSession, Archive, digest
import run as base

REPO, OBS = base.REPO, base.OBS
PREFIX = "native-memory-20261004-v1"
SLOTS = threading.BoundedSemaphore(8)
LOCK = threading.Lock()
read, save, sha = base.read, base.save, base.sha


def timed_slot(kind, work, function):
    queued = time.perf_counter()
    with SLOTS:
        entered = time.perf_counter()
        try:
            return function()
        finally:
            with LOCK:
                path = ROOT / ".runtime/sandbox-spans.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(dict(kind=kind, work=str(work), queue_seconds=entered - queued,
                        execution_seconds=time.perf_counter() - entered, cap=8)) + "\n")


def shell_call(command, identity, ordinal):
    broker = read(ROOT / ".runtime/shell-broker.json")
    ticket = uuid.uuid4().hex
    def execute():
        request = Request(broker["url"], data=json.dumps(dict(ticket=ticket, command=command)).encode(),
                          headers={"Content-Type": "application/json", "X-Broker-Token": broker["token"]})
        with urlopen(request, timeout=50) as response:
            result = json.load(response)
        if not result["trace_present"]:
            raise RuntimeError("Native shell trace missing")
        result.update(identity=identity, memory_call_ordinal=ordinal)
        return result
    return timed_slot("memory_shell", ticket, execute)


def engine():
    # Reuse the exact solver/recorder/evaluator of the three-mode experiment.
    eng, _ = base.engine()
    path = OBS / "engine.py"
    source = path.read_text(encoding="utf-8")
    old_system = "'system': getattr(task, 'system_hint', 'Complete the current task using the declared tools. Submit once.') +\n" \
                 "                     ' Previous episodes below are your own fallible observations, not verified answers. Use only relevant experience.\\n' + json.dumps(selected, ensure_ascii=False),"
    replacements = [
        ("    selected, retrieval = adapter.retrieve(prompt) if adapter else retrieval_record(history, method, prompt)",
         "    tools = [*tools, *adapter.tools]\n    selected, retrieval = adapter.retrieve(prompt)"),
        ("                value = task.tool(data['name'], data['args'])",
         "                value = (adapter.call(data['name'], data['args'], data['tool_call_id']) if data['name'].startswith('MEMORY_') else task.tool(data['name'], data['args']))"),
        (old_system, "'system': adapter.system(),"),
        ("'memory_blocks': memory_blocks(selected)", "'memory_blocks': adapter.blocks()"),
        ("str(ROOT / 'pi_runner_v2.mjs')", "str(AGENTIC_ROOT / 'pi_runner.mjs')"),
        ("    save(out / 'legal-episode.json', episode)", "    # Target history is audit-only and is never a searchable episode."),
    ]
    for old, new in replacements:
        assert source.count(old) == 1
        source = source.replace(old, new)
    exec(compile(source, str(path) + "[native-memory-overlay]", "exec"), eng.__dict__)
    actual_sandbox = eng.sandbox
    eng.sandbox = lambda work, command, timeout=120: timed_slot("business_or_grading", work,
                         lambda: actual_sandbox(work, command, timeout))
    return eng, hashlib.sha256(source.encode()).hexdigest()


def run_folder(method, index, prefix=PREFIX):
    return OBS / ".runtime/runs" / f"{prefix}-codeeval-{method}" / f"{index:03d}"


def prepare():
    original_config, archive = base.check_freeze()
    corpus = Corpus(archive)
    corpus.materialize()
    _, overlay_hash = engine()
    config = dict(config_id=PREFIX, methods=list(METHODS), status="authorized_by_user_steering",
        model=original_config["model"], budgets=original_config["budgets"],
        task_count=96, tasks_per_method=48, target_indices=list(range(48, 96)), repetitions=1,
        max_parallel_tasks=48, max_parallel_sandboxes=8, max_memory_calls=12,
        per_result_byte_cap=12000, total_memory_bytes_including_startup=48000,
        transport_extra_retries=2, performance_retry=False, new_writer_calls=0, embedding_calls=0,
        library_hash=archive.library_hash, corpus_hash=corpus.hash, source_episodes=48,
        startup_bytes={m: len(NativeSession(corpus, m).prelude().encode()) for m in METHODS},
        startup_policy=dict(native_files="Full 52-line extractive MEMORY.md index, below 200 lines / 25KB",
                            native_shell="Small memory_summary.md locator; registry and histories read on demand"),
        shell=dict(readonly_mount="/memory", timeout_seconds=30, private_scratch="/work", network=False,
                   file_open_audit="strace outside agent chroot", extra_reasoning_calls=0),
        scoring="Existing 48 executions / 46 eligible tasks; 316 and historical 954 caveats retained",
        initial_canary=dict(index=48, methods=list(METHODS), included_in_96=True),
        source_construction="Deterministic formatting and extractive descriptions only; no target or scorer input",
        money=None, model_alias="variable alias; not fixed weights", overlay_sha256=overlay_hash,
        authorization="用户：你再从这个方面进行调研，额外设计2种模式吧，跑的时候不用跟我确认配置了")
    paths = [p for p in ROOT.glob("*.py")] + [ROOT / "sandbox.sh"]
    prior = read(BASE / "records/freeze.json")
    frozen = dict(config_hash=digest(config), corpus_hash=corpus.hash,
                  files={p.relative_to(REPO).as_posix(): sha(p) for p in paths},
                  inherited_files=prior["files"], inherited_sources=prior["source_inputs"], corpus_files=corpus.hashes)
    if (ROOT / "records/approval.json").exists():
        raise RuntimeError("Already frozen for paid execution")
    save(ROOT / "records/config.json", config)
    save(ROOT / "records/freeze.json", frozen)
    save(ROOT / "records/corpus-provenance.json", dict(files=corpus.hashes, line_ranges=corpus.provenance,
         original_library_hash=archive.library_hash, new_model_calls=0))
    print(json.dumps(dict(prepared=True, corpus_files=len(corpus.files), startup_bytes=config["startup_bytes"],
                          config_hash=digest(config), new_model_calls=0)))


def check():
    config, frozen = read(ROOT / "records/config.json"), read(ROOT / "records/freeze.json")
    assert digest(config) == frozen["config_hash"]
    for relative, expected in {**frozen["files"], **frozen["inherited_files"], **frozen["inherited_sources"]}.items():
        assert sha(REPO / relative) == expected, relative
    corpus = Corpus(Archive(read(base.SOURCE)))
    corpus.verify()
    assert corpus.hash == config["corpus_hash"] == frozen["corpus_hash"]
    return config, corpus


def run(stage):
    from audit_native import audit_task
    config, corpus = check()
    acceptance = read(ROOT / "records/fixtures.json")
    assert acceptance["passed"] and acceptance["freeze_hash"] == sha(ROOT / "records/freeze.json")
    approval = read(ROOT / "records/approval.json")
    assert approval["approved"] and approval["config_hash"] == digest(config)
    eng, overlay_hash = engine()
    assert overlay_hash == config["overlay_sha256"]
    key = eng.secret()
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    if stage == "remaining":
        for method in METHODS:
            result = audit_task(run_folder(method, 48), corpus, config)
            assert result["terminal_state"] == "completed" and not result["unknown_usage_http_attempts"]
    def one(method, index):
        session = NativeSession(corpus, method, shell_call)
        after, _ = eng.run_task(config, method, "codeeval", index, assets[index], session.snapshot(), key,
                               run_prefix=PREFIX, adapter=session)
        assert digest(after) == corpus.archive.library_hash
        return audit_task(run_folder(method, index), corpus, config)
    jobs = iter((m, i) for i in ([48] if stage == "canary" else range(49, 96)) for m in METHODS)
    active, completed, errors = {}, [], []
    workers = 2 if stage == "canary" else 48
    with ThreadPoolExecutor(max_workers=workers) as pool:
        def dispatch():
            try:
                method, index = next(jobs)
            except StopIteration:
                return False
            active[pool.submit(one, method, index)] = (method, index)
            return True
        for _ in range(workers):
            dispatch()
        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                method, index = active.pop(future)
                try:
                    result = future.result()
                    completed.append(result)
                    if result["terminal_state"] != "completed" or result["unknown_usage_http_attempts"]:
                        errors.append(dict(method=method, index=index, status=result["terminal_state"], unknown_usage=result["unknown_usage_http_attempts"]))
                except Exception as error:
                    errors.append(dict(method=method, index=index, error=type(error).__name__ + ": " + str(error)))
            if not errors:
                while len(active) < workers and dispatch():
                    pass
            save(ROOT / "records" / f"progress-{stage}.json", dict(committed=len(completed), errors=errors,
                stopped_dispatch=bool(errors), results=completed))
    check()
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "check", "canary", "remaining"])
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    elif args.mode == "check":
        check()
        print("Native config/corpus frozen checks passed; no model call.")
    else:
        run(args.mode)
