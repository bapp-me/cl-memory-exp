"""Experiment primitives. Agent-visible history never includes evaluator records."""
from __future__ import annotations
import ast
import hashlib
import json
import os
import random
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request,urlopen

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache'
sys.path.insert(0, str(ROOT.parent / 'memory_direction_20261002'))
from lab_common import get_secret

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temp.replace(path)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def linux(path):
    p = Path(path).resolve().as_posix()
    return '/mnt/' + p[0].lower() + p[2:]

def sandbox(work, command, timeout=120, direct=False):
    # Caller can only supply a directory inside this experiment's private runtime.
    work=Path(work).resolve()
    if not work.is_relative_to((ROOT / '.runtime').resolve()):
        raise ValueError('Sandbox work must be experiment-private')
    broker_path=ROOT/'.runtime/sandbox-broker.json'
    if not direct and broker_path.exists():
        broker=json.loads(broker_path.read_text(encoding='utf-8'))
        req=Request(broker['url'],data=json.dumps({'work':str(work),'command':command,'timeout':timeout}).encode(),headers={'Content-Type':'application/json','X-Broker-Token':broker['token']})
        with urlopen(req,timeout=timeout+15) as response:return json.load(response)
    mount_root = ROOT / '.runtime/sandbox-root'
    mount_root.mkdir(parents=True, exist_ok=True)
    command=['/python/bin/python3.10' if c=='/usr/bin/python3' else c for c in command]
    cmd=['wsl.exe','-d','Ubuntu','--exec','unshare','-Urnmpf','sh',linux(ROOT/'sandbox.sh'),linux(mount_root),linux(work),'/home/fucak/.cache/agent-memory-plan-20261002/deps310','/home/fucak/.cache/agent-memory-plan-20261002/python310',*command]
    try:
        result=subprocess.run(cmd,capture_output=True,timeout=timeout)
        return {'returncode':result.returncode,'stdout':result.stdout.decode('utf-8',errors='replace')[-24000:],
                'stderr':result.stderr.decode('utf-8',errors='replace')[-24000:]}
    except subprocess.TimeoutExpired:
        return {'returncode':124,'stdout':'','stderr':'sandbox wall timeout'}

def grade_code(row, code):
    issue_path=ROOT/'records/scorer-issues.json'
    if issue_path.exists():
        issues=json.loads(issue_path.read_text(encoding='utf-8'))
        if issues['status']=='user_confirmed_exclude_from_scores_keep_execution' and any(x['id']==row['id'] and x['category']==row['category'] for x in issues['issues']):
            return {'correct':None,'scorable':False,'tests_run':None,'checks_executed':None,'reason':'pre-registered scorer defect; task retained, excluded from scores'}
    folder=ROOT/'.runtime/evaluators'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    # Hidden tests are introduced only AFTER submission in a different sandbox.
    class CountAssertions(ast.NodeTransformer):
        def visit_Assert(self,node):
            node.test=ast.Call(func=ast.Name(id='_eval_record_bool',ctx=ast.Load()),args=[node.test],keywords=[])
            return node
        def visit_Call(self,node):
            node=self.generic_visit(node)
            name=node.func.attr if isinstance(node.func,ast.Attribute) else ''
            if name.startswith('assert'):
                return ast.Subscript(value=ast.Tuple(elts=[ast.Call(func=ast.Name(id='_eval_tick',ctx=ast.Load()),args=[],keywords=[]),node],ctx=ast.Load()),slice=ast.Constant(1),ctx=ast.Load())
            return node
    test_tree=CountAssertions().visit(ast.parse(row['test_code']))
    test_code=ast.unparse(ast.fix_missing_locations(test_tree))
    compatibility='import unittest\nunittest.TestCase.assertEquals = unittest.TestCase.assertEqual\nunittest.TestCase.assertNotEquals = unittest.TestCase.assertNotEqual\n'
    counters='''
_eval_assert_count=0
def _eval_tick():
    global _eval_assert_count
    _eval_assert_count+=1
def _eval_record_bool(value):
    _eval_tick()
    return value
'''
    runner = compatibility+counters+code+'\n\n'+test_code+'''
\nif __name__ == '__main__':
    import unittest as _ut
    import inspect as _inspect
    for _name,_function in list(globals().items()):
        if _name.startswith('test_') and _inspect.isfunction(_function):
            _function()
    _suite = _ut.defaultTestLoader.loadTestsFromModule(__import__('__main__'))
    _result = _ut.TextTestRunner(verbosity=0).run(_suite)
    _count = _result.testsRun + _eval_assert_count
    print('EVALUATOR_RESULT=' + str(_count) + ':' + str(_result.wasSuccessful()) + ':' + str(_result.testsRun))
    raise SystemExit(0 if _result.wasSuccessful() and _count else 1)
'''
    (folder/'evaluate.py').write_text(runner,encoding='utf-8')
    result=sandbox(folder,['/bin/sh','-c','cd /work && python3 evaluate.py'])
    match=re.search(r'EVALUATOR_RESULT=(\d+):(True|False):(\d+)',result['stdout'])
    result['tests_run']=int(match.group(3)) if match else 0
    result['checks_executed']=int(match.group(1)) if match else 0
    result['correct']=bool(result['returncode']==0 and match and match.group(2)=='True' and int(match.group(1))>0)
    result['scorable']=bool(match) or result['returncode'] in (1,124)
    return result

