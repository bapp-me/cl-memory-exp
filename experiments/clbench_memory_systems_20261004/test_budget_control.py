import json
from pathlib import Path
import tempfile
import unittest
from budget_control import authorize_growth


class BudgetControlTest(unittest.TestCase):
    def make(self, path, *, output=16384, finish='length', phase='finished'):
        requests=path/'requests'; requests.mkdir(exist_ok=True)
        (requests/'a.request.json').write_text('{}')
        (requests/'a.attempt.json').write_text(json.dumps({'attempt_id':'a','protocol':'chat','phase':phase,'http_status':200}))
        (requests/'a.response.bin').write_text('data: '+json.dumps({'model':'glm-5.3-flash',
            'choices':[{'finish_reason':finish}],'usage':{'completion_tokens':output}})+'\n\ndata: [DONE]\n')
    def test_length_exhaustion_and_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); self.make(path)
            route,receipt=authorize_growth(path,{'output_limit':16384},16384)
            self.assertEqual(receipt,{'previous_limit':16384,'output_limit':32768,'context_window':262144,
                'compression_threshold':229376,'evidence_attempt_id':'a'})
            with self.assertRaises(ValueError): authorize_growth(path,route,32768)
    def test_context_exhaustion_is_not_output_exhaustion(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); self.make(path,output=120)
            with self.assertRaises(ValueError): authorize_growth(path,{'output_limit':16384},16384)
    def test_normal_stop_does_not_raise_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); self.make(path,finish='stop')
            with self.assertRaises(ValueError): authorize_growth(path,{'output_limit':16384},16384)
    def test_incomplete_transport_does_not_raise_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); self.make(path,phase='started')
            with self.assertRaises(ValueError): authorize_growth(path,{'output_limit':16384},16384)
    def test_responses_string_deltas_and_incomplete_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); self.make(path)
            (path/'requests/a.attempt.json').write_text(json.dumps({'attempt_id':'a','protocol':'responses','phase':'finished','http_status':200}))
            values=[{'type':'response.output_text.delta','delta':'partial'},
                {'type':'response.incomplete','response':{'model':'glm-5.3-flash','status':'incomplete',
                    'incomplete_details':{'reason':'max_output_tokens'},'usage':{'input_tokens':1200,'output_tokens':16384}}}]
            (path/'requests/a.response.bin').write_text('\n\n'.join('data: '+json.dumps(v) for v in values))
            _,receipt=authorize_growth(path,{'output_limit':16384},16384)
            self.assertEqual(receipt['output_limit'],32768)


if __name__=='__main__': unittest.main()
