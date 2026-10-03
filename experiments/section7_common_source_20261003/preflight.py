"""Offline discussion audit; no model calls, candidate execution, or baseline writes."""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LEGACY = REPO / "experiments/agent_memory_plan_20261002"
OBS = REPO / "experiments/section7_observability_20261002"
ANALYSIS = REPO / "experiments/section7_analysis_20261003"
INPUTS = {}


def read(path):
    data = path.read_bytes()
    INPUTS[path.relative_to(REPO).as_posix()] = hashlib.sha256(data).hexdigest()
    return json.loads(data)


def size(value, compact=False):
    kwargs = {"separators": (",", ":")} if compact else {}
    return len(json.dumps(value, ensure_ascii=False, **kwargs).encode())


def episode(method, index, prompt):
    path = LEGACY / "runs" / f"full-codeeval-glm-{method}" / f"{index:03d}" / "pi-result.json"
    visible = []
    for message in read(path)["messages"]:
        if message["role"] == "assistant":
            visible.extend(block for block in message.get("content", [])
                           if block.get("type") in ("text", "toolCall"))
        elif message["role"] == "toolResult":
            visible.append({"tool": message.get("toolName"), "content": message.get("content")})
    # No Memory did not retain a library. Assign common-library chronology 0..47;
    # do not preserve its empty-history sequence=0 for every source episode.
    return {"sequence": index, "text": json.dumps({"task": prompt, "trajectory": visible}, ensure_ascii=False)}


def representation_sizes(selected):
    structured = [{"sequence": entry["sequence"], **json.loads(entry["text"])} for entry in selected]
    counts = Counter()

    def walk(value):
        if isinstance(value, str):
            counts[value] += 1
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            assert set(value) != {"$text"}
            for item in value.values():
                walk(item)

    walk(structured)
    repeated = {text: f"s{i}" for i, (text, count) in enumerate(counts.items())
                if count > 1 and len(text.encode()) >= 160}
    definitions = {ref: text for text, ref in repeated.items()}

    def encode(value):
        if isinstance(value, str):
            return {"$text": repeated[value]} if value in repeated else value
        if isinstance(value, list):
            return [encode(item) for item in value]
        if isinstance(value, dict):
            return {key: encode(item) for key, item in value.items()}
        return value

    def decode(value):
        if isinstance(value, list):
            return [decode(item) for item in value]
        if isinstance(value, dict):
            if set(value) == {"$text"}:
                return definitions[value["$text"]]
            return {key: decode(item) for key, item in value.items()}
        return value

    encoded = encode(structured)
    assert decode(encoded) == structured
    restored = [{"sequence": entry["sequence"], "text": json.dumps(
        {"task": entry["task"], "trajectory": entry["trajectory"]}, ensure_ascii=False)}
        for entry in structured]
    assert restored == selected
    payload = {"definitions": definitions, "episodes": encoded} if definitions else structured
    return {"raw_bytes": size(selected), "structured_bytes": size(structured, True),
            "exact_string_dedup_bytes": size(payload, True), "repeated_long_strings": len(definitions)}


def ranked(history, prompt, field):
    query = set(re.findall(r"\w+", prompt.lower()))
    scores = []
    for entry in history:
        text = entry["text"] if field == "full_episode" else json.loads(entry["text"])["task"]
        words = set(re.findall(r"\w+", text.lower()))
        scores.append((len(query & words) / (len(query | words) or 1), entry["sequence"], entry))
    return sorted(scores, key=lambda item: (item[0], item[1]), reverse=True)


def pack(entries):
    selected = entries[:]
    while selected and size(selected) > 48000:
        selected.pop(0)
    return selected


