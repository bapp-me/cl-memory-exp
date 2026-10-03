"""Offline acceptance of the bounded study. Never loads credentials or calls providers."""
from datetime import datetime
import subprocess

from common_opt import *
from round_runner import check, folder, prepare, execute
from audit_round import audit_task
from review_glm import call
import run_native


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def main():
    protocol = read(ROOT / "records/protocol.json")
    budget = read(ROOT / "records/round-budget.json")
    assert protocol["plan_revision"] == PLAN_REVISION
    assert sha(ROOT / "records/v1.5-section7.md") == protocol["plan_section_sha256"]
    assert budget["closed"] and budget["actual_solver_tasks"] == 144
    assert len(budget["rounds"]) == 3 and all(r["status"] == "completed" for r in budget["rounds"])
    manifest = read(ROOT / "records/review-manifest-initial.json")
    assert len(manifest["cases"]) == 240
    for path, expected in manifest["source_files"].items():
        assert sha(REPO / path) == expected, path
    for phase, expected in (("initial", 240), ("r1", 12), ("r2", 12), ("r3", 0)):
        cases = read(ROOT / "records" / f"review-manifest-{phase}.json")["cases"]
        assert len(cases) == expected
        if phase.startswith("r"):
            assert len({r["index"] for r in cases}) <= 12
        for case in cases:
            assert sha(ROOT / case["packet"]) == case["packet_sha256"]
    extraction = read(ROOT / "records/raw-field-extraction.json")
    assert extraction["summary"]["initial"]["all_4_original_semantic_fields_present"] == 240
    for row in extraction["rows"]:
        path = ROOT / row["source_file"]
        assert sha(path) == row["source_sha256"]
        raw = path.read_text(encoding="utf-8")
        for field in row["fields"].values():
            if field.get("value") is not None:
                assert raw[field["raw_char_start"]:field["raw_char_end"]] == field["value"]
    eng, _ = run_native.engine()  # Pure imports; do not load secret or launch broker.
    rounds, starts, finishes = {}, {}, []
    for rid in ("r1", "r2", "r3"):
        config, corpus = check(rid)
        decision = read(ROOT / "rounds" / rid / "analysis.json")
        stored = {r["index"]: r for r in decision["rows"]}
        namespace = folder(rid, 48).parent
        assert len(list(namespace.glob("*/commit.json"))) == 48
        assert not list(namespace.rglob("legal-episode.json"))
        rows, attempt_count, first = [], 0, float("inf")
        for index in range(48, 96):
            result = audit_task(folder(rid, index), corpus, config)
            assert result["terminal_state"] == "completed" and result["audit_passed"]
            for key in result:
                assert result[key] == stored[index][key], (rid, index, key)
            for request in read(folder(rid, index) / "call-ledger.json"):
                for attempt in request["http_attempts"]:
                    attempt_count += 1
                    assert attempt["http_attempt"] == 1 and attempt["status"] == 200
                    assert eng.normalized_usage(attempt["raw_usage"]) is not None
                    first = min(first, stamp(attempt["started_at"]))
                    finishes.append(stamp(attempt["finished_at"]))
            rows.append(result)
        starts[rid] = first
        relative = (ROOT / "rounds" / rid / "hypothesis.json").relative_to(REPO).as_posix()
        commit = subprocess.check_output(["git", "log", "--diff-filter=A", "--format=%H %ct", "--", relative], cwd=REPO, text=True).strip().split()
        assert len(commit) == 2 and int(commit[1]) < first
        assert attempt_count == decision["logical_calls"]
        rounds[rid] = dict(tasks=len(rows), http_attempts=attempt_count,
            tokens=sum(r["known_usage_subtotal"]["totalTokens"] for r in rows),
            hypotheses_committed_before_execution=commit[0], result=decision["result"],
            all_source_and_payload_audits=True, unknown_usage_attempts=0)
    equal = []
    for index in range(48, 96):
        paths = [next((folder(rid, index) / "payloads").glob("*.call-1.http-1.json")) for rid in ("r1", "r3")]
        assert read(paths[0]) == read(paths[1]), index
        equal.append(dict(index=index, r1_sha256=sha(paths[0]), r3_sha256=sha(paths[1]), parsed_payload_equal=True))
    reviewers = [read(p) for p in (ROOT / "api").rglob("terminal.json")]
    assert len(reviewers) == 269 and sum(r.get("usage") is not None for r in reviewers) == 264
    for request_path in (ROOT / "api").rglob("request.json"):
        request = read(request_path)
        assert request["model"] == "glm-5.3-flash" and request["reasoning_effort"] == "high"
        assert request["thinking"] == {"type": "enabled"}
    assert sum(r.get("http_status") == 429 for r in reviewers) == 5
    assert max(stamp(r["finished_at_utc"]) for r in reviewers) < starts["r3"]
    assert not (ROOT / "api/r3").exists()
    assert max(finishes) <= stamp(budget["closed_at_utc"])
    for attempt in (lambda: prepare("r4"), lambda: execute("r3", "canary"),
                    lambda: call({}, "unused", "r3"), lambda: call({}, "unused", "initial")):
        try:
            attempt()
        except RuntimeError as error:
            assert "closed" in str(error) or "Final-round stop" in str(error)
        else:
            raise AssertionError("Paid entry point did not reject closed study")
    review_tokens = sum(r["usage"]["total_tokens"] for r in reviewers if r.get("usage") is not None)
    solver_tokens = sum(r["tokens"] for r in rounds.values())
    result = dict(passed=True, model_calls_during_audit=0,
        old_plan_section_hash_verified=True, original_source_files_unchanged=len(manifest["source_files"]),
        original_review_packets=240, original_semantic_four_fields_raw_coverage=240,
        all_review_requests_glm53flash_high=True,
        no_invented_citations=True, rounds=rounds, total_solver_tasks=144,
        r1_r3_all48_first_provider_payloads_equal=equal,
        review_http_attempts=len(reviewers), review_model_responses=264, review_unknown_usage_attempts=5,
        known_solver_tokens=solver_tokens, known_review_tokens=review_tokens,
        known_new_study_tokens=solver_tokens + review_tokens, money=None,
        all_review_calls_ended_before_round3=True, study_closed=True,
        no_round4=True, paid_entry_points_reject_before_credentials=True,
        caveat="Citation checks and AI adjudication are not human semantic truth; two compact observations are not statistical noninferiority or unseen generalization.")
    save(ROOT / "records/completion-audit.json", result)
    print(json.dumps({k:v for k,v in result.items() if k not in ("r1_r3_all48_first_provider_payloads_equal", "rounds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
