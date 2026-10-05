"""Official JSON extraction and same-session native continuation, offline."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from prepare import ROOT,UPSTREAM
sys.path.insert(0,str(UPSTREAM))
sys.path.insert(0,str(ROOT/'native-runtime'))
from codebase_adapter import BashCommandResponse
from src.systems.codex.system import _parse_action_text
import codex_session


class FinalActionTests(unittest.TestCase):
    def test_official_fenced_json_is_used(self):
        value=_parse_action_text('Action:\n```json\n{"thought":"new","command":"pwd"}\n```',BashCommandResponse)
        self.assertEqual(value.command,'pwd')

    def test_plain_text_or_missing_required_field_is_rejected(self):
        for text in ['I submitted the solution.','{"command":"pwd"}']:
            with self.assertRaises(Exception):_parse_action_text(text,BashCommandResponse)

    def test_codex_final_dispatch_and_feedback_use_same_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);commands=[];dispatched=[]
            class Process:
                def __init__(self,command,**kwargs):
                    commands.append(command)
                    self.stdout=io.StringIO('{"type":"thread.started","thread_id":"same-session"}\n')
                    (root/'final.txt').write_text('{"thought":"submit","command":"echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}')
                def wait(self):return 0
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self):return b'{}'
            def dispatch(text,ident):
                dispatched.append(text)
                observed={'instance_complete':True,'observation':'Official feedback'}
                (root/'last-business-result.json').write_text(json.dumps(observed))
                return observed
            cfg={'prompt':'current issue','gateway':'http://fixture','gateway_token':'fixture-only','automatic_output_growth':False}
            with patch.object(codex_session.subprocess,'Popen',Process),patch.object(codex_session,'urlopen',lambda *a,**k:Response()),patch.dict(sys.modules,{'business_mcp':types.SimpleNamespace(final_action=dispatch)}):
                sid=codex_session.run_solver(cfg,root,root,root,{})
            self.assertEqual(sid,'same-session');self.assertEqual(len(commands),2);self.assertEqual(len(dispatched),1)
            self.assertEqual(commands[1][-3:-1],['resume','same-session'])
            self.assertIn('Official feedback',commands[1][-1])


if __name__=='__main__':unittest.main()