def reference_module(row):
    # CodeEval's solution is a function-body completion, not a full module.
    # Some complex prompts concatenate prose and the import prefix without a newline.
    for match in re.finditer(r'\b(?:import|from|def)\s',row['problem']):
        candidate=row['problem'][match.start():]+row['solution']
        try:ast.parse(candidate)
        except SyntaxError:continue
        return candidate
    raise ValueError('Cannot reconstruct reference code prefix without editing task semantics')

def load_native_database_methods():
    source=(CACHE/'clbench/task.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    names={'_execute_sql','_format_results','_evaluate_answer'}
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DatabaseExploration')
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    sequence=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_build_schema_drift_question_sequence')
    ns={'sqlite3':sqlite3,'time':time,'re':re,'random':random,'Any':object,'MAX_QUERY_RESULT_ROWS':50,'SQL_QUERY_TIMEOUT_SECONDS':10}
    mod=ast.Module(body=[sequence,*methods],type_ignores=[])
    exec(compile(ast.fix_missing_locations(mod),'<pinned-native-database-methods>','exec'),ns)
    return ns

NATIVE=load_native_database_methods()
PROMPTS={}
exec(compile((CACHE/'clbench/src_tasks_database_exploration_prompts.py').read_text(encoding='utf-8'),'<pinned-native-prompts>','exec'),PROMPTS)

class Database:
    _execute_sql=NATIVE['_execute_sql']
    _format_results=NATIVE['_format_results']
    _evaluate_answer=NATIVE['_evaluate_answer']

    def __init__(self):
        pre=json.loads((CACHE/'clbench/data_database_exploration_questions.json').read_text(encoding='utf-8'))
        post=json.loads((CACHE/'clbench/data_database_exploration_questions_post_drift.json').read_text(encoding='utf-8'))
        self.rows=NATIVE['_build_schema_drift_question_sequence'](pre_questions=pre,post_questions=post,pre_drift_count=20,post_drift_count=20,seed=42,run_index=0)
        self._conn=None

    def start(self,index):
        if self._conn: self._conn.close()
        path=CACHE/'clbench'/('products.db' if index<20 else 'products_drifted.db')
        self._conn=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,check_same_thread=False)
        self._conn.execute('PRAGMA query_only=ON')
        # Deny alternate files and mutable PRAGMAs even if a model requests them.
        self._conn.set_authorizer(lambda action,a,b,c,d: sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK)
        self.row=self.rows[index];self.index=index;self.queries=0;self.submission=None

    def prompt(self):
        notice='NOTICE: The live database schema or contents may have changed since your earlier exploration. Inspect current metadata and data before relying on prior assumptions.\n\n' if self.index==20 else ''
        return notice+PROMPTS['QUESTION_TEMPLATE'].format(question_num=self.index+1,total=40,question_text=self.row['question'],budget=15,queries_used=0)

    def tool(self,name,args):
        if self.submission is not None: return {'submitted':True}
        if name=='QUERY':
            if self.queries>=15:
                self.submission=''
                return {'submitted':True,'feedback':'Query budget exhausted. No further attempts.'}
            self.queries+=1
            return {'observation':self._execute_sql(str(args['sql'])),'queries_used':self.queries,'queries_remaining':15-self.queries}
        if name=='ANSWER':
            self.submission=str(args['answer'])
            # Never format native gold-bearing feedback in agent-visible memory.
            correct=self._evaluate_answer(self.submission,self.row)
            return {'submitted':True,'feedback':'CORRECT' if correct else 'INCORRECT','queries_used':self.queries}
        return {'error':'Unknown tool'}

    def score(self):
        correct=self._evaluate_answer(self.submission or '',self.row)
        return {'correct':correct,'queries':self.queries,'reward':1-self.queries/15 if correct else 0.,'scorable':True}

def schema(name,description,field):
    return {'name':name,'description':description,'parameters':{'type':'object','properties':{field:{'type':'string'}},'required':[field],'additionalProperties':False}}

DB_TOOLS=[schema('QUERY','Run one read-only SQLite query or .tables/.schema. Each call counts toward 15 queries.','sql'),schema('ANSWER','Submit the final answer once. This ends the task.','answer')]
CODE_TOOLS=[schema('PYTHON','Execute Python in the current task sandbox for your own tests. Hidden tests unavailable.','code'),schema('SUBMIT','Submit the complete Python module implementing the requested function. Ends this task.','code')]

