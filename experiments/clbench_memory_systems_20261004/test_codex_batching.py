"""Reject stale, uncommitted, and off-schedule native maintenance evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('completion', Path(__file__).parent/'native-runtime/codex_completion.py')
completion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion)


def barrier(environment='database_exploration', index=8):
    plan = completion.schedule(environment, index)
    job = {'kind':'memory_consolidate_global','job_key':'global','status':'done',
           'worker_id':'worker','ownership_token':'token','started_at':20,'finished_at':30,'last_success_watermark':100}
    return {'schedule':plan,'session_id':'source','source_updated_at':100,
            'stage1':[{'status':'done','job_key':'source','last_success_watermark':100}],
            'phase2':[job], 'phase2_before':[copy.deepcopy(job)],
            'pipeline_receipt':{'consolidation_deferred':not plan['consolidation_required']},
            'status':'native_pipeline_verified' if plan['consolidation_required'] else 'native_extraction_verified_consolidation_deferred',
            'extracted_sources':[{'thread_id':'source','source_updated_at':100,'selected_for_phase2':1,'selected_for_phase2_source_updated_at':100}]}


class BatchTests(unittest.TestCase):
    def test_complete_schedule_and_final_partial_batch(self):
        for environment,total,expected in [('database_exploration',40,[10,20,30,40]),('codebase_adaptation',19,[5,10,15,19])]:
            self.assertEqual([i+1 for i in range(total) if completion.schedule(environment,i)['consolidation_required']],expected)

    def test_deferred_extraction_can_queue_native_global_job(self):
        value=barrier();value['phase2'][0].update(status='pending',input_watermark=105,retry_remaining=3)
        completion.validate_barrier(value)

    def test_historical_global_error_does_not_claim_completed_consolidation(self):
        value=barrier();value['phase2'][0]['status']='error'
        completion.validate_barrier(value)
        value['phase2'][0]['started_at']=21
        with self.assertRaisesRegex(RuntimeError,'outside the batch'):completion.validate_barrier(value)

    def test_extracting_without_consolidation_requires_explicit_receipt(self):
        value=barrier();value['pipeline_receipt']['consolidation_deferred']=False
        with self.assertRaisesRegex(RuntimeError,'did not defer'):completion.validate_barrier(value)

    def test_stale_extraction_fails(self):
        value=barrier();value['stage1'][0]['last_success_watermark']=99
        with self.assertRaisesRegex(RuntimeError,'stale'):completion.validate_barrier(value)

    def test_running_writer_cannot_advance(self):
        value=barrier();value['phase2'][0]['status']='running'
        with self.assertRaisesRegex(RuntimeError,'Unsettled'):completion.validate_barrier(value)

    def test_batch_requires_every_extracted_source_committed(self):
        value=barrier(index=9);completion.validate_barrier(value)
        value['extracted_sources'].append({'thread_id':'earlier','source_updated_at':99,'selected_for_phase2':0,'selected_for_phase2_source_updated_at':None})
        with self.assertRaisesRegex(RuntimeError,'every extracted source'):completion.validate_barrier(value)

    def test_batch_cannot_be_marked_deferred(self):
        value=barrier(index=9);value['pipeline_receipt']['consolidation_deferred']=True
        with self.assertRaisesRegex(RuntimeError,'requires native consolidation'):completion.validate_barrier(value)

    def test_schedule_tampering_fails(self):
        value=barrier();value['schedule']['consolidation_required']=True
        with self.assertRaisesRegex(RuntimeError,'differs'):completion.validate_barrier(value)


if __name__ == '__main__': unittest.main()
