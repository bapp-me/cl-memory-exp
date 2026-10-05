import unittest
import json
from pathlib import Path
import tempfile
from database_followup_results import token_summary
from native_evidence import usage_for
from prepare import ROOT


class ProtocolAccountingTests(unittest.TestCase):
    def attempt(self,ident,protocol,usage):
        return {'attempt_id':ident,'protocol':protocol,'usage':usage}

    def test_two_protocols_count_cache_without_double_counting(self):
        summary=token_summary([
            self.attempt('r','responses',{'input_tokens':100,'output_tokens':10,'total_tokens':110,
                'input_tokens_details':{'cached_tokens':70}}),
            self.attempt('a','anthropic',{'input_tokens':30,'cache_read_input_tokens':70,
                'cache_creation_input_tokens':5,'output_tokens':10})])
        self.assertEqual(summary['by_protocol']['responses']['derived_processed_input_assuming_standard_semantics'],100)
        self.assertEqual(summary['by_protocol']['anthropic']['derived_processed_input_assuming_standard_semantics'],105)
        self.assertFalse(summary['provider_semantics_verified'])
        self.assertEqual(summary['provider_total_not_equal_input_plus_output_attempt_ids'],[])

    def test_unknown_failed_usage_and_missing_cache_are_not_zero(self):
        summary=token_summary([self.attempt('f','anthropic',None),
            self.attempt('m','anthropic',{'input_tokens':3,'output_tokens':2})])
        self.assertEqual(summary['unknown_usage_attempt_ids'],['f'])
        self.assertEqual(summary['cache_not_reported_attempt_ids'],['m'])
        self.assertNotIn('total_tokens',summary['by_protocol']['anthropic']['reported_fields'])

    def test_provider_inconsistent_total_preserved(self):
        summary=token_summary([self.attempt('i','responses',{'input_tokens':10,'output_tokens':3,'total_tokens':20})])
        self.assertEqual(summary['by_protocol']['responses']['reported_fields']['total_tokens'],20)
        self.assertEqual(summary['provider_total_not_equal_input_plus_output_attempt_ids'],['i'])

    def stream(self,terminal):
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as directory:
            out=Path(directory);requests=out/'requests';requests.mkdir()
            (requests/'one.request.json').write_text('{}')
            (requests/'one.attempt.json').write_text(json.dumps({'attempt_id':'one','protocol':'anthropic',
                'phase':'finished' if terminal else 'failed','http_status':200}))
            events=[{'type':'message_start','message':{'model':'glm-5.3-flash','usage':{'input_tokens':0,'output_tokens':0}}}]
            if terminal:events.append({'type':'message_delta','usage':{'output_tokens':65},'delta':{'stop_reason':'end_turn'}})
            (requests/'one.response.bin').write_text(''.join('data: '+json.dumps(e)+'\n\n' for e in events))
            return usage_for(out)[0]

    def test_partial_stream_placeholder_is_not_zero_usage(self):
        attempt=self.stream(False)
        self.assertIsNone(attempt['usage'])
        self.assertEqual(attempt['reported_partial_usage']['output_tokens'],0)
        self.assertIn('unknown',attempt['usage_status'])

    def test_terminal_stream_usage_remains_reported(self):
        attempt=self.stream(True)
        self.assertEqual(attempt['usage']['output_tokens'],65)
        self.assertNotIn('reported_partial_usage',attempt)


if __name__=='__main__':unittest.main()