class CodeTask:
    def __init__(self,row,work):
        self.row=row;self.work=work;self.submission=None;self.calls=0
        work.mkdir(parents=True,exist_ok=True)
    def tool(self,name,args):
        if self.submission is not None:return {'submitted':True}
        if name=='SUBMIT':
            self.submission=str(args['code']);return {'submitted':True,'feedback':'Submission recorded. Hidden correctness is not available.'}
        if name=='PYTHON':
            self.calls+=1
            if self.calls>15:return {'error':'Python execution budget exhausted. Submit now.'}
            (self.work/'scratch.py').write_text(str(args['code']),encoding='utf-8')
            return sandbox(self.work,['/bin/sh','-c','cd /work && python3 scratch.py'])
        return {'error':'Unknown tool'}

def memory_context(history,method,prompt):
    if method=='no_memory':return []
    candidates=list(history)
    if method=='episodic_retrieval':
        query=set(re.findall(r'\w+',prompt.lower()))
        ranked=[]
        for i,e in enumerate(history):
            words=set(re.findall(r'\w+',e['text'].lower()))
            score=len(query & words)/(len(query | words) or 1)
            ranked.append((score,i,e))
        candidates=[e for _,_,e in sorted(ranked,reverse=True)[:3]]
        candidates.sort(key=lambda e:e['sequence'])
    elif method!='bounded_icl':raise ValueError(method)
    # 48k UTF-8 bytes, whole episodes only, deterministic oldest removal.
    while candidates and len(json.dumps(candidates,ensure_ascii=False).encode())>48000:
        candidates.pop(0)
    return candidates

def run_pi(provider,prompt,history,method,task,tools,out,injection_override=None):
    out.mkdir(parents=True,exist_ok=True)
    token=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.headers.get('X-Run-Token')!=token:
                self.send_error(403);return
            try:
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                value=task.tool(payload['name'],payload['args'])
            except Exception as e:value={'error':type(e).__name__+': '+str(e)}
            data=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
    server=HTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    selected=memory_context(history,method,prompt) if injection_override is None else injection_override
    if len(json.dumps(selected,ensure_ascii=False).encode())>48000:
        raise ValueError('Diagnostic injection exceeds registered memory byte budget')
    save(out/'memory-before.json',history);save(out/'injected.json',selected)
    cfg={'provider':provider,'model':'deepseek-flash' if provider=='deepseek' else 'glm-5.3-flash',
         'base_url':'https://api.deepseek.com' if provider=='deepseek' else 'https://api.z.ai/api/paas/v4',
         'system':getattr(task,'system_hint','Complete the current task using the declared tools. Submit once.')+' Previous episodes below are your own fallible observations, not verified answers. Use only relevant experience.\n'+json.dumps(selected,ensure_ascii=False),
         'prompt':prompt,'tools':tools,'tool_url':f'http://127.0.0.1:{server.server_port}', 'tool_token':token,
         'max_turns':getattr(task,'max_turns',18),'timeout_seconds':getattr(task,'timeout_seconds',600),
         'response_timeout_ms':getattr(task,'response_timeout_ms',60000 if isinstance(task,Database) else 180000),
         'transport_file':str(out/'transport.jsonl'),
         'events_file':str(out/'events.jsonl'),'requests_file':str(out/'requests.jsonl'),'result_file':str(out/'pi-result.json')}
    input_path=ROOT/'.runtime/inputs'/(uuid.uuid4().hex+'.json');save(input_path,cfg)
    env=os.environ.copy();env['EXPERIMENT_API_KEY']=get_secret(provider)
    started=time.monotonic()
    try:
        process=subprocess.run(['node',str(ROOT/'pi_runner.mjs'),str(input_path)],capture_output=True,env=env,timeout=cfg['timeout_seconds']+30)
    finally:
        server.shutdown();server.server_close()
    result=json.loads((out/'pi-result.json').read_text(encoding='utf-8'))
    # Memory holds own observable actions/results, not hidden scores or model reasoning.
    visible=[]
    for message in result['messages']:
        if message['role']=='assistant':
            visible.extend(c for c in message.get('content',[]) if c.get('type') in ('text','toolCall'))
        elif message['role']=='toolResult':visible.append({'tool':message.get('toolName'),'content':message.get('content')})
    episode={'sequence':len(history),'text':json.dumps({'task':prompt,'trajectory':visible},ensure_ascii=False)}
    assistants=[m for m in result['messages'] if m['role']=='assistant']
    usage={field:sum(m.get('usage',{}).get(field,0) for m in assistants) for field in ['input','output','cacheRead','cacheWrite','totalTokens']}
    record={'seconds':round(time.monotonic()-started,3),'usage':usage,'turns':result['turns'],'tool_calls':result['toolCalls'],
            'error':result['error'],'stop_reason':result['stop_reason'],'submitted':task.submission is not None,
            'response_timed_out':result['responseTimedOut'],'context_exceeded':result['contextExceeded'],
            'memory_hash':digest(history),'injected_hash':digest(selected),'node_returncode':process.returncode}
    save(out/'execution.json',record)
    return episode,record
