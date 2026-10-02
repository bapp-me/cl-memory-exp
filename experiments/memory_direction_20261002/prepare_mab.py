"""Small FactConsolidation probe: complete 6k pool, first five MH questions.

Uses fact-line boundaries and a 4096 cl100k token cap. This is an adaptation,
not the upstream sentence splitter or a reported official benchmark score.
"""
import json
import re
from pathlib import Path
import tiktoken

root=Path(__file__).resolve().parent
row=json.loads((root/'.cache/mab/conflict.json').read_text(encoding='utf-8'))[0]
enc=tiktoken.get_encoding('cl100k_base')
lines=[s for s in row['context'].splitlines() if re.match(r'^\d+\. ',s)]
chunks=[];chunk=[]
for line in lines:
    if chunk and len(enc.encode('\n'.join(chunk+[line])))>4096:chunks.append('\n'.join(chunk));chunk=[]
    chunk.append(line)
if chunk:chunks.append('\n'.join(chunk))
assert '\n'.join(chunks)=='\n'.join(lines)
dest=root/'fixtures/mab6k';dest.mkdir(parents=True,exist_ok=True)
rule=('This is a synthetic knowledge-pool benchmark. Answer only from the provided pool, even when it conflicts with real-world knowledge. '
      'Each fact has a serial number; a larger serial is newer and overrides an older conflicting fact about the same subject and relation. '
      'For multi-hop questions, resolve the newest fact separately at every hop. ')
sessions=[]
for i,c in enumerate(chunks):
    s={'id':f'mab6k-chunk-{i+1}','date':f'2025/01/0{i+1} ('+['Wed','Thu','Fri','Sat'][i]+') 10:00',
       'messages':[{'role':'user','content':rule+'\n\n'+c}]}
    sessions.append(s)
    (dest/f'history-{i+1}.json').write_text(json.dumps({'sessions':sessions},ensure_ascii=False,indent=2),encoding='utf-8')
    prompt=rule+'\n\nRead this next portion of the pool. You MUST use the native memory tool to save or update useful knowledge for later questions. Raw portions also remain available through session_search. You do not know the later questions. After saving, acknowledge briefly.\n\n'+c
    (dest/f'write-{i+1}.txt').write_text(prompt,encoding='utf-8')
cases=[]
for i,(q,a) in enumerate(zip(row['questions'][:5],row['answers'][:5])):
    question=rule+'\n\nUse memory/history as needed. Return JSON with answer (a concise string) and evidence (fact serials and the chain).\n\n'+q
    (dest/f'query-{i}.txt').write_text(question,encoding='utf-8')
    (dest/f'query-{i}-oracle.txt').write_text(question+'\n\nThe complete pool follows:\n'+row['context'],encoding='utf-8')
    cases.append({'index':i,'question_id':row['metadata']['qa_pair_ids'][i],'question':q,'answers':a})
(root/'results/mab-selection.json').write_text(json.dumps({'source':json.loads((root/'.cache/mab/provenance.json').read_text()),
    'facts':len(lines),'chunks':[{'tokens':len(enc.encode(c)),'lines':len(c.splitlines())} for c in chunks],
    'selection':'first five MH questions, chosen before running','cases':cases,
    'adaptation':'4096 cl100k tokens, whole numbered fact lines; native Hermes curated memory + FTS history'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'facts':len(lines),'chunks':len(chunks),'queries':len(cases)}))
