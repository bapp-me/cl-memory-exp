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
    if cfg['framework'] == 'codex':
        from codex_session import run
        return run(path, cfg, out, project)
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
        if cfg.get('enforce_action_schema'):
            from business_mcp import SCHEMA
            command[-1:-1]=['--json-schema',json.dumps(SCHEMA)]
        budget=cfg.get('output_limit',16384)
        continuations=[]
        while True:
            with (out / 'events.jsonl').open('a') as stdout, (out / 'stderr.txt').open('a') as stderr:
                result = subprocess.run(command, env=env, cwd=project, stdout=stdout, stderr=stderr)
            events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()]
            results=[e for e in events if e.get('type')=='result']
            if not results: break
            latest=results[-1]
            if latest.get('stop_reason') in {'max_tokens','length'}:
                if budget>=131072: raise RuntimeError('Provider maximum output exhausted')
                from native_budget import grow
                receipt=grow(cfg,budget); budget=receipt['output_limit']
                env['CLAUDE_CODE_MAX_OUTPUT_TOKENS']=str(budget)
                env['CLAUDE_CODE_AUTO_COMPACT_WINDOW']=str(receipt['compression_threshold'])
                next_prompt='Continue the same instance using its existing history and business state.'
                continuations.append({'kind':'output_budget','result_index':len(results)-1,**receipt})
            else:
                observed_path=out/'last-business-result.json'
                observed=json.loads(observed_path.read_text()) if observed_path.exists() else {}
                if observed.get('instance_complete'): break
                if latest.get('is_error'): break
                final_action=latest.get('structured_output')
                if final_action is None: final_action=json.loads(latest['result'])
                required={'action','content'} if cfg['environment']=='database_exploration' else {'command'}
                if not isinstance(final_action,dict) or not required<=final_action.keys():
                    raise RuntimeError('Native final response has no official action')
                from business_mcp import action
                observed=action(final_action,'final-json-'+str(len(results)))
                next_prompt=json.dumps(observed)
                continuations.append({'kind':'official_final_json_action','result_index':len(results)-1,
                    'action':final_action,'observation':observed})
            (out/'continuations.json').write_text(json.dumps(continuations))
            # Resume the exact same native session and existing business state.
            command=command[:-1]
            if '--session-id' in command:
                index=command.index('--session-id'); command[index]='--resume'
            command.append(next_prompt)
        (out / 'exit.json').write_text(json.dumps({'exit_code': result.returncode, 'session_id': cfg['session_id']}))
        return result.returncode
    raise ValueError('Framework adapter not accepted')


if __name__ == '__main__': sys.exit(main())
