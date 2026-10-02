"""Check source, memory transformation, and the actual returned tool text."""
import json
from lab_common import ROOT,save_json

pool=json.loads((ROOT/'.cache/mab/conflict.json').read_text(encoding='utf-8'))[0]['context']
chain=[line for line in pool.splitlines() if line.startswith(('146. ','335. ','322. '))]
assert len(chain)==3
before=(ROOT/'results/runs/mab-ds-write1-r1/memory_after/MEMORY.md').read_text(encoding='utf-8')
after=(ROOT/'results/runs/mab-ds-write2-wide-r1/memory_after/MEMORY.md').read_text(encoding='utf-8')
result={'expected_chain':chain,'source_memory_had_author_update':'Our Mutual Friend Charles Darwin146' in before,
        'updated_memory_still_mentions_book':'Our Mutual Friend' in after,'runs':[]}
for name in ['mab-ds-q0-history-r1','mab-ds-q0-native-r1','mab-ds-q0-history-wide-r2','mab-ds-q0-native-wide-r2',
             'mab-ds-q0-atomic-history-r1','mab-ds-q0-atomic-native-r1']:
    r=json.loads((ROOT/'results/runs'/name/'hermes-result.json').read_text(encoding='utf-8'))
    outputs=[str(m.get('content','')) for m in r['messages'] if m.get('role')=='tool']
    result['runs'].append({'run_id':name,'tool_outputs':len(outputs),
        'outputs_with_new_author_fact':sum('146. The author of Our Mutual Friend is Charles Darwin' in s for s in outputs),
        'outputs_with_old_author_fact':sum('107. The author of Our Mutual Friend is Charles Dickens' in s for s in outputs),
        'outputs_flagging_content_truncation':sum('content_truncated' in s and 'true' in s for s in outputs),
        'final_response':r['final_response']})
result['scope']='Literal fact-string visibility audit on native session_search tool outputs. Raw database contains all facts; this does not audit full Hermes shell/filesystem fallbacks.'
save_json(ROOT/'results/mab-retrieval-audit.json',result)
print(json.dumps({k:v for k,v in result.items() if k!='runs'}))
