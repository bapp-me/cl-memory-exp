"""Use Hermes AIAgent's native loop and memory with a registered SQL tool.

Run with the official PM-selected Python, not the initial experiment venv.
Task tools and native memory are exposed; optional native read/search tools
are confined to the run workspace. No arbitrary shell or filesystem access.
"""
import argparse
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from lab_common import ROOT, get_secret, save_json
from api_proxy import RecordingProxy
from sql_backend import execute_query

MODELS={'deepseek':('deepseek-flash','https://api.deepseek.com/anthropic'),
        'glm':('glm-5.3-flash','https://api.z.ai/api/anthropic')}


def run(a):
    prompt_file=Path(a.prompt_file).resolve() if a.prompt_file else None
    history_file=Path(a.history_file).resolve() if a.history_file else None
    result_dir=ROOT/'results/runs'/a.run_id
    if result_dir.exists():raise FileExistsError(a.run_id)
    result_dir.mkdir(parents=True)
    work=ROOT/'workspaces'/a.run_id;work.mkdir(parents=True)
    home=ROOT/'.runtime/hermes-profiles'/a.run_id;home.mkdir(parents=True)
    os.environ.update({'HERMES_HOME':str(home),'HERMES_RUNTIME_DIR':str(ROOT/'.runtime/hermes-tools'),
        'LOCALAPPDATA':str(ROOT/'.runtime/hermes-localappdata'),'UV_CACHE_DIR':str(ROOT/'.cache/hermes-uv'),
        'HERMES_TELEMETRY_ENABLED':'false','PYTHONUTF8':'1','TERMINAL_CWD':str(work),
        'HERMES_GIT_BASH_PATH':r'D:\Git\bin\bash.exe'})
    memory_dir=home/'memories';memory_dir.mkdir()
    if a.memory_from:
        for p in (ROOT/'results/runs'/a.memory_from/'memory_after').glob('*.md'):shutil.copy2(p,memory_dir/p.name)
    before=result_dir/'memory_before';before.mkdir()
    for p in memory_dir.glob('*.md'):shutil.copy2(p,before/p.name)
    enabled=a.mode=='native' or a.write_memory
    # Keep normal memory caps and native prompts. Bound request costs separately.
    (home/'config.yaml').write_text('memory:\n  memory_enabled: '+str(enabled).lower()+'\n  user_profile_enabled: false\n',encoding='utf-8')
    sys.path.insert(0,str(ROOT/'.runtime/hermes-source'))
    os.chdir(work)
    from tools.registry import registry
    schema={'name':'query','description':'Execute one read-only SQLite query to inspect schema/data or calculate an answer. sqlite_master and schema PRAGMAs are available. At most 50 rows are returned; use aggregation or LIMIT. SQL errors are returned for repair.',
        'parameters':{'type':'object','properties':{'sql':{'type':'string'}},'required':['sql']}}
    registry.register(name='query',toolset='lab_sql',schema=schema,
        handler=lambda args,**kw:json.dumps(execute_query(args['sql'],ROOT/'.cache/clbench/products.db',result_dir/'sql.jsonl'),ensure_ascii=False))
    from run_agent import AIAgent
    if a.archive_files:
        from native_archive_files import register_archive_files
        register_archive_files(work,result_dir/'archive-file-tools.jsonl')
    session_db=None
    if history_file:
        from hermes_state import SessionDB
        from datetime import datetime,timezone,timedelta
        session_db=SessionDB(home/'state.db')
        history=json.loads(history_file.read_text(encoding='utf-8'))
        if a.archive_files:
            archive=work/'history';archive.mkdir()
            for i,s in enumerate(history['sessions']):
                (archive/f'{i+1:03d}.txt').write_text('Session: '+s['id']+'\nDate: '+s['date']+'\n\n'+'\n\n'.join(m['role']+':\n'+m['content'] for m in s['messages']),encoding='utf-8',newline='\n')
        for s in history['sessions']:
            # The dataset gives naive wall times. Preserve them in this host's
            # Asia/Hong_Kong display instead of shifting them by eight hours.
            stamp=datetime.strptime(s['date'],'%Y/%m/%d (%a) %H:%M').replace(tzinfo=timezone(timedelta(hours=8))).timestamp()
            session_db.create_session(s['id'],'cli',profile_name='default')
            for i,m in enumerate(s['messages']):session_db.append_message(s['id'],m['role'],m['content'],timestamp=stamp+i)
            session_db.end_session(s['id'],'imported_archive')
            session_db._write_sql('UPDATE sessions SET started_at=?,ended_at=? WHERE id=?',(stamp,stamp+len(s['messages']),s['id']))
    model,endpoint=MODELS[a.provider]
    key=get_secret(a.provider)
    proxy=RecordingProxy(endpoint,model,key,result_dir/'http',capture_only=a.capture_only,max_output_tokens=a.max_output_tokens,max_requests=a.max_requests,effort=a.effort).start()
    questions=json.loads((ROOT/'.cache/clbench/questions.json').read_text(encoding='utf-8'))
    question=next(q['question'] for q in questions if q['question_id']==a.question)
    prompt=('Answer this independent database-analysis request using the read-only SQLite query tool. '
        'Discover the schema and verify any assumptions needed. Do not ask the user to supply schema. '
        'You have access to a SQLite database that contains three separate product datasets covering different categories: '
        'office products, electronics, and musical instruments. Each dataset has its own set of tables. '
        'You will need to explore the schema to determine which tables belong to which product category. '
        'All data access must use the query tool. Return the final answer as JSON with fields answer and sql (the final computation query).\n\n'+question)
    if a.smoke:prompt='Use the database query tool to return the integer result of SELECT 1 AS probe. Reply with only the integer.'
    if prompt_file:prompt=prompt_file.read_text(encoding='utf-8')
    if a.archive_files:prompt+='\n\nComplete raw conversation archives are also available as text files in the workspace history/ directory. Native read_file and search_files tools can inspect them if useful.'
    if a.mode=='native':prompt+='\n\nPrior experience is available through native memory if useful. Decide whether and what to use.'
    if a.write_memory and not prompt_file:prompt+=('\n\nBefore your final answer, you MUST use the memory tool to save reusable findings from your actual observations. '
        'Record scope and evidence, distinguish inference from verification, and exclude the numerical answer to this request. '
        'Do not invent a fact if not observed. This persistence step is required even if the note says no reusable fact was confirmed.')
    save_json(result_dir/'input.json',{'provider':a.provider,'model':model,'endpoint':endpoint,'question_id':a.question,
        'mode':a.mode,'write_memory':a.write_memory,'memory_from':a.memory_from,'prompt':prompt,'agent':'Hermes 07ab19b0',
        'protocol':'native-hermes-text-memory-v2' if prompt_file else 'clbench-derived-hermes-v1','capture_only':a.capture_only,'skip_background_review':True,
        'task_kind':'text_memory' if prompt_file else 'sql','effort':a.effort,
        'prompt_file':str(prompt_file) if prompt_file else None,'history_file':str(history_file) if history_file else None,
        'history_timestamp_interpretation':'Asia/Hong_Kong; preserve dataset wall time',
        'archive_files':a.archive_files,
        'provider_adapter':{'thinking':'enabled','effort':a.effort,'max_output_tokens':a.max_output_tokens,'max_requests':a.max_requests}})
    start=time.monotonic();result={};error=None;agent=None
    save_json(result_dir/'process.json',{'pid':os.getpid(),'status':'running'})
    try:
        agent=AIAgent(base_url=proxy.url,api_key='local-experiment-proxy',provider='custom',api_mode='anthropic_messages',
            model=model,enabled_toolsets=([] if prompt_file else ['lab_sql'])+(['memory'] if enabled else [])+(['session_search'] if history_file else [])+(['lab_files'] if a.archive_files else []),max_iterations=a.max_requests,
            max_tokens=a.max_output_tokens,reasoning_config={'enabled':True,'effort':a.effort},quiet_mode=True,
            skip_context_files=True,skip_memory=not enabled,skip_background_review=True,
            save_trajectories=True,run_budget_seconds=480,cwd=str(work),session_db=session_db)
        save_json(result_dir/'exposed-tools.json',agent.tools)
        result=agent.run_conversation(prompt)
    except Exception:
        error=traceback.format_exc().replace(key,'[REDACTED]')
        (result_dir/'error.txt').write_text(error,encoding='utf-8')
    finally:
        if agent:
            try:agent.close()
            except Exception:pass
        if session_db:
            try:session_db.close()
            except Exception:pass
        proxy.close()
    elapsed=round(time.monotonic()-start,3)
    # Preserve the native return object, including messages/tool calls and usage.
    save_json(result_dir/'hermes-result.json',result)
    snapshot=result_dir/'memory_after';snapshot.mkdir()
    for p in memory_dir.glob('*.md'):shutil.copy2(p,snapshot/p.name)
    summary={'run_id':a.run_id,'seconds':elapsed,'agent':'Hermes 07ab19b0','error':error,
        'memory_files':[p.name for p in snapshot.glob('*.md')],'result':result}
    save_json(result_dir/'summary.json',summary)
    save_json(result_dir/'process.json',{'pid':os.getpid(),'status':'finished','error':bool(error)})
    print(json.dumps({'run_id':a.run_id,'seconds':elapsed,'memory_files':summary['memory_files'],'error':error,
        'result_keys':list(result),'final_response':result.get('final_response')},ensure_ascii=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--provider',choices=MODELS,required=True)
    p.add_argument('--question',type=int,default=11);p.add_argument('--run-id',required=True)
    p.add_argument('--mode',choices=['none','native'],default='none');p.add_argument('--memory-from')
    p.add_argument('--write-memory',action='store_true');p.add_argument('--capture-only',action='store_true');p.add_argument('--smoke',action='store_true')
    p.add_argument('--prompt-file');p.add_argument('--history-file')
    p.add_argument('--max-output-tokens',type=int,default=8192)
    p.add_argument('--max-requests',type=int,default=24)
    p.add_argument('--archive-files',action='store_true')
    p.add_argument('--effort',choices=['low','high'],default='high')
    run(p.parse_args())
