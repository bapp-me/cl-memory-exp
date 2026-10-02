"""Reproduce the first atomic-retrieval diagnostic (including timestamp change)."""
import json
import re
from datetime import datetime,timedelta
from lab_common import ROOT,save_json

p=ROOT/'fixtures/mab6k'
history=json.loads((p/'history-2.json').read_text(encoding='utf-8'))
facts=[]
for s in history['sessions']:facts.extend(re.findall(r'^\d+\. .+$',s['messages'][0]['content'],flags=re.M))
assert len(facts)==455
sessions=[]
for i,f in enumerate(facts):
    assert f.startswith(str(i)+'. ')
    sessions.append({'id':f'mab6k-fact-{i}','date':(datetime(2025,1,1,10)+timedelta(minutes=i)).strftime('%Y/%m/%d (%a) %H:%M'),
                     'messages':[{'role':'user','content':f}]})
save_json(p/'history-atomic.json',{'sessions':sessions})
save_json(p/'atomic-manifest.json',{'diagnostic':'same 455 numbered facts, one searchable session per fact instead of two long messages',
    'source_text_unchanged':True,'target_answers_added':False,
    'note':'Changes retrieval granularity and presentation timestamps; serial-based recency rule and fact content are unchanged. No curation or model required to build this fixture.'})
