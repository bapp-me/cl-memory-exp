"""Compare every resumed stage to the actual upstream uninterrupted schedule."""
import unittest
from codebase_adapter import CodebaseAdaptationTask, restore_rollout_context


class RestoreNoticeTests(unittest.TestCase):
    def test_all_resume_positions_match_uninterrupted_upstream(self):
        uninterrupted = CodebaseAdaptationTask(schedule='default')
        notices = []
        for index in range(len(uninterrupted._schedule_stage_lookup)):
            uninterrupted._stage_change_notice = None
            uninterrupted._update_rollout_context_for_issue(index, announce=index > 0)
            resumed = CodebaseAdaptationTask(schedule='default')
            restore_rollout_context(resumed, index)
            self.assertEqual(resumed._stage_change_notice, uninterrupted._stage_change_notice, index)
            self.assertEqual(resumed.variant, uninterrupted.variant, index)
            self.assertEqual(resumed.variant_repo, uninterrupted.variant_repo, index)
            if resumed._stage_change_notice: notices.append(index)
        self.assertEqual(notices, [9])

    def test_original_recovery_bug_is_reproduced(self):
        for index in [13, 16, 18]:
            task = CodebaseAdaptationTask(schedule='default')
            task._update_rollout_context_for_issue(index, announce=True)
            self.assertEqual(task._stage_change_notice, 'NOTICE: We are now coding in a new repo.')
            restore_rollout_context(task, index)
            self.assertIsNone(task._stage_change_notice)


if __name__ == '__main__': unittest.main()
