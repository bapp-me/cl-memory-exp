"""No-model checks of temporal isolation and unmodified raw sidebar sources."""
import json
import unittest
from database_followup_d1 import sidebar
from database_followup_d0 import ROOT, restored_prefix
from prepare import read


class FollowupTests(unittest.TestCase):
    def test_sidebar_exact_legal_raw_fields(self):
        for target, indices in [(33,[30,31,32]), (27,[24,25,26])]:
            rows=json.loads(sidebar(target))
            self.assertEqual(len(rows),3)
            for row,index in zip(rows,indices):
                self.assertLess(index,target)
                source=read(ROOT/'trajectories/codex/database'/f'task-{index:03d}.json')
                self.assertEqual(row,{key:source[key] for key in ['prompt','tools','feedback']})
                self.assertNotIn('assistant_text',row)

    def test_original_complete_prefix_matches_before(self):
        for target in [27,33]:
            proof=restored_prefix('codex',target)
            self.assertTrue(proof['matches_exported_before'])
            self.assertFalse(proof['contains_target_task_directory'])
            self.assertGreater(proof['session_files'],0)
            self.assertIn('home/.codex/memories_1.sqlite',proof['native_database_files'])


if __name__=='__main__':unittest.main()
