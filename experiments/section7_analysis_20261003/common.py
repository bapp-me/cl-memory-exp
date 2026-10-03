"""Read-only baseline access and reproducible section 7.2 derived artifacts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OBS = REPO / 'experiments/section7_observability_20261002'
LEGACY = REPO / 'experiments/agent_memory_plan_20261002'
METHODS = ['no_memory', 'bounded_icl', 'episodic_retrieval', 'mem0', 'awm', 'ace']


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def lines(p):
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()] if p.exists() else []


def visible(messages):
    """Never include private reasoning/thinking blocks in reviewer inputs."""
    result = []
    for i, m in enumerate(messages):
        if m['role'] == 'assistant':
            blocks = [b for b in m.get('content', []) if b.get('type') in ['text', 'toolCall']]
            result.append({'message_index': i, 'role': 'assistant', 'content': blocks})
        elif m['role'] == 'toolResult':
            result.append({'message_index': i, 'role': 'toolResult', 'tool': m.get('toolName'),
                           'isError': m.get('isError'), 'content': m.get('content')})
    return result


def case_id(row):
    return 'c-' + digest([row['method'], row['benchmark'], row['index']])[:12]
