"""Replay native CLI event boundaries without invoking Codex or a provider."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

RUNTIME=Path(__file__).parent/'native-runtime'
sys.path.insert(0,str(RUNTIME))
spec=importlib.util.spec_from_file_location('codex_session',RUNTIME/'codex_session.py')
actor=importlib.util.module_from_spec(spec); spec.loader.exec_module(actor)


class ContinuationTests(unittest.TestCase):
    def execute(self, grow, changed_session=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); home=root/'home'; home.mkdir(); out=root/'task'; out.mkdir()
            (home/'config.toml').write_text('model_auto_compact_token_limit = 245760\n')
            commands=[]; registrations=[]
            class Process:
                def __init__(self, command, **kwargs):
                    commands.append(command); self.number=len(commands)
                    sid='new-wrong-session' if self.number==2 and changed_session else 'fixed-session'
                    self.stdout=io.StringIO(json.dumps({'type':'thread.started','thread_id':sid})+'\n')
                def wait(self):
                    if self.number==2:
                        (out/'last-business-result.json').write_text('{"instance_complete":true}')
                    return 1 if self.number==1 else 0
            class Response:
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def read(self): return b'{}'
            def register(request,**kwargs):
                registrations.append(json.loads(request.data));return Response()
            cfg={'prompt':'current task','gateway':'http://127.0.0.1/fixture','gateway_token':'fixture-only',
                 'output_limit':16384,'automatic_output_growth':True}
            with patch.object(actor.subprocess,'Popen',Process),patch.object(actor,'urlopen',register),patch('native_budget.grow',grow):
                sid=actor.run_solver(cfg,out,root,home,{})
            return sid,commands,registrations,(home/'config.toml').read_text(),json.loads((out/'solver-continuations.json').read_text())

    def test_proven_length_resumes_same_session_with_larger_reserve(self):
        def grow(cfg,previous):
            self.assertEqual(previous,16384)
            return {'previous_limit':16384,'output_limit':32768,'compression_threshold':229376,'evidence_attempt_id':'length-proof'}
        sid,commands,registrations,config,receipts=self.execute(grow)
        self.assertEqual(sid,'fixed-session')
        self.assertEqual(len(registrations),1)
        self.assertIn('resume',commands[1]);self.assertIn('fixed-session',commands[1])
        self.assertIn('229376',config);self.assertEqual(receipts[0]['evidence_attempt_id'],'length-proof')

    def test_unproven_failure_does_not_create_another_model_turn(self):
        def rejected(cfg,previous): raise ValueError('No unused output-budget exhaustion evidence')
        with self.assertRaisesRegex(ValueError,'No unused'):
            self.execute(rejected)

    def test_changed_resume_identity_is_rejected(self):
        def grow(cfg,previous): return {'output_limit':32768,'compression_threshold':229376}
        with self.assertRaisesRegex(RuntimeError,'different Codex session'):
            self.execute(grow,changed_session=True)


if __name__=='__main__': unittest.main()
