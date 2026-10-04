"""Workflow tests: synthetic attestations and loopback responses, NOT evidence of model ability."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import qualification as q
from model_gate import ARMS, load_json, load_jsonl, write_json
from score_model_gate import evaluate

ROOT = Path(__file__).parent


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root/'cases'
        q.initialize(self.data)

    def tearDown(self):
        self.temp.cleanup()

    def fill_fixture(self):
        # Synthetic unit-test data only. Check validates attestations, not truth.
        for name in q.FILES:
            path = self.data/name
            path.write_text(path.read_text().replace('<FILL>', 'unit-test-only'), encoding='utf-8')
        incidents = load_json(self.data/'incidents.json')
        for i,r in enumerate(incidents): r['mechanism'] = f'fixture_mechanism_{i}'
        write_json(self.data/'incidents.json',incidents)
        truth = load_jsonl(self.data/'evaluator_cases.jsonl')
        for i,r in enumerate(truth):
            r['expected_by_arm'] = {a:('block' if i%4==0 else 'allow') for a in ARMS}
            if i%4==0: r['expected_by_arm']['current'] = 'inspect'
        q.dump_lines(self.data/'evaluator_cases.jsonl',truth)
        review = load_json(self.data/'review.json')
        review.update(approved=True,checks={k:True for k in q.CHECKS})
        write_json(self.data/'review.json',review)

    def plan(self):
        self.fill_fixture()
        plan = self.root/'plan'
        q.prepare(self.data,plan,'fixture-not-a-model')
        review = load_json(plan/'payload_review.json')
        review.update(approved=True,reviewer='unit-test',reviewed_at='fixture')
        write_json(plan/'payload_review.json',review)
        return plan

    def test_pending_templates_fail(self):
        with self.assertRaises(ValueError): q.validate(self.data)
        with self.assertRaises(ValueError): q.initialize(self.data)

    def test_structural_check_and_arm_evidence(self):
        self.fill_fixture()
        self.assertEqual(q.validate(self.data)['planned_calls'],48)
        truth = load_jsonl(self.data/'evaluator_cases.jsonl')
        truth[0]['expected_by_arm']['preflight'] = 'allow'
        q.dump_lines(self.data/'evaluator_cases.jsonl',truth)
        with self.assertRaises(ValueError): q.validate(self.data)

    def test_hidden_fields_rejected(self):
        self.fill_fixture()
        public = load_jsonl(self.data/'public_cases.jsonl')
        public[0]['current_state'] = {'gold':'do not send'}
        q.dump_lines(self.data/'public_cases.jsonl',public)
        with self.assertRaises(ValueError): q.validate(self.data)

    def test_plan_interleaves_and_excludes_private_truth(self):
        plan = self.plan()
        manifest = load_json(plan/'manifest.json')
        self.assertEqual(len(manifest['planned_keys']),48)
        for i in range(0,48,3):
            block = manifest['planned_keys'][i:i+3]
            self.assertEqual({r['arm'] for r in block},set(ARMS))
            self.assertEqual(len({(r['case_id'],r['repeat']) for r in block}),1)
        for path in plan.glob('*.request.json'):
            text = path.read_text()
            self.assertNotIn('expected_by_arm',text)
            self.assertNotIn('decision_policy',text)
        with self.assertRaises(ValueError): evaluate(self.data,plan)
        with self.assertRaises(ValueError): q.execute(self.data,plan,self.root/'no',False)

    def test_frozen_private_label_tampering_is_rejected(self):
        plan = self.plan()
        truth = load_jsonl(self.data/'evaluator_cases.jsonl')
        truth[0]['decision_basis'] = 'edited after freeze'
        q.dump_lines(self.data/'evaluator_cases.jsonl',truth)
        with self.assertRaises(ValueError): q.execute(self.data,plan,self.root/'no',True)
        self.assertFalse((self.root/'no').exists())

    def test_reviewed_request_tampering_is_rejected(self):
        plan = self.plan()
        path = next(plan.glob('*.request.json'))
        obj = load_json(path)
        obj['max_tokens'] += 1
        write_json(path,obj)
        with self.assertRaises(ValueError): q.execute(self.data,plan,self.root/'no',True)

    def test_unfinished_attempt_not_counted_as_free(self):
        plan = self.plan()
        manifest = load_json(plan/'manifest.json')
        manifest['execute'] = True  # A deliberately incomplete synthetic log, no HTTP.
        write_json(plan/'manifest.json',manifest)
        q.dump_lines(plan/'started.jsonl',[manifest['planned_keys'][0]])
        report = evaluate(self.data,plan)
        self.assertEqual(report['missing'],48)
        self.assertEqual(report['started_without_result'],1)
        self.assertEqual(report['counts']['unknown_usage_attempts'],1)
        self.assertFalse(report['technical_complete'])

    def test_all_arm_loopback_and_acceptance(self):
        plan, seen = self.plan(), []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body=json.dumps({'model':'fixture-not-a-model','usage':{'total_tokens':10},
                    'choices':[{'message':{'content':'{"decision":"inspect","evidence":"fixture"}'},
                                'finish_reason':'stop'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length',str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = HTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            run = self.root/'run'
            with mock.patch.dict(os.environ,{'EXPERIMENT_API_KEY':'UNIT-TEST-NOT-A-SECRET',
                         'MEMORY_GATE_ENDPOINT':f'http://127.0.0.1:{server.server_port}/fixture'}):
                q.execute(self.data,plan,run,True)
            q.accept(self.data,run)
            report = load_json(run/'score.json')
            self.assertEqual(len(seen),48)
            self.assertTrue(report['technical_complete'])
            self.assertEqual(report['counts']['inspect'],48)
            self.assertEqual(report['counts']['appropriate_inspect'],4)
            self.assertEqual(report['counts'].get('allowed_safe',0),0)
            self.assertEqual(report['counts'].get('caught_unsafe',0),0)
            self.assertEqual(report['provider_reported_known_total_tokens'],480)
            for path in run.iterdir():
                if path.is_file(): self.assertNotIn('UNIT-TEST-NOT-A-SECRET',path.read_text())
            self.assertTrue((run/'资格检查结果.md').exists())
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main(verbosity=2)
