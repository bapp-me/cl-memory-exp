import tempfile
from pathlib import Path
import unittest
from protocol import Boundary, apply_notepad, database_feedback, digest, jaccard, namespace, project_episode


class ProtocolTests(unittest.TestCase):
    def test_feedback_cannot_include_evaluator_only_fields(self):
        for correct, timed_out, exhausted in [(True, False, False), (False, False, False),
                                               (False, True, False), (False, False, True)]:
            result = database_feedback({'correct': correct, 'timed_out': timed_out,
                'budget_exceeded': exhausted, 'submitted_answer': 'candidate', 'num_queries': 15,
                'ground_truth': 'SECRET_GOLD', 'sql': 'SECRET_REFERENCE_SQL'}, 1)
            self.assertNotIn('SECRET', result)
            self.assertIn('15', result)

    def test_notepad_replacement_null_and_clear(self):
        self.assertEqual(apply_notepad('old', {'action': 'QUERY', 'notepad_update': None}), ('old', {'action': 'QUERY'}))
        self.assertEqual(apply_notepad('old', {'notepad_update': ''}), ('', {}))
        self.assertEqual(apply_notepad('old', {'notepad_update': 'new'}), ('new', {}))
        with self.assertRaises(ValueError): apply_notepad('old', {'notepad_update': {'append': 'bad'}})

    def episode(self, ns, i):
        return project_episode(namespace=ns, index=i, instance_id=str(i), prompt='same query',
            assistant_text=['public'], tools=[{'action': {'action': 'QUERY', 'content': '.tables'},
            'observation': 'table', 'hidden_reasoning': 'SECRET'}], feedback='done')

    def test_future_and_cross_environment_and_cross_method_rejected(self):
        db = namespace('pi_jaccard', 1, 'database_exploration')
        code = namespace('pi_jaccard', 1, 'codebase_adaptation')
        other = namespace('pi_notepad', 1, 'database_exploration')
        for bad in [self.episode(code, 0), self.episode(other, 0), self.episode(db, 5)]:
            with self.assertRaises(ValueError): jaccard([bad], 'same', namespace=db, current_index=5)
        self.assertNotIn('SECRET', str(self.episode(db, 0)))

    def test_tie_break_newest_then_chronological(self):
        ns = namespace('pi_jaccard', 1, 'database_exploration')
        sources, _ = jaccard([self.episode(ns, i) for i in range(5)], 'same query', namespace=ns, current_index=5)
        self.assertEqual([x['episode']['index'] for x in sources], [2, 3, 4])

    def test_crash_resume_preserves_submission_and_blocks_future(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'state.json'
            b = Boundary(p, 'pi_none/r1/database_exploration')
            b.start(0, 'session1'); b.freeze({'answer': 'fixed'}, 'watermark-final')
            resumed = Boundary(p, 'pi_none/r1/database_exploration')
            with self.assertRaises(RuntimeError): resumed.start(1, 'session2')
            with self.assertRaises(RuntimeError): resumed.freeze({'answer': 'changed'}, 'tail')
            self.assertEqual(resumed.state['pending']['submission'], {'answer': 'fixed'})
            for status in ['not_triggered', 'idle_ineligible', 'timeout', 'error', 'still_running', 'uncommitted_storage']:
                with self.assertRaises(RuntimeError): resumed.complete(status=status,
                    covered_watermark='watermark-final', jobs=[], memory_version='v1', durable=True)
            with self.assertRaises(RuntimeError): resumed.complete(status='completed_noop',
                covered_watermark='watermark-final', jobs=[], memory_version='v1', durable=True)
            resumed.complete(status='not_applicable', covered_watermark='watermark-final', jobs=[],
                memory_version=digest([]), durable=True, no_async_mechanism=True)
            with self.assertRaises(RuntimeError): resumed.start(1, 'session1')
            resumed.start(1, 'session2')


if __name__ == '__main__': unittest.main()
