"""No paid requests. Negative controls test evaluator isolation and memory persistence."""
import json
import tempfile
import unittest
from pathlib import Path
from environment import Environment, grade
from make_tasks import build


class HarnessChecks(unittest.TestCase):
    def env(self, group, stage, mechanism='file', seed=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Environment(build(group, stage)[0], Path(tmp.name), mechanism, seed)

    def test_private_checks_not_visible_and_sql_readonly(self):
        e = self.env('01_units', 'a')
        self.assertTrue(e.call('read_file', {'path': '../checks/01_units/a.json'}).get('error'))
        self.assertTrue(e.call('sql', {'query': 'DELETE FROM orders'}).get('error'))
        self.assertEqual(e.call('sql', {'query': 'SELECT COUNT(*) FROM orders'})['rows'][0][0], 9)

    def test_quality_rejects_final_claim_without_action(self):
        e = self.env('05_update', 'c')
        c = build('05_update', 'c')[1]
        self.assertFalse(grade('{"answer":"updated"}', c, e.final_state())['success'])
        e.call('api', {'method': 'PUT', 'path': '/profile', 'body': {'timezone': 'Asia/Tokyo'}})
        self.assertFalse(grade('{"answer":"updated"}', c, e.final_state())['success'])
        e.call('api', {'method': 'PUT', 'path': '/profile', 'body': c['state']['profile']})
        self.assertTrue(grade('{"answer":"updated"}', c, e.final_state())['success'])

    def test_unsupported_patch_does_not_reset_profile(self):
        e = self.env('05_update', 'c')
        before = e.final_state()
        result = e.call('api', {'method': 'PATCH', 'path': '/profile', 'body': {'timezone': 'Asia/Tokyo'}})
        self.assertEqual(result['status'], 405)
        self.assertEqual(e.final_state(), before)

    def test_coverage_and_duplicate_join_negative_controls(self):
        e = self.env('02_coverage', 'c')
        wrong = e.call('sql', {'query': 'SELECT AVG(display_usd) FROM products'})['rows'][0][0]
        self.assertFalse(grade(json.dumps({'answer': wrong}), build('02_coverage', 'c')[1], {})['success'])
        e = self.env('03_join', 'c')
        wrong = e.call('sql', {'query': "SELECT SUM(amount_usd) FROM orders JOIN customer_tags USING(customer_id) WHERE tag LIKE 'vip-%'"})['rows'][0][0]
        self.assertFalse(grade(json.dumps({'answer': wrong}), build('03_join', 'c')[1], {})['success'])

    def test_memory_version_retrieval_isolation_and_limit(self):
        a = self.env('01_units', 'a', 'search')
        a.call('experience', {'op': 'put', 'id': 'units', 'content': 'v1 cents'})
        b = self.env('01_units', 'c', 'search', a.entries)
        b.call('experience', {'op': 'put', 'id': 'units', 'content': 'v1 cents; v2 dollars'})
        self.assertEqual(a.entries['units']['version'], 1)
        result = b.call('experience', {'op': 'search', 'query': 'dollars'})
        self.assertEqual(result['matches'][0]['version'], 2)
        self.assertTrue(b.call('experience', {'op': 'put', 'id': 'large', 'content': 'x' * 3201}).get('error'))
        self.assertNotIn('large', b.entries)

    def test_time_boundary_and_csv(self):
        e = self.env('08_csv', 'c')
        self.assertTrue(e.call('parse_csv', {'path': 'ledger.csv'}).get('error'))
        rows = e.call('parse_csv', {'path': 'ledger.csv', 'encoding': 'utf-16', 'delimiter': '\t', 'skip_lines': 2})['rows']
        self.assertEqual(sum(int(r['amount']) for r in rows if r['category'] == 'sales'), build('08_csv', 'c')[1]['answer'])
        self.assertEqual(build('09_timezone', 'c')[1]['answer'], 7)
        self.assertEqual(build('09_timezone', 'd')[1]['answer'], 9)

    def test_report_spec_precision_not_raw_storage(self):
        env, check = build('10_preference', 'a')
        raw = json.loads(env['files']['figures.json'])['value']
        report = dict(check['state']['report'], value=raw)
        self.assertTrue(grade('{"answer":"saved"}', check, {'report': report})['success'])
        report['decimals'] = 0
        self.assertFalse(grade('{"answer":"saved"}', check, {'report': report})['success'])


if __name__ == '__main__':
    unittest.main()
