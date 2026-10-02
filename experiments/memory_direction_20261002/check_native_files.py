"""Check the native file backend and path guard without model calls."""
import json
import os
import sys
from lab_common import ROOT,save_json

work=ROOT/'workspaces/native-file-check';work.mkdir(exist_ok=True)
home=ROOT/'.runtime/hermes-profiles/native-file-check';home.mkdir(parents=True,exist_ok=True)
os.environ.update({'HERMES_HOME':str(home),'HERMES_RUNTIME_DIR':str(ROOT/'.runtime/hermes-tools'),
                   'HERMES_GIT_BASH_PATH':r'D:\Git\bin\bash.exe','TERMINAL_CWD':str(work),
                   'LOCALAPPDATA':str(ROOT/'.runtime/hermes-localappdata')})
sys.path.insert(0,str(ROOT/'.runtime/hermes-source'));os.chdir(work)
(work/'probe.txt').write_text('line one\nsecond line: VERIFIED_PROBE\nthird line\n',encoding='utf-8')
from native_archive_files import register_archive_files
from tools.registry import registry
register_archive_files(work,ROOT/'results/native-file-check-calls.jsonl')
out=[]
for name,args in [('read_file',{'path':str(work/'probe.txt'),'offset':2,'limit':1}),
                   ('search_files',{'path':str(work),'pattern':'VERIFIED_PROBE'}),
                   ('read_file',{'path':str(ROOT/'.private/credentials.json')})]:
    handler=registry._lookup(name,None).handler
    response=handler(args,task_id='native-file-check')
    out.append({'name':name,'arguments':args,'response':response})
assert 'VERIFIED_PROBE' in out[0]['response'], out[0]['response']
assert 'VERIFIED_PROBE' in out[1]['response'], out[1]['response']
assert 'limited to' in out[2]['response']
save_json(ROOT/'results/native-file-check.json',{'success':True,'checks':out})
print(json.dumps({'read':True,'search':True,'outside_denied':True}))
