"""Shared paths and accounting for a strictly bounded agentic-search optimization study."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / "experiments/agentic_search_20261004"
NATIVE = REPO / "experiments/agentic_native_20261004"
OBS = REPO / "experiments/section7_observability_20261002"
LEGACY = REPO / "experiments/agent_memory_plan_20261002"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(NATIVE))
METHODS = ("lexical", "hybrid_context", "graph_walk", "native_files", "native_shell")
PLAN_REVISION = "0571ff586f818a6a20b142edb3f3ad2cd2a85cd4"
TAGS = ("EVAL_CONTRACT", "INFRA_PROTOCOL", "TASK_EXECUTION", "OPPORTUNITY_SOURCE", "WRITE_ADMISSION",
        "REPRESENTATION", "RETRIEVAL", "PACKING_VISIBILITY", "USE_TRANSFER", "UPDATE_RETENTION", "SCOPE_INTERFERENCE", "COST_UTILITY")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()] if Path(path).exists() else []


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def baseline_rows():
    return read(BASE / "records/analysis.json")["rows"] + read(NATIVE / "records/analysis.json")["rows"]


def visible(messages):
    output = []
    for i, message in enumerate(messages):
        if message["role"] == "assistant":
            output.append(dict(message_index=i, role="assistant", content=[v for v in message.get("content", [])
                          if v.get("type") in ("text", "toolCall")]))
        elif message["role"] == "toolResult":
            output.append(dict(message_index=i, role="toolResult", tool=message.get("toolName"),
                               tool_call_id=message.get("toolCallId"), isError=message.get("isError"), content=message.get("content")))
    return output


def result_status(row):
    if row.get("terminal_state") in ("infrastructure_failure", "memory_failure", "evaluator_failure"):
        return "infrastructure_interruption"
    if row.get("scorable") is False:
        return "asset_unscorable"
    if row.get("scorable") is True:
        return "success" if row.get("correct") is True else "scorable_failure"
    return "observation_missing"
