"""Read-only audit of old persistent-memory changes; no model/API calls."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'memory_direction_20261002'


def snapshot(directory):
    return {str(p.relative_to(directory)): p.read_text(encoding='utf-8')
            for p in directory.rglob('*.md')} if directory.exists() else {}


def run():
    rows = []
    for directory in sorted((OLD / 'results/runs').iterdir()):
        if not (directory / 'input.json').exists():
            continue
        config = json.loads((directory / 'input.json').read_text(encoding='utf-8'))
        after = snapshot(directory / 'memory_after')
        before = snapshot(directory / 'memory_before')
        before_source = 'memory_before'
        if not before and config.get('memory_from'):
            before = snapshot(OLD / 'results/runs' / config['memory_from'] / 'memory_after')
            before_source = 'reconstructed from immutable source run; not a recorded before snapshot'
        calls = []
        if (directory / 'events.jsonl').exists():
            for line in (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                for block in event.get('message', {}).get('content', []):
                    if isinstance(block, dict) and block.get('type') == 'tool_use':
                        if block.get('name') in ('Write', 'Edit'):
                            calls.append(block)
        if (directory / 'hermes-result.json').exists():
            data = json.loads((directory / 'hermes-result.json').read_text(encoding='utf-8'))
            for message in data.get('messages', []):
                for call in message.get('tool_calls') or []:
                    if call.get('function', {}).get('name') == 'memory':
                        calls.append(call)
        changes = []
        for name in sorted(set(before) | set(after)):
            if before.get(name, '') != after.get(name, ''):
                changes.append({'file': name, 'diff': '\n'.join(difflib.unified_diff(
                    before.get(name, '').splitlines(), after.get(name, '').splitlines(),
                    fromfile='before/' + name, tofile='after/' + name))})
        rows.append({'run_id': directory.name, 'agent': config.get('agent'),
                     'protocol': config.get('protocol'), 'memory_from': config.get('memory_from'),
                     'source_task_explicit_write': config.get('write_memory', False),
                     'before_source': before_source, 'changed': bool(changes),
                     'changes': changes, 'write_calls': calls})
    target = ROOT / 'results'
    target.mkdir(exist_ok=True)
    (target / 'old-memory-audit.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    consumers = [r for r in rows if r['memory_from'] and not r['source_task_explicit_write']]
    print(json.dumps({'runs': len(rows), 'consumers': len(consumers),
                      'changed_consumers': [{k: r[k] for k in ('run_id', 'changed', 'before_source')}
                                            for r in consumers if r['changed']]}, ensure_ascii=False))


if __name__ == '__main__':
    run()
