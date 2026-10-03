"""Lossless scalar extraction from GLM text, including malformed JSON. No invented citations."""
import re
from collections import Counter, defaultdict

from common_opt import *
from review_glm import ENUMS, AGENTIC_ENUMS


def main():
    output = []
    for phase in ("initial", "r1", "r2"):
        manifest_path = ROOT / "records" / f"review-manifest-{phase}.json"
        if not manifest_path.exists():
            continue
        for case in read(manifest_path)["cases"]:
            folder = ROOT / "api" / phase / case["case_id"]
            retry = folder / "transport-retry-1"
            if (retry / "visible-output.txt").exists():
                folder = retry
            path = folder / "visible-output.txt"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            fields = {}
            for field, allowed in {**ENUMS, **AGENTIC_ENUMS}.items():
                pattern = r'"' + re.escape(field) + r'"\s*:\s*\{\s*"value"\s*:\s*"([^"]*)"'
                matches = list(re.finditer(pattern, text))
                if len(matches) == 1:
                    match = matches[0]
                    fields[field] = dict(value=match.group(1), valid_enum=match.group(1) in allowed,
                        raw_char_start=match.start(1), raw_char_end=match.end(1))
                else:
                    fields[field] = dict(value=None, state="missing" if not matches else "ambiguous_multiple_occurrences")
            labels = [dict(tag=m.group(1), valid_enum=m.group(1) in TAGS, raw_char_start=m.start(1), raw_char_end=m.end(1))
                      for m in re.finditer(r'"tag"\s*:\s*"([^"]*)"', text)]
            output.append(dict(phase=phase, case_id=case["case_id"], method=case["method"], index=case["index"],
                source_file=path.relative_to(ROOT).as_posix(), source_sha256=sha(path), fields=fields, labels=labels,
                original_json_parseable=(ROOT / "reviews" / phase / (case["case_id"] + ".json")).exists(),
                source_values_reproduced_verbatim=True, citations_reconstructed=False,
                evidence_level="D0 about what GLM wrote; not validation of its D1 judgments"))
    counts = defaultdict(Counter)
    for row in output:
        key = row["phase"]
        counts[key]["outputs"] += 1
        counts[key]["unparseable_json_with_readable_scalar_fields"] += not row["original_json_parseable"]
        counts[key]["all_4_original_semantic_fields_present"] += all(row["fields"][f].get("valid_enum", False) for f in ENUMS)
        counts[key]["all_7_fields_present"] += all(v.get("valid_enum", False) for v in row["fields"].values())
    distributions = {}
    for phase in ("initial", "r1", "r2"):
        distributions[phase] = {}
        for method in sorted({r["method"] for r in output if r["phase"] == phase}):
            group = [r for r in output if r["phase"] == phase and r["method"] == method]
            distributions[phase][method] = {field: dict(Counter(
                r["fields"][field].get("value") or "missing_or_ambiguous" for r in group))
                for field in {**ENUMS, **AGENTIC_ENUMS}}
    save(ROOT / "records/raw-field-extraction.json", dict(rows=output, summary={k:dict(v) for k,v in counts.items()},
        raw_scalar_distributions=distributions,
        new_model_calls=0, qualification="Malformed outputs retained; extracted scalar claims remain ungrounded unless separately adjudicated. No JSON rewriting or citation invention."))
    print({k:dict(v) for k,v in counts.items()})


if __name__ == "__main__":
    main()
