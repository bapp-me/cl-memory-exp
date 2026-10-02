"""Two bounded connectivity calls using existing encrypted credentials."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'memory_direction_20261002'))
from smoke_api import request

def main():
    records = []
    for provider, model, endpoint in [
        ('deepseek', 'deepseek-flash', 'https://api.deepseek.com/chat/completions'),
        ('glm', 'glm-5.3-flash', 'https://api.z.ai/api/paas/v4/chat/completions'),
    ]:
        result = request(provider, endpoint, {
            'model': model, 'messages': [{'role': 'user', 'content': 'Reply with exactly OK.'}],
            'thinking': {'type': 'enabled'}, 'reasoning_effort': 'high', 'max_tokens': 512,
        })
        records.append(result)
        (ROOT / 'records/model-connectivity.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'provider': provider, 'status': result['status'],
                          'returned_model': result.get('data', {}).get('model'),
                          'usage': result.get('data', {}).get('usage'),
                          'error': result.get('error')}, ensure_ascii=True), flush=True)

if __name__ == '__main__':
    main()
