"""Offline fault fixtures: a retry is not a new business result or zero cost."""
import json
from pathlib import Path
import tempfile
import unittest
from native_evidence import usage_for, validate_attempt_accounting


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'requests').mkdir()
        self.add('success', {'model': 'glm-5.3-flash', 'usage': {'prompt_tokens': 100, 'completion_tokens': 10},
                             'choices': [{'finish_reason': 'stop'}]})

    def tearDown(self):
        self.temp.cleanup()

    def add(self, ident, body=None, phase='finished', status=200, error=None, model='glm-5.3-flash'):
        stem = self.root/'requests'/ident
        stem.with_suffix('.request.json').write_text(json.dumps({'model': model}), encoding='utf-8')
        stem.with_suffix('.attempt.json').write_text(json.dumps({'attempt_id': ident, 'protocol': 'chat',
            'phase': phase, 'http_status': status, 'error': error}), encoding='utf-8')
        if body is not None:
            stem.with_suffix('.response.bin').write_text(body if isinstance(body, str) else json.dumps(body), encoding='utf-8')

    def check(self):
        return validate_attempt_accounting(self.root, usage_for(self.root))

    def test_transport_timeout_preserved_without_usage(self):
        self.add('timeout', phase='failed', status=None, error='TimeoutError')
        result = self.check()
        self.assertEqual(result['failed_attempts_with_unknown_usage'], ['timeout'])
        self.assertIsNone(next(a for a in usage_for(self.root) if a['attempt_id'] == 'timeout')['usage'])

    def test_http_200_unframed_provider_error_is_not_success(self):
        self.add('server-error', 'data: {"choices":[]}\n\n{"error":{"code":"500","message":"Operation failed"}}')
        self.assertEqual(self.check()['failed_attempts_with_unknown_usage'], ['server-error'])

    def test_http_500_keeps_unknown(self):
        self.add('server-error', {'error': {'message': 'unavailable'}}, status=500)
        self.assertEqual(len(self.check()['failed_attempts_with_unknown_usage']), 1)

    def test_in_flight_blocks_boundary(self):
        self.add('pending', phase='started', status=None)
        with self.assertRaisesRegex(RuntimeError, 'in flight'):
            self.check()

    def test_success_missing_usage_blocks_boundary(self):
        self.add('unmetered', {'model': 'glm-5.3-flash', 'choices': [{'finish_reason': 'stop'}]})
        with self.assertRaisesRegex(RuntimeError, 'lacks verifiable usage'):
            self.check()

    def test_model_fallback_blocks_even_on_failure(self):
        self.add('fallback', {'error': {'message': 'failed'}}, status=500, model='other-model')
        with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
            self.check()


if __name__ == '__main__': unittest.main()
