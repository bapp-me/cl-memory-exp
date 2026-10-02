"""Claude PreToolUse policy: file tools may access only their run workspace."""
import json
import sys
from pathlib import Path

root=Path(sys.argv[1]).resolve()
event=json.load(sys.stdin)
name=event.get('tool_name','')
args=event.get('tool_input',{})
field='file_path' if name in {'Read','Write','Edit'} else 'path'
raw=args.get(field) or str(root)
target=(root/str(raw)).resolve()
allowed=target==root or root in target.parents
if name=='Glob':
    pattern=str(args.get('pattern','')).replace('\\','/')
    allowed=allowed and not pattern.startswith('/') and '..' not in pattern.split('/') and ':' not in pattern
if not allowed:
    print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny',
                                           'permissionDecisionReason':'Experiment file tools are limited to the isolated run workspace. Use the SQL tool for database access.'}}))
else:
    print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'allow'}}))
