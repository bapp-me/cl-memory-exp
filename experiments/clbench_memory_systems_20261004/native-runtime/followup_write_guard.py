"""Native PreToolUse hook: model file writes stay inside isolated memory."""
import json
from pathlib import Path
import sys


def decide(event,root):
    if event.get('tool_name') not in {'Write','Edit'}:return None
    value=event.get('tool_input',{}).get('file_path','')
    path=Path(value)
    allowed=bool(value) and path.is_absolute() and path.resolve().is_relative_to(Path(root).resolve())
    return {'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'allow' if allowed else 'deny',
            'permissionDecisionReason':'Controlled maintenance writes are limited to this isolated memory directory.'}}


if __name__=='__main__':
    event=json.load(sys.stdin);result=decide(event,sys.argv[1])
    if result:print(json.dumps(result))
