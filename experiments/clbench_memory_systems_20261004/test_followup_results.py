import unittest
from database_followup_results import token_summary


class ProtocolAccountingTests(unittest.TestCase):
    def attempt(self,ident,protocol,usage):
        return {'attempt_id':ident,'protocol':protocol,'usage':usage}

    def test_two_protocols_count_cache_without_double_counting(self):
        summary=token_summary([
            self.attempt('r','responses',{'input_tokens':100,'output_tokens':10,'total_tokens':110,
                'input_tokens_details':{'cached_tokens':70}}),
            self.attempt('a','anthropic',{'input_tokens':30,'cache_read_input_tokens':70,
                'cache_creation_input_tokens':5,'output_tokens':10})])
        self.assertEqual(summary['by_protocol']['responses']['known_processed_input_tokens'],100)
        self.assertEqual(summary['by_protocol']['anthropic']['known_processed_input_tokens'],105)
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


if __name__=='__main__':unittest.main()
