"""Fetch pinned public source and documentation for a read-only memory audit.

No agent installation, remote code execution, or model requests. Cached source
is ignored by Git. The manifest records hashes and fetch failures explicitly.
"""
import concurrent.futures
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache' / 'framework-memory'
PINS = {
    'openai/codex': '57ac6f51639f7cad705a48ac4bd8073034a2f150',
    'NousResearch/hermes-agent': '357f51c49106f47136caf9b01015467b7b633fe8',
    'openclaw/openclaw': '4d1890a3cdc3b8f31ac70bb63e19723fee0cc6a9',
}
FILES = {
    'openai/codex': [
        'codex-rs/memories/README.md',
        'codex-rs/memories/write/src/start.rs',
        'codex-rs/memories/write/src/phase1.rs',
        'codex-rs/memories/write/src/phase2.rs',
        'codex-rs/memories/write/src/guard.rs',
        'codex-rs/memories/write/src/lib.rs',
        'codex-rs/memories/write/templates/memories/stage_one_system.md',
        'codex-rs/ext/memories/templates/memories/read_path.md',
        'codex-rs/ext/memories/src/extension.rs',
        'codex-rs/model-provider/src/provider.rs',
        'codex-rs/protocol/src/protocol.rs',
        'codex-rs/rollout/src/lib.rs',
    ],
    'NousResearch/hermes-agent': [
        'agent/background_review.py', 'agent/memory_manager.py',
        'agent/system_prompt.py', 'run_agent.py',
        'tools/memory_tool.py', 'tools/session_search_tool.py',
        'hermes_cli/config_defaults.py',
        'website/docs/user-guide/features/memory.md',
        'website/docs/integrations/providers.md',
        'agent/turn_finalizer.py', 'agent/prompt_builder.py',
        'agent/conversation_loop.py',
        'agent/turn_context.py',
    ],
    'openclaw/openclaw': [
        'docs/concepts/memory.md', 'docs/concepts/dreaming.md',
        'src/agents/system-prompt.ts', 'src/agents/memory-prompt-prepare.ts',
        'src/auto-reply/reply/memory-flush.ts',
        'src/hooks/bundled/session-memory/HOOK.md',
        'extensions/memory-core/src/dreaming-cron.ts',
        'extensions/memory-core/index.ts',
        'docs/reference/templates/AGENTS.md',
        'docs/providers/zai.md',
        'extensions/memory-core/src/memory-tool-contract.ts',
        'docs/concepts/memory-search.md', 'docs/concepts/active-memory.md',
        'docs/concepts/active-memory/configuration.md',
        'docs/concepts/active-memory/how-it-works.md',
    ],
}
DOCS = {
    'codex-memories.md': 'https://learn.chatgpt.com/docs/customization/memories.md',
    'claude-memory.md': 'https://code.claude.com/docs/en/memory.md',
    'zai-codex.md': 'https://docs.z.ai/devpack/tool/codex.md',
    'zai-claude.md': 'https://docs.z.ai/devpack/tool/claude.md',
    'zai-cursor.md': 'https://docs.z.ai/devpack/tool/cursor.md',
    'zai-glm-5.3.md': 'https://docs.z.ai/guides/llm/glm-5.3.md',
    'zai-latest-model.md': 'https://docs.z.ai/devpack/latest-model.md',
}


def fetch(item):
    key, url = item
    path = CACHE / key
    record = {'cache_path': str(path.relative_to(ROOT)), 'url': url}
    try:
        request = Request(url, headers={'User-Agent': 'agent-memory-trigger-audit/1.0'})
        with urlopen(request, timeout=40) as response:
            raw = response.read(12 * 1024 * 1024 + 1)
            record['resolved_url'] = response.url
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError('Source exceeded 12 MiB cap')
        raw.decode('utf-8')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        record.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), status='fetched')
    except Exception as error:
        record.update(status='failed', error=str(error))
    return record


def main():
    items = [(f'{repo}/{path}', f'https://raw.githubusercontent.com/{repo}/{PINS[repo]}/{path}')
             for repo, paths in FILES.items() for path in paths]
    items += [(f'docs/{name}', url) for name, url in DOCS.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(fetch, items))
    result = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'repository_pins': PINS, 'sources': records,
        'model_calls': 0, 'agent_runs': 0,
        'limitations': [
            'Pinned upstream source is not proof that every packaged release has the same behavior.',
            'Vendor integration recipes are not a successful local GLM-5.3 compatibility test.',
            'Documentation and code describe triggers, not empirical write or recall probabilities.',
            'Cursor current memory implementation was not available for source inspection.',
        ],
    }
    (ROOT / '框架记忆机制来源核查.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'fetched': sum(x['status'] == 'fetched' for x in records),
                      'failed': [x for x in records if x['status'] == 'failed']}))


if __name__ == '__main__':
    main()