def main():
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    assert len(assets) == 96
    assert all(row["category"] == "raw" for row in assets[:48])
    assert all(row["category"] == "new" for row in assets[48:])
    # Only legal prompt text enters episode formation or retrieval.
    prompts = [row["problem"] for row in assets]
    recorded = read(LEGACY / "runs/full-codeeval-glm-episodic_retrieval/048/memory-before.json")
    assert [episode("episodic_retrieval", i, prompts[i]) for i in range(48)] == recorded
    history = [episode("no_memory", i, prompts[i]) for i in range(48)]
    code_path = LEGACY / "core.py"
    code = code_path.read_bytes()
    INPUTS[code_path.relative_to(REPO).as_posix()] = hashlib.sha256(code).hexdigest()
    node = next(node for node in ast.parse(code.decode()).body
                if isinstance(node, ast.FunctionDef) and node.name == "memory_context")
    namespace = {"re": re, "json": json}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<frozen memory_context>", "exec"), namespace)

    selections = {}
    variants = [("bounded_icl_raw", None, None)] + [
        (f"jaccard_{field}_top{k}", field, k)
        for field in ("full_episode", "source_prompt") for k in (1, 2, 3)]
    for name, field, k in variants:
        rows = []
        for index in range(48, 96):
            if field is None:
                selected = pack(history)
                assert selected == namespace["memory_context"](history, "bounded_icl", prompts[index])
            else:
                selected = pack(sorted([item[2] for item in ranked(history, prompts[index], field)[:k]],
                                       key=lambda entry: entry["sequence"]))
                if field == "full_episode" and k == 3:
                    assert selected == namespace["memory_context"](history, "episodic_retrieval", prompts[index])
            rows.append({"target_index": index, "selected_indices": [entry["sequence"] for entry in selected],
                         **representation_sizes(selected)})
        selections[name] = rows

    # Offline diagnostic joins happen AFTER all retrieval decisions. Neither
    # paired IDs nor hidden correctness labels are retrieval/packing inputs.
    pairs = {row["target_index"]: row for row in read(ANALYSIS / "records/source-target-pairs.json")
             if row["method"] == "no_memory"}
    summaries = {}
    for name, rows in selections.items():
        for row in rows:
            pair = pairs[row["target_index"]]
            row.update(target_task_id=pair["target_task_id"], target_scorable=pair["target_scorable"],
                       corresponding_source_injected=pair["source_index"] in row["selected_indices"])
        valid = [row for row in rows if row["target_scorable"] is True]
        totals = {key: sum(row[key] for row in rows)
                  for key in ("raw_bytes", "structured_bytes", "exact_string_dedup_bytes")}
        summaries[name] = {
            "targets": len(rows), "scorable_targets": len(valid),
            "corresponding_source_hits_all": sum(row["corresponding_source_injected"] for row in rows),
            "corresponding_source_hits_scorable": sum(row["corresponding_source_injected"] for row in valid),
            "mean_selected_episodes": statistics.mean(len(row["selected_indices"]) for row in rows),
            "mean_injected_bytes": statistics.mean(row["raw_bytes"] for row in rows),
            "structured_byte_reduction": 1 - totals["structured_bytes"] / totals["raw_bytes"],
            "exact_string_dedup_byte_reduction": 1 - totals["exact_string_dedup_bytes"] / totals["raw_bytes"],
            "repeated_long_strings_across_target_payloads": sum(row["repeated_long_strings"] for row in rows),
            "missed_target_ids": [row["target_task_id"] for row in rows if not row["corresponding_source_injected"]]}

    cards = []
    for entry in history:
        decoded = json.loads(entry["text"])
        submissions = [event["arguments"]["code"] for event in decoded["trajectory"]
                       if event.get("type") == "toolCall" and event.get("name") == "SUBMIT"]
        assert len(submissions) == 1
        cards.append({"sequence": entry["sequence"], "task": decoded["task"],
                      "unverified_submission": submissions[0]})
    packed_cards = pack(cards)
    same_ids = [card for card in cards if card["sequence"] in selections["bounded_icl_raw"][0]["selected_indices"]]
    historical_cost = sum(read(LEGACY / "runs/full-codeeval-glm-no_memory" / f"{i:03d}" /
                               "execution.json")["usage"]["totalTokens"] for i in range(48))
    report = {
        "status": "discussion_only_no_online_execution", "date_hong_kong": "2026-10-03",
        "user_confirmed": {"source": "existing No Memory 48 raw-task legal trajectories",
                           "target_memory_policy": "frozen source library; no complex-task writeback"},
        "model_calls": 0, "source_extraction_verified_against_existing_library": True,
        "library": {"episodes": 48, "serialized_bytes": size(history),
                    "historical_shared_source_solver_tokens": historical_cost,
                    "incremental_source_solver_calls": 0},
        "summaries": summaries, "target_selections": selections,
        "lossy_task_and_submission_probe": {
            "all_48_bytes": size(cards), "reduction_against_full_48": 1 - size(cards) / size(history),
            "same_original_icl_8_bytes": size(same_ids), "fifo_repacked_count": len(packed_cards),
            "fifo_repacked_bytes": size(packed_cards),
            "fifo_repacked_source_indices": [card["sequence"] for card in packed_cards],
            "warning": "Discards exploration, observations and recovery. Not a verified safe compression. Repacking also changes selected episodes."},
        "limits": [
            "Byte counts are not provider token counts, measured spend or downstream correctness.",
            "Corresponding-source provenance is diagnostic; presence does not guarantee useful or correct content.",
            "This is a post-baseline development audit, not unseen transfer or an independent repeat.",
            "The tested reversible codec interns exact string leaves >=160 UTF-8 bytes; no claim that all possible substring compression is exhausted.",
            "No failing or unscorable source was removed using hidden scores.",
            "Model-visible provenance wording must say archived No Memory observations, not falsely describe these as this reader's own prior observations.",
            "No API batch size, optimized configuration or extra paid controls have been approved in this discussion."],
        "input_hashes": INPUTS}
    for relative, expected in INPUTS.items():
        assert hashlib.sha256((REPO / relative).read_bytes()).hexdigest() == expected
    destination = ROOT / "records/preflight.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "source_files_unchanged": len(INPUTS),
                      "library": report["library"], "summaries": summaries,
                      "lossy_probe": report["lossy_task_and_submission_probe"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
