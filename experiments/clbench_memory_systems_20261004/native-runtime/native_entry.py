"""Native CLI entry point inside an isolated, experiment-owned container."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    path = Path(sys.argv[1]); cfg = json.loads(path.read_text()); out = path.parent
    home = Path('/state/home'); project = Path('/state/work') / cfg.get('project_key', 'database')
    project.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'HOME': str(home), 'DISABLE_AUTOUPDATER': '1'}
    if cfg['framework'] == 'hermes':
        from hermes_session import run
        return run(path, cfg, out, project)
    if cfg['framework'] == 'claude':
        claude_home = home / '.claude'; claude_home.mkdir(exist_ok=True)
        env.update(CLAUDE_CONFIG_DIR=str(claude_home), ANTHROPIC_BASE_URL=cfg['gateway'],
            ANTHROPIC_AUTH_TOKEN=cfg['gateway_token'], ANTHROPIC_MODEL='glm-5.3-flash',
            ANTHROPIC_DEFAULT_OPUS_MODEL='glm-5.3-flash', ANTHROPIC_DEFAULT_SONNET_MODEL='glm-5.3-flash',
            ANTHROPIC_DEFAULT_HAIKU_MODEL='glm-5.3-flash', CLAUDE_CODE_SUBAGENT_MODEL='glm-5.3-flash',
            CLAUDE_CODE_MAX_CONTEXT_TOKENS='262144', CLAUDE_CODE_AUTO_COMPACT_WINDOW='245760',
            CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(cfg.get('output_limit', 16384)),
            CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', CLAUDE_CODE_EFFORT_LEVEL='high')
        settings = {'autoMemoryEnabled': True, 'model': 'glm-5.3-flash'}
        (out / 'settings.json').write_text(json.dumps(settings))
        mcp = {'mcpServers': {'clbench': {'command': 'python', 'args': ['/runtime/business_mcp.py', str(path)]}}}
        (out / 'mcp.json').write_text(json.dumps(mcp))
        command = ['claude', '-p', '--verbose', '--output-format', 'stream-json', '--effort', 'high',
            '--dangerously-skip-permissions', '--strict-mcp-config', '--mcp-config', str(out / 'mcp.json'),
            '--settings', str(out / 'settings.json'), '--session-id', cfg['session_id'],
            '--append-system-prompt', cfg['framing'], cfg['prompt']]
        with (out / 'events.jsonl').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
            result = subprocess.run(command, env=env, cwd=project, stdout=stdout, stderr=stderr)
        (out / 'exit.json').write_text(json.dumps({'exit_code': result.returncode, 'session_id': cfg['session_id']}))
        return result.returncode
    raise ValueError('Framework adapter not accepted')


if __name__ == '__main__': sys.exit(main())
