"""GLM-only evidence reviews; immutable packets and preserved raw answers, no quality retries."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import argparse
import ast
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from common_opt import *

ENUMS = dict(source_quality={"pass_with_limits", "failed_or_partial", "unknown", "not_applicable"},
    memory_fidelity={"faithful", "partial", "contradicted", "absent", "unknown", "not_applicable"},
    target_applicability={"applicable", "partial", "irrelevant", "absent", "unknown", "not_applicable"},
    visible_use={"consistent_adaptation", "misapplication_candidate", "no_visible_use", "unknown", "not_applicable"})
AGENTIC_ENUMS = dict(search_strategy={"focused", "overbroad_candidate", "stopped_early_candidate", "no_search_need_unknown", "unknown"},
    failure_boundary={"info_missing_candidate", "info_visible_but_adaptation", "task_contract_candidate", "own_execution_candidate", "no_failure", "unknown"},
    reading_efficiency={"avoidable_overhead_candidate", "contextual_confirmation", "no_identified_overhead", "unknown"})


def prompt():
    original = (REPO / "experiments/section7_analysis_20261003/review_prompt.txt").read_text(encoding="utf-8")
    return original + """

本轮补充：这是五种 agentic search 访问方式的只读记忆实验。分析模型固定 GLM 5.3 Flash。
实际目标看过的动态记忆工具结果在 target_visible 内；target_startup_memory 是启动时真正给过的索引/入口。
corresponding_source_original 只供离线机会判断，不能因它出现在审查包里就说 solver 读到了它。
全部源已合法保存且只读，WRITE_ADMISSION 与 UPDATE_RETENTION 通常为 not_applicable，不凭旧框架强加 writer/遗忘标签。
给定 result_status 是直接记录，不得改变；资产不可评分仍可以分析搜索与成本，不推断答对/答错。
传给你的每个 evidence section 带 [L0001] 行号。引用使用 section 和 quote，另附 line（1-based整数）；quote 必须是对应原文中的短字面片段，不包含显示用 [L0001] 前缀。优先引用一行内 10–150 字符。
不要给 chain-of-thought，只输出可核查的短理由。非正文元数据不自动等于无用成本；字符/字节不是 token，命中不是使用，打开文件也不等于全部内容向模型曝光。
除原 schema 外必须增加 agentic_search 对象，三项都使用 {value, evidence:[{section,line,quote}], reason} 格式：
- search_strategy: focused | overbroad_candidate | stopped_early_candidate | no_search_need_unknown | unknown
- failure_boundary: info_missing_candidate | info_visible_but_adaptation | task_contract_candidate | own_execution_candidate | no_failure | unknown
- reading_efficiency: avoidable_overhead_candidate | contextual_confirmation | no_identified_overhead | unknown
每个非 unknown 值必须引用证据；“no_search_need_unknown”仅表示没有调用、需求未定，不能等价检索失败。
在 minimal_intervention 中仅提一个可测试的访问工具/检索策略改动，不修改目标答案、隐藏测试、来源库、模型或源写入，不硬编码本题。若没有证据支持改动则 change=none。
总输出保持简洁：每个 reason 最多两句，最多四个标签，不重复整段代码。causal_claim 必须为 false。
"""


def render(packet):
    parts = [f"case_id: {packet['case_id']}", f"result_status: {packet['result_status']}", packet["global_rules"], packet["unavailable"]]
    for section in packet["evidence"]:
        parts += ["\n## EVIDENCE SECTION " + section["id"], "NOTE: " + str(section.get("note") or ""),
                  "\n".join(f"[L{i:04d}] {line}" for i, line in enumerate(section["text"].splitlines(), 1))]
    return "\n".join(parts)


def validate(obj, packet):
    errors = []
    required = {"case_id", "result_status", "semantic", "labels", "primary_hypothesis", "competing_explanations", "confidence", "uncertainties", "minimal_intervention", "causal_claim", "agentic_search"}
    if not isinstance(obj, dict):
        return ["not an object"]
    errors += ["missing:" + key for key in sorted(required - set(obj))]
    if obj.get("case_id") != packet["case_id"]:
        errors.append("case_id mismatch")
    if obj.get("result_status") != packet["result_status"]:
        errors.append("result_status mismatch")
    if obj.get("causal_claim") is not False:
        errors.append("unsupported causal claim")
    evidence = {s["id"]: s["text"] for s in packet["evidence"]}
    claims = []
    for group, enums in (("semantic", ENUMS), ("agentic_search", AGENTIC_ENUMS)):
        for field, allowed in enums.items():
            claim = obj.get(group, {}).get(field, {})
            if claim.get("value") not in allowed:
                errors.append("enum:" + group + "." + field)
            claims.append((group + "." + field, claim))
    labels = obj.get("labels", [])
    if not isinstance(labels, list) or len(labels) > 4:
        errors.append("invalid labels")
        labels = []
    for i, claim in enumerate(labels):
        if claim.get("tag") not in TAGS or claim.get("level") not in ("D0", "D1"):
            errors.append("label enum:" + str(i))
        claims.append(("label." + str(i), claim))
    for field, claim in claims:
        if not isinstance(claim, dict):
            errors.append("claim shape:" + field)
            continue
        citations = claim.get("evidence", [])
        if not citations and claim.get("value") not in ("unknown", "not_applicable"):
            errors.append("missing citation:" + field)
        for i, cite in enumerate(citations):
            text = evidence.get(cite.get("section"), "")
            quote, line = cite.get("quote"), cite.get("line")
            if not isinstance(quote, str) or not quote or quote not in text:
                errors.append(f"unmatched quote:{field}:{i}")
            if type(line) is not int or not 1 <= line <= len(text.splitlines()):
                errors.append(f"invalid line:{field}:{i}")
    if obj.get("primary_hypothesis") not in set(TAGS) | {"unknown"}:
        errors.append("invalid primary")
    if not obj.get("competing_explanations"):
        errors.append("no competing explanation")
    if obj.get("confidence") not in ("high", "medium", "low", "unable"):
        errors.append("invalid confidence")
    if not isinstance(obj.get("uncertainties"), list):
        errors.append("uncertainties must be a list")
    intervention = obj.get("minimal_intervention")
    if not isinstance(intervention, dict) or not all(isinstance(intervention.get(k), str) for k in ("change", "fixed", "falsifier")):
        errors.append("invalid minimal_intervention")
    return errors


def call(case, key, phase, rate_limit_retry=False):
    folder = ROOT / "api" / phase / case["case_id"]
    original_folder = folder
    if rate_limit_retry:
        previous = read(original_folder / "terminal.json")
        assert previous["status"] == "http_error" and previous["http_status"] == 429
        folder = folder / "transport-retry-1"
    if (folder / "terminal.json").exists():
        return read(folder / "terminal.json")
    if folder.exists() and any(folder.iterdir()):
        raise RuntimeError("Unfinished review attempt; audit before restart")
    packet_path = ROOT / case["packet"]
    assert sha(packet_path) == case["packet_sha256"]
    packet = read(packet_path)
    system = (ROOT / "review_prompt.txt").read_text(encoding="utf-8")
    body = dict(model="glm-5.3-flash", messages=[dict(role="system", content=system), dict(role="user", content=render(packet))],
                temperature=1, max_tokens=24000, thinking=dict(type="enabled"), reasoning_effort="high",
                response_format=dict(type="json_object"), stream=False)
    if rate_limit_retry:
        assert body == read(original_folder / "request.json"), "Retry must preserve the exact analysis request"
    raw = json.dumps(body, ensure_ascii=False).encode()
    assert len(raw) <= 400000
    save(folder / "request.json", body)
    state = dict(case_id=case["case_id"], provider="glm", requested_model=body["model"], role="offline_reviewer",
        phase=phase, packet_sha256=case["packet_sha256"], prompt_sha256=sha(ROOT / "review_prompt.txt"),
        raw_request_sha256=hashlib.sha256(raw).hexdigest(), request_bytes=len(raw),
        started_at_utc=datetime.now(timezone.utc).isoformat(), retry=rate_limit_retry, http_attempts=1,
        usage=None, money=None, status="started")
    save(folder / "started.json", state)
    started = time.perf_counter()
    try:
        request = Request("https://api.z.ai/api/paas/v4/chat/completions", data=raw,
                          headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        with urlopen(request, timeout=660) as response:
            response_bytes = response.read()
            state["http_status"] = response.status
        response = json.loads(response_bytes)
        save(folder / "response.json", response)
        state.update(usage=response.get("usage"), returned_model=response.get("model"), response_id=response.get("id"),
                     response_sha256=hashlib.sha256(response_bytes).hexdigest())
        text = response["choices"][0]["message"].get("content") or ""
        state["finish_reason"] = response["choices"][0].get("finish_reason")
        (folder / "visible-output.txt").write_text(text, encoding="utf-8")
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(cleaned)
        save(ROOT / "reviews" / phase / (case["case_id"] + ".json"), result)
        state["validation_errors"] = validate(result, packet)
        state["status"] = "valid" if not state["validation_errors"] else "needs_audit"
    except HTTPError as error:
        state.update(status="http_error", http_status=error.code, error=error.read().decode(errors="replace")[:1500])
    except Exception as error:
        state.update(status="error", error=type(error).__name__ + ": " + str(error)[:800])
    state.update(seconds=time.perf_counter() - started, finished_at_utc=datetime.now(timezone.utc).isoformat())
    save(folder / "terminal.json", state)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["initial", "r1", "r2", "r3"])
    parser.add_argument("--first", action="store_true")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--retry-rate-limited", action="store_true")
    args = parser.parse_args()
    assert 1 <= args.workers <= 48
    if read(ROOT / "records/round-budget.json").get("closed") or args.phase == "r3":
        raise RuntimeError("Final-round stop: no new paid reviewer calls; offline audit only")
    manifest = read(ROOT / "records" / f"review-manifest-{args.phase}.json")
    assert sha(ROOT / "review_prompt.txt") == read(ROOT / "records/protocol.json")["review_prompt_sha256"]
    if args.phase != "initial":
        assert len({c["index"] for c in manifest["cases"]}) <= 12
    from run import engine
    eng, _ = engine()
    key = eng.secret()
    cases = manifest["cases"][:1] if args.first else manifest["cases"]
    if not args.first:
        first = read(ROOT / "api" / args.phase / cases[0]["case_id"] / "terminal.json")
        # Initial transport/JSON compatibility is already established. A later review's
        # malformed JSON is retained as a quality failure, not a reason to reissue it.
        compatible = first["status"] in ("valid", "needs_audit") or (
            args.phase != "initial" and first.get("http_status") == 200 and first.get("finish_reason") == "stop")
        assert compatible and first["usage"] is not None
    if args.retry_rate_limited:
        cases = [c for c in cases if (ROOT / "api" / args.phase / c["case_id"] / "terminal.json").exists()
                 and read(ROOT / "api" / args.phase / c["case_id"] / "terminal.json").get("http_status") == 429]
    def terminal_path(case):
        folder = ROOT / "api" / args.phase / case["case_id"]
        return (folder / "transport-retry-1" if args.retry_rate_limited else folder) / "terminal.json"
    jobs = iter(c for c in cases if not terminal_path(c).exists())
    done_rows, active, errors = [], {}, []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        def dispatch():
            try:
                case = next(jobs)
            except StopIteration:
                return False
            active[pool.submit(call, case, key, args.phase, args.retry_rate_limited)] = case["case_id"]
            return True
        for _ in range(1 if args.first else args.workers):
            dispatch()
        while active:
            finished, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in finished:
                cid = active.pop(future)
                result = future.result()
                done_rows.append(result)
                print(json.dumps({k: result.get(k) for k in ("case_id", "status", "seconds", "finish_reason", "usage")}), flush=True)
                if result["status"] == "http_error" or result.get("usage") is None:
                    errors.append(dict(case_id=cid, status=result["status"]))
            if not errors:
                while len(active) < args.workers and dispatch():
                    pass
            suffix = "-retry" if args.retry_rate_limited else ""
            save(ROOT / "records" / f"review-progress-{args.phase}{suffix}.json", dict(new_completed=len(done_rows), stopped_dispatch=bool(errors), errors=errors))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
