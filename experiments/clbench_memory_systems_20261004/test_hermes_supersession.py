"""Cancellation requires a settled replacement of the same native writer scope."""
import sys
import unittest
from copy import deepcopy
from prepare import ROOT
sys.path.insert(0,str(ROOT/'native-runtime'))
from hermes_completion import validate_calls


class SupersessionTests(unittest.TestCase):
    def setUp(self):
        self.jobs=[{'id':'old','source_hash':'early','status':'returned','native_result':'none','review_memory':False,'review_skills':True},
            {'id':'memory','source_hash':'final','status':'returned','native_result':'memory','review_memory':True,'review_skills':False}]
        self.calls=[{'id':'interrupted','job_id':'old','status':'returned','result':{'failed':False,'completed':False,'interrupted':True,'turn_exit_reason':'interrupted_during_api_call(background_review_superseded)'}},
            {'id':'complete-memory','job_id':'memory','status':'returned','result':{'failed':False,'completed':True}}]

    def test_memory_writer_cannot_stand_in_for_cancelled_skill_writer(self):
        proofs,missing=validate_calls(self.jobs,self.calls,'final',allow_missing=True)
        self.assertEqual(proofs,[]);self.assertEqual(missing,[(False,True)])
        with self.assertRaises(RuntimeError):validate_calls(self.jobs,self.calls,'final')

    def test_matching_completed_final_skill_review_is_required(self):
        self.jobs.append({'id':'replacement','source_hash':'final','status':'returned','native_result':'none','review_memory':False,'review_skills':True})
        self.calls.append({'id':'complete-skill','job_id':'replacement','status':'returned','result':{'failed':False,'completed':True}})
        proofs,missing=validate_calls(self.jobs,self.calls,'final')
        self.assertEqual(missing,[]);self.assertEqual(proofs[0]['replacement_job_id'],'replacement')
        self.jobs[-1]['source_hash']='stale'
        with self.assertRaises(RuntimeError):validate_calls(self.jobs,self.calls,'final')

    def test_failure_or_ordinary_incompletion_cannot_be_superseded(self):
        for edit in [{'failed':True},{'interrupted':False},{'turn_exit_reason':'max_tokens'}]:
            calls=deepcopy(self.calls);calls[0]['result'].update(edit)
            with self.assertRaises(RuntimeError):validate_calls(self.jobs,calls,'final',allow_missing=True)


if __name__=='__main__':unittest.main()
