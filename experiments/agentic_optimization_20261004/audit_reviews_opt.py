"""Keep raw GLM labels distinct from grounded citations and AI adjudication."""
import argparse
from collections import Counter, defaultdict
import json

from common_opt import *
from review_glm import validate


def strings(value, pointer="$", depth=0):
    if depth > 10:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, pointer + "/" + str(key), depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, pointer + "/" + str(index), depth + 1)
    elif isinstance(value, str):
        yield pointer, value
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return
        if decoded != value:
            yield from strings(decoded, pointer + "/@json", depth + 1)


def resolve(cite, sections):
    text = sections.get(cite.get("section"), "")
    quote = cite.get("quote")
    if not isinstance(quote, str) or not quote:
        return dict(status="unresolved", reason="missing quote or section")
    start = text.find(quote)
    if start >= 0:
        actual_line = text[:start].count("\n") + 1
        return dict(status="raw_exact", char_start=start, char_end=start + len(quote), actual_line=actual_line,
                    declared_line_matches=cite.get("line") == actual_line)
    # Equivalent escaping is separate; never silently change the original quote.
    variants = [quote]
    for _ in range(2):
        variants.append(json.dumps(variants[-1], ensure_ascii=False)[1:-1])
    variants.append(quote.replace("\\n", "\n").replace('\\"', '"'))
    for q in variants[1:]:
        start = text.find(q)
        if start >= 0:
            return dict(status="json_representation_match", char_start=start, char_end=start + len(q),
                        resolved_quote=q, original_quote_unchanged=True)
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return dict(status="unresolved", reason="quote not found")
    for pointer, leaf in strings(value):
        for q in variants:
            start = leaf.find(q)
            if start >= 0:
                return dict(status="decoded_json_value_match", pointer=pointer, char_start=start,
                            char_end=start + len(q), resolved_quote=q, original_quote_unchanged=True)
    return dict(status="unresolved", reason="no exact raw or decoded source-value match")


def chosen(case, phase):
    folder = ROOT / "api" / phase / case["case_id"]
    retry = folder / "transport-retry-1/terminal.json"
    terminal = retry if retry.exists() else folder / "terminal.json"
    answer = ROOT / "reviews" / phase / (case["case_id"] + ".json")
    repaired = ROOT / "reviews/syntax-repaired" / phase / (case["case_id"] + ".json")
    return (read(terminal) if terminal.exists() else None,
            read(answer) if answer.exists() else read(repaired) if repaired.exists() else None,
            "raw" if answer.exists() else "syntax_repaired" if repaired.exists() else "missing")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["initial", "r1", "r2", "r3"])
    args = parser.parse_args()
    manifest = read(ROOT / "records" / f"review-manifest-{args.phase}.json")
    output = []
    for case in manifest["cases"]:
        terminal, answer, source = chosen(case, args.phase)
        if terminal is None:
            output.append(dict(**case, status="unfinished", parsed=False, fully_citation_grounded=False))
            continue
        packet = read(ROOT / case["packet"])
        if not isinstance(answer, dict):
            output.append(dict(**case, status=terminal["status"], parsed=False, fully_citation_grounded=False,
                               error=terminal.get("error"), output_source=source))
            continue
        sections = {s["id"]: s["text"] for s in packet["evidence"]}
        claims = []
        for group in ("semantic", "agentic_search"):
            for field, claim in answer.get(group, {}).items():
                claims.append((group + "." + field, claim))
        claims += [("labels." + str(i), c) for i, c in enumerate(answer.get("labels", []))]
        grounded = []
        for field, claim in claims:
            citations = [dict(citation=c, resolution=resolve(c, sections)) for c in claim.get("evidence", [])]
            supported = bool(citations) and all(c["resolution"]["status"] != "unresolved" for c in citations)
            if claim.get("value") in ("unknown", "not_applicable") and not citations:
                supported = True
            grounded.append(dict(field=field, value=claim.get("value", claim.get("tag")), level=claim.get("level", "D1"),
                citation_grounded=supported, citations=citations, reason=claim.get("reason")))
        errors = validate(answer, packet)
        raw_labels = [c.get("tag") for c in answer.get("labels", [])]
        valid_labels = [c["value"] for c in grounded if c["field"].startswith("labels.") and c["citation_grounded"]
                        and c["value"] in TAGS and c["level"] in ("D0", "D1")]
        output.append(dict(**case, status=terminal["status"], parsed=True, output_source=source,
            strict_schema_and_raw_quotes_passed=not errors, strict_errors=errors,
            fully_citation_grounded=all(c["citation_grounded"] for c in grounded),
            raw_labels=raw_labels, grounded_labels=valid_labels, claims=grounded,
            primary_hypothesis=answer.get("primary_hypothesis"), minimal_intervention=answer.get("minimal_intervention"),
            competing_explanations=answer.get("competing_explanations"), causal_claim=answer.get("causal_claim")))
    summaries = {}
    for method in sorted({c["method"] for c in manifest["cases"]}):
        group = [r for r in output if r["method"] == method]
        parsed = [r for r in group if r["parsed"]]
        semantics = defaultdict(Counter)
        for row in parsed:
            for claim in row["claims"]:
                if not claim["field"].startswith("labels."):
                    semantics[claim["field"] + ":all"][claim["value"]] += 1
                    if claim["citation_grounded"]:
                        semantics[claim["field"] + ":grounded"][claim["value"]] += 1
        summaries[method] = dict(cases=len(group), parsed=len(parsed), strict_valid=sum(r.get("strict_schema_and_raw_quotes_passed", False) for r in group),
            fully_citation_grounded=sum(r["fully_citation_grounded"] for r in group),
            result_states=dict(Counter(r["result_status"] for r in group)),
            raw_label_counts=dict(Counter(t for r in parsed for t in r["raw_labels"])),
            grounded_label_counts=dict(Counter(t for r in parsed for t in r["grounded_labels"])),
            semantic_counts={k: dict(v) for k, v in semantics.items()})
    attempts = [read(p) for p in (ROOT / "api" / args.phase).rglob("terminal.json")]
    usage = [r["usage"] for r in attempts if r.get("usage")]
    costs = dict(http_attempts=len(attempts), unknown_usage_attempts=sum(r.get("usage") is None for r in attempts),
        prompt_tokens_including_cache=sum(u.get("prompt_tokens", 0) for u in usage),
        completion_tokens_including_reasoning=sum(u.get("completion_tokens", 0) for u in usage),
        total_tokens=sum(u.get("total_tokens", 0) for u in usage),
        cache_read_tokens=sum(u.get("prompt_tokens_details", {}).get("cached_tokens", 0) for u in usage), money=None)
    result = dict(phase=args.phase, attempted=sum(r["status"] != "unfinished" for r in output), planned=len(output),
        parsed=sum(r["parsed"] for r in output), citation_grounding_is_not_semantic_validation=True,
        human_reviewed=False, summary=summaries, costs=costs, rows=output)
    save(ROOT / "records" / f"review-audit-{args.phase}.json", result)
    print(json.dumps(dict(phase=args.phase, attempted=result["attempted"], planned=result["planned"], parsed=result["parsed"], costs=costs,
                         summaries={m: {k: v[k] for k in ("cases", "parsed", "strict_valid", "fully_citation_grounded", "grounded_label_counts")} for m, v in summaries.items()})))


if __name__ == "__main__":
    main()
