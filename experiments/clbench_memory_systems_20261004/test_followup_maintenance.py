import importlib.util
from pathlib import Path
import tempfile
import unittest
from prepare import ROOT
from database_followup_claude import sources


class MaintenanceTests(unittest.TestCase):
    def test_sources_stop_at_event_and_exclude_posthoc_writer_text(self):
        for event in [22,24]:
            history=sources(event)
            self.assertEqual(list(history),list(range(event+1)))
            self.assertEqual(set(history[event]),{'prompt','tools','feedback'})
            self.assertNotIn(event+1,history)
            self.assertIn('prc_v2',str(history[20]['tools']))

    def test_hook_blocks_writes_outside_memory_and_traversal(self):
        spec=importlib.util.spec_from_file_location('guard',ROOT/'native-runtime/followup_write_guard.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as directory:
            root=Path(directory)/'memory';root.mkdir()
            def decision(path):
                return module.decide({'tool_name':'Write','tool_input':{'file_path':str(path)}},root)['hookSpecificOutput']['permissionDecision']
            self.assertEqual(decision(root/'note.md'),'allow')
            self.assertEqual(decision(root/'..'/'source.json'),'deny')
            self.assertEqual(decision(Path(directory)/'settings.json'),'deny')


if __name__=='__main__':unittest.main()
