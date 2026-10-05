import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from prepare import ROOT


class ResumeTests(unittest.TestCase):
    def load(self):
        sys.path.insert(0,str(ROOT/'native-runtime'))
        spec=importlib.util.spec_from_file_location('resume_fixture',ROOT/'native-runtime/codex_session.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_existing_thread_and_history_are_preserved(self):
        module=self.load()
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as directory:
            out=Path(directory)
            prior=json.dumps({'type':'turn.failed','error':{'message':'HTTP 520'}})+'\n'
            (out/'events.jsonl').write_text(prior)
            (out/'last-business-result.json').write_text('{"instance_complete":true}')
            class Process:
                stdout=[json.dumps({'type':'thread.started','thread_id':'same-session'})+'\n']
                def wait(self):return 0
            cfg={'solver_transport_resume':True,'session_id':'same-session',
                 'transport_resume_prompt':'continue transport interruption','prompt':'original task'}
            with patch.object(module.subprocess,'Popen',return_value=Process()) as launched:
                result=module.run_solver(cfg,out,out,out,{})
            self.assertEqual(result,'same-session')
            self.assertEqual(launched.call_args.args[0][-3:],['resume','same-session','continue transport interruption'])
            self.assertTrue((out/'events.jsonl').read_text().startswith(prior))
            self.assertFalse(json.loads((out/'transport-resume-receipt.json').read_text())['new_thread'])

    def test_resume_requires_a_failed_turn(self):
        module=self.load()
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as directory:
            out=Path(directory);(out/'events.jsonl').write_text('{"type":"turn.completed"}\n')
            cfg={'solver_transport_resume':True,'session_id':'same-session',
                 'transport_resume_prompt':'continue','prompt':'task'}
            with patch.object(module.subprocess,'Popen') as launched:
                with self.assertRaisesRegex(RuntimeError,'No failed native turn'):
                    module.run_solver(cfg,out,out,out,{})
                launched.assert_not_called()


if __name__=='__main__':unittest.main()
