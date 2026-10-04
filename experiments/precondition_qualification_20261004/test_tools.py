"""Tooling tests use only synthetic responses and an explicit loopback server."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import model_gate

ROOT = Path(__file__).parent

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.temp.name)/'demo'
        subprocess.run([sys.executable, str(ROOT/'probe.py'), '--out', str(cls.data)],
                       check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_parser(self):
        self.assertEqual(model_gate.parse_decision({'choices':[{'message':{'content':'{"decision":"inspect"}'}}]}),'inspect')
        with self.assertRaises(ValueError):
            model_gate.parse_decision({'choices':[{'message':{'content':'{"decision":"maybe"}'}}]})

    def test_public_boundary(self):
        with self.assertRaises(ValueError):
            model_gate.make_messages({'shape':'leak'}, [], 'current')
        current = model_gate.make_messages({'case_id':'x'}, [{'text':'history only'}], 'current')
        self.assertNotIn('history only', json.dumps(current))

    def test_endpoint(self):
        model_gate.endpoint_ok('https://example.com/v1/chat/completions')
        model_gate.endpoint_ok('http://127.0.0.1:1/test')
        for url in ['http://example.com/v1', 'https://secret@example.com/v1', 'https://example.com/v1?key=secret']:
            with self.assertRaises(ValueError):
                model_gate.endpoint_ok(url)

    def test_budget_and_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            bad = subprocess.run([sys.executable,str(ROOT/'model_gate.py'),'--data',str(self.data),'--run-dir',d+'/bad','--max-calls','1'],capture_output=True)
            self.assertNotEqual(bad.returncode,0)
            self.assertFalse(Path(d+'/bad').exists())
            good = subprocess.run([sys.executable,str(ROOT/'model_gate.py'),'--data',str(self.data),'--run-dir',d+'/dry'],capture_output=True)
            self.assertEqual(good.returncode,0,good.stderr)
            self.assertEqual(len(list(Path(d+'/dry').glob('*.request.json'))),16)
            self.assertFalse(Path(d+'/dry/results.jsonl').exists())

    def run_fixture(self, status):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append(payload)
                data=json.dumps({'model':'fixture-not-a-model','choices':[{'message':{'content':'{"decision":"inspect"}'},'finish_reason':'stop'}]}).encode()
                self.send_response(status); self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        server=HTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                env=dict(os.environ,EXPERIMENT_API_KEY='FIXTURE-ONLY-FAKE-KEY',MEMORY_GATE_ENDPOINT=f'http://127.0.0.1:{server.server_port}/fixture')
                run=subprocess.run([sys.executable,str(ROOT/'model_gate.py'),'--data',str(self.data),'--run-dir',d+'/run','--model','fixture-not-a-model','--execute'],env=env,capture_output=True,timeout=15)
                records=[json.loads(x) for x in Path(d+'/run/results.jsonl').read_text().splitlines()]
                self.assertNotIn('FIXTURE-ONLY-FAKE-KEY', ''.join(p.read_text() for p in Path(d+'/run').iterdir()))
                if status==200:
                    self.assertEqual(run.returncode,0,run.stderr)
                    self.assertEqual(len(records),16)
                    score=subprocess.run([sys.executable,str(ROOT/'score_model_gate.py'),'--data',str(self.data),'--run-dir',d+'/run'],capture_output=True,timeout=10)
                    self.assertEqual(score.returncode,0,score.stderr)
                    obj=json.loads(score.stdout)
                    self.assertEqual(obj['counts']['unknown_usage_attempts'],16)
                    self.assertEqual(obj['counts'].get('caught_unsafe',0),0)
                    self.assertEqual(obj['counts'].get('allowed_safe',0),0)
                    self.assertEqual(obj['counts']['unsafe_abstentions']+obj['counts']['safe_abstentions'],16)
                else:
                    self.assertNotEqual(run.returncode,0)
                    self.assertEqual(len(records),1)
                    self.assertEqual(records[0]['http_status'],status)
        finally:
            server.shutdown();server.server_close();worker.join()
        return seen

    def test_mock_transport_and_abstention(self):
        self.assertEqual(len(self.run_fixture(200)),16)

    def test_http_error_stops_without_retry(self):
        self.assertEqual(len(self.run_fixture(402)),1)

if __name__=='__main__':
    unittest.main(verbosity=2)
