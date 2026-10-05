import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
from prepare import ROOT
from database_followup_claude import sources


class MaintenanceTests(unittest.TestCase):
    def resume_fixture(self,prior):
        spec=importlib.util.spec_from_file_location('maintenance',ROOT/'native-runtime/claude_followup.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module,prior

    def test_resume_preserves_events_and_uses_same_native_session(self):
        module,_=self.resume_fixture(None)
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as directory:
            out=Path(directory);prior='{"type":"system"}\n';(out/'events.jsonl').write_text(prior)
            cfg={'session_id':'original-session','gateway':'http://local','gateway_token':'fixture',
                'framing':'common maintenance','prompt':'original record','maintenance_transport_resume':True,
                'maintenance_resume_prompt':'finish same interrupted operation'}
            real_path=Path
            def mapped(path):return real_path(directory)/'claude' if str(path)=='/state/home/.claude' else real_path(path)
            def completed(*args,**kwargs):
                kwargs['stdout'].write('{"type":"result"}\n');return SimpleNamespace(returncode=0)
            with patch.object(module,'Path',side_effect=mapped),patch.object(module.subprocess,'run',side_effect=completed) as launch:
                module.run(None,cfg,out,out)
            command=launch.call_args.args[0]
            self.assertEqual(command[command.index('--resume')+1],'original-session')
            self.assertNotIn('--session-id',command)
            self.assertTrue((out/'events.jsonl').read_text().startswith(prior))

    def test_completed_maintenance_cannot_be_resumed(self):
        module,_=self.resume_fixture(None)
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as directory:
            out=Path(directory);(out/'events.jsonl').write_text(json.dumps({'type':'result','is_error':False,'terminal_reason':'completed'})+'\n')
            cfg={'session_id':'done','gateway':'http://local','gateway_token':'fixture','framing':'common',
                'prompt':'record','maintenance_transport_resume':True,'maintenance_resume_prompt':'continue'}
            real_path=Path
            with patch.object(module,'Path',side_effect=lambda path:real_path(directory)/'claude' if str(path)=='/state/home/.claude' else real_path(path)),patch.object(module.subprocess,'run') as launch:
                with self.assertRaisesRegex(RuntimeError,'Completed maintenance'):
                    module.run(None,cfg,out,out)
                launch.assert_not_called()

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
