"""Pinned native foreground memory maintenance with a common, narrow fixture."""
import json
import os
from pathlib import Path
import subprocess


def run(path,cfg,out,project):
    home=Path('/state/home/.claude');home.mkdir(exist_ok=True)
    memory=home/'projects/-state-work-database/memory'
    memory.mkdir(parents=True,exist_ok=True)
    settings={'autoMemoryEnabled':True,'model':'glm-5.3-flash','hooks':{'PreToolUse':[{
        'matcher':'Write|Edit','hooks':[{'type':'command',
            'command':'python /runtime/followup_write_guard.py '+str(memory)}]}]}}
    (out/'settings.json').write_text(json.dumps(settings))
    (out/'mcp.json').write_text('{"mcpServers":{}}')
    env={**os.environ,'HOME':'/state/home','CLAUDE_CONFIG_DIR':str(home),'DISABLE_AUTOUPDATER':'1',
        'ANTHROPIC_BASE_URL':cfg['gateway'],'ANTHROPIC_AUTH_TOKEN':cfg['gateway_token'],
        'ANTHROPIC_MODEL':'glm-5.3-flash','ANTHROPIC_DEFAULT_OPUS_MODEL':'glm-5.3-flash',
        'ANTHROPIC_DEFAULT_SONNET_MODEL':'glm-5.3-flash','ANTHROPIC_DEFAULT_HAIKU_MODEL':'glm-5.3-flash',
        'CLAUDE_CODE_SUBAGENT_MODEL':'glm-5.3-flash','CLAUDE_CODE_EFFORT_LEVEL':'high',
        'CLAUDE_CODE_MAX_CONTEXT_TOKENS':'262144','CLAUDE_CODE_AUTO_COMPACT_WINDOW':'196608',
        'CLAUDE_CODE_MAX_OUTPUT_TOKENS':'65536','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'}
    command=['claude','-p','--verbose','--output-format','stream-json','--effort','high',
        '--dangerously-skip-permissions','--strict-mcp-config','--mcp-config',str(out/'mcp.json'),
        '--settings',str(out/'settings.json'),'--session-id',cfg['session_id'],
        '--tools','Read,Write,Edit,Glob,Grep','--include-hook-events',
        '--append-system-prompt',cfg['framing'],cfg['prompt']]
    with (out/'events.jsonl').open('w') as events,(out/'stderr.txt').open('w') as stderr:
        result=subprocess.run(command,env=env,cwd=project,stdout=events,stderr=stderr)
    (out/'exit.json').write_text(json.dumps({'exit_code':result.returncode,'session_id':cfg['session_id']}))
    return result.returncode
