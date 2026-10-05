"""Provider-format repair is literal and leaves usage/content values intact."""
import json
import sys
import unittest
from prepare import ROOT
sys.path.insert(0,str(ROOT/'native-runtime'))
from responses_format_proxy import normalize,unwrap


def stream(text):
    events=[{'type':'response.output_text.delta','item_id':'m','output_index':1,'content_index':0,'delta':text[:8]},
        {'type':'response.output_text.delta','item_id':'m','output_index':1,'content_index':0,'delta':text[8:]},
        {'type':'response.output_text.done','item_id':'m','output_index':1,'content_index':0,'text':text},
        {'type':'response.completed','response':{'usage':{'input_tokens':123,'output_tokens':45},
            'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}}]
    return ''.join('data: '+json.dumps(e)+'\n\n' for e in events).encode()


class FormatTests(unittest.TestCase):
    def test_complete_json_fence_only(self):
        text='```json\n{"value":"Unicode 中文","nested":[1,true]}\n```'
        changed,count=normalize(stream(text));self.assertEqual(count,1)
        events=[json.loads(line[6:]) for line in changed.decode().splitlines() if line.startswith('data: ')]
        self.assertEqual(json.loads(events[0]['delta']),json.loads(unwrap(text)))
        final=events[-1]['response']
        self.assertEqual(final['usage'],{'input_tokens':123,'output_tokens':45})
        self.assertEqual(final['output'][0]['content'][0]['text'],unwrap(text))

    def test_unframed_output_is_byte_identical(self):
        raw=stream('{"value":1}');self.assertEqual(normalize(raw),(raw,0))

    def test_invalid_or_explanatory_output_is_not_repaired(self):
        for value in ['```json\n{"broken":\n```','Explanation\n```json\n{"v":1}\n```','```json\n[1,2]\n```']:
            raw=stream(value);self.assertEqual(normalize(raw),(raw,0))

    def test_real_failed_extraction_is_parseable_without_value_changes(self):
        path=ROOT/'private-runs/candidate-code-codex-64k-v1/task-002/requests/82bb3b0f70d4480cae702af1262c2d32.response.bin'
        if not path.exists():self.skipTest('private audit record unavailable')
        raw=path.read_bytes();changed,count=normalize(raw);self.assertEqual(count,1)
        def final(data):
            values=[]
            for line in data.decode().splitlines():
                if not line.startswith('data: '):continue
                try:values.append(json.loads(line[6:]))
                except ValueError:pass
            return next(v['response'] for v in values if v.get('type')=='response.completed')
        before,after=final(raw),final(changed)
        self.assertEqual(before['usage'],after['usage'])
        old=next(c['text'] for o in before['output'] for c in o.get('content',[]) if c['type']=='output_text')
        new=next(c['text'] for o in after['output'] for c in o.get('content',[]) if c['type']=='output_text')
        self.assertEqual(json.loads(new),json.loads(unwrap(old)))


if __name__=='__main__':unittest.main()
