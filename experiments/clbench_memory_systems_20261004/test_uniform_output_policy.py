"""The 64k revision must not inherit tighter auxiliary caps or a larger ceiling."""
import unittest
from native_gateway import apply_output_policy
from budget_control import authorize_growth
from prepare import ROOT,read


class UniformOutputPolicyTests(unittest.TestCase):
    def test_all_protocols_and_auxiliary_caps_are_uniform(self):
        for protocol in ['chat','responses','anthropic']:
            for original in [None,8192,16384,32768,131072]:
                key='max_output_tokens' if protocol=='responses' else 'max_tokens'
                payload={} if original is None else {key:original}
                apply_output_policy(payload,protocol,{'output_limit':65536,'uniform_output_limit':True})
                self.assertEqual(payload[key],65536)

    def test_legacy_routes_do_not_change_retroactively(self):
        payload={'max_tokens':8192}
        apply_output_policy(payload,'chat',{'output_limit':16384})
        self.assertEqual(payload['max_tokens'],8192)

    def test_fixed_ceiling_rejects_further_growth_without_model_call(self):
        with self.assertRaisesRegex(ValueError,'Fixed output budget'):
            authorize_growth(None,{'output_limit':65536,'automatic_output_growth':False},65536)

    def test_aligned_reserve_fits_native_codex_without_source_patch(self):
        plan=read(ROOT/'config/experiment.json')
        context=plan['context']
        self.assertEqual(context['window_tokens'],262144)
        self.assertEqual(context['reserve_tokens'],65536)
        self.assertEqual(context['auto_compact_trigger_target_tokens'],196608)
        self.assertEqual(context['window_tokens']-context['reserve_tokens'],196608)
        self.assertEqual(min(196608,262144*9//10),196608)


if __name__=='__main__':unittest.main()
