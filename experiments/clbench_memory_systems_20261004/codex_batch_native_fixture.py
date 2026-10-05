"""Run inside a disposable native container; all model replies are local fixtures."""
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import sys
import threading
import uuid

sys.path.insert(0, '/runtime')
from codex_session import run
from codex_completion import schedule


def main():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            extraction = payload.get('text', {}).get('format', {}).get('type') == 'json_schema'
            consolidation = payload.get('client_metadata', {}).get('x-openai-subagent') == 'memory_consolidation'
            calls.append('extraction' if extraction else 'consolidation' if consolidation else 'sync')
            text = json.dumps({'raw_memory':'Offline fixture: durable native extraction.',
                              'rollout_summary':'Offline fixture summary; not a formal experiment result.',
                              'rollout_slug':'offline_batch_fixture'}) if extraction else 'ACK'
            ident='resp_'+uuid.uuid4().hex;mid='msg_'+uuid.uuid4().hex
            item={'type':'message','id':mid,'role':'assistant','status':'completed',
                  'content':[{'type':'output_text','text':text,'annotations':[]}]}
            response={'id':ident,'object':'response','status':'completed','model':'glm-5.3-flash',
                      'output':[item],'usage':{'input_tokens':10,'output_tokens':10,'total_tokens':20}}
            events=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}},
                    {'type':'response.output_item.added','output_index':0,'item':{**item,'status':'in_progress','content':[]}},
                    {'type':'response.content_part.added','item_id':mid,'output_index':0,'content_index':0,
                     'part':{'type':'output_text','text':'','annotations':[]}},
                    {'type':'response.output_text.delta','item_id':mid,'output_index':0,'content_index':0,'delta':text},
                    {'type':'response.output_text.done','item_id':mid,'output_index':0,'content_index':0,'text':text},
                    {'type':'response.output_item.done','output_index':0,'item':item},
                    {'type':'response.completed','response':response}]
            raw=''.join('data: '+json.dumps(e)+'\n\n' for e in events).encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    out=Path('/state/tasks/task-007');path=out/'input.json';cfg=json.loads(path.read_text())
    cfg.update(maintenance_only=True,gateway=f'http://127.0.0.1:{server.server_port}',gateway_token='offline-fixture',
               recover_format_error=False,retry_native_maintenance=False,retry_transport_maintenance=False,
               consolidation_schedule=schedule('codebase_adaptation',7))
    project=Path('/state/work');home=Path('/state/home/.codex')
    checks=[]
    def execute(label):
        path.write_text(json.dumps(cfg));before=len(calls)
        assert run(path,cfg,out,project)==0
        barrier=json.loads((out/'barrier-candidate.json').read_text())
        checks.append({'case':label,'calls':calls[before:],'status':barrier['status'],
                       'phase2_status':[j['status'] for j in barrier['phase2']]})
    execute('reuse_completed_extraction_without_model_request')
    assert not checks[-1]['calls']
    for database in home.glob('memories_*.sqlite'):
        with closing(sqlite3.connect(database)) as db:
            # Modify only this disposable fixture to make extraction eligible.
            db.execute("DELETE FROM jobs WHERE kind='memory_stage1' AND job_key=?",(cfg['session_id'],))
            db.execute('DELETE FROM stage1_outputs WHERE thread_id=?',(cfg['session_id'],));db.commit()
    execute('new_extraction_deferred_global_consolidation')
    assert checks[-1]['calls'].count('extraction')==1 and 'consolidation' not in checks[-1]['calls']
    cfg['consolidation_schedule']=schedule('codebase_adaptation',9)
    execute('batch_boundary_dispatches_one_global_consolidation')
    assert checks[-1]['calls'].count('consolidation')==1 and 'extraction' not in checks[-1]['calls']
    result={'status':'passed','external_model_calls':0,'simulated_responses':len(calls),'checks':checks,
            'scope':'Native scheduler and durable barriers only; mock writer is not memory-quality evidence.'}
    (out/'offline-batch-fixture.json').write_text(json.dumps(result))
    print(json.dumps(result),flush=True)
    server.shutdown()


if __name__=='__main__':main()
