import json
from pathlib import Path
import tempfile
import unittest
from full_analysis import wire_tool_calls,packets,memory_kind
from judge_full_analysis import validate,METRICS,normalize_citations


class EvidenceTests(unittest.TestCase):
    def test_chat_tool_argument_reassembly(self):
        events=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'x','function':{'name':'read','arguments':'{"path":'}}]}}]},
                {'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'arguments':'"a"}'}}]}}]}]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'response';p.write_text('\n'.join('data: '+json.dumps(e) for e in events),encoding='utf8')
            self.assertEqual(wire_tool_calls(p),[{'id':'x','name':'read','arguments':{'path':'a'}}])

    def test_responses_done_and_final_are_not_double_counted(self):
        item={'type':'function_call','id':'i','call_id':'c','name':'read','arguments':'{"path":"b"}'}
        events=[{'type':'response.output_item.done','item':item},{'type':'response.completed','response':{'output':[item]}}]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'response';p.write_text('\n'.join('data: '+json.dumps(e) for e in events),encoding='utf8')
            self.assertEqual(len(wire_tool_calls(p)),1)

    def test_memory_sizes_separate_raw_and_bookkeeping(self):
        self.assertEqual(memory_kind('episodes/001.json'),'episodic_store')
        self.assertEqual(memory_kind('home/.codex/memories/raw_memories.md'),'extracted_sources')
        self.assertEqual(memory_kind('home/.hermes/skills/.locks/a.lock'),'bookkeeping')

    def make(self):
        packet={'packet_id':'p','kind':'task_review','documents':[{'id':'d','text':'The record contains exact observable evidence.'}],
                'scope':{'synthesized_memory_changed':False,'visible_memory_evidence':False}}
        result={'packet_id':'p','metrics':{m:{'status':'not_applicable','score':None,'reason':'not present','citations':[]} for m in METRICS},'findings':[],'candidates':[]}
        return packet,result

    def test_valid_citation(self):
        p,r=self.make();r['metrics']['repetition_efficiency']={'status':'assessed','score':1,'reason':'mixed','citations':[{'evidence_id':'d','quote':'exact observable evidence'}]}
        self.assertTrue(validate(r,p))

    def test_fabricated_citation_is_rejected(self):
        p,r=self.make();r['metrics']['repetition_efficiency']={'status':'assessed','score':0,'reason':'bad','citations':[{'evidence_id':'d','quote':'This claim is invented'}]}
        with self.assertRaises(ValueError):validate(r,p)

    def test_unknown_cannot_be_zero(self):
        p,r=self.make();r['metrics']['faithfulness']['status']='unknown';r['metrics']['faithfulness']['score']=0
        with self.assertRaises(ValueError):validate(r,p)

    def test_absent_memory_cannot_receive_quality_score(self):
        p,r=self.make();r['metrics']['faithfulness']={'status':'assessed','score':2,'reason':'good','citations':[{'evidence_id':'d','quote':'exact observable evidence'}]}
        with self.assertRaises(ValueError):validate(r,p)

    def test_exact_quote_can_move_only_within_same_source(self):
        p,r=self.make();p['documents']=[{'id':'d@0','text':'abcdefgh evidence'},{'id':'d@100','text':'other text'}]
        r['metrics']['repetition_efficiency']={'status':'assessed','score':1,'reason':'mixed','citations':[{'evidence_id':'d@100','quote':'abcdefgh evidence'}]}
        fixed,changes=normalize_citations(r,p)
        self.assertEqual(len(changes),1);self.assertTrue(validate(fixed,p))
        self.assertEqual(r['metrics']['repetition_efficiency']['citations'][0]['evidence_id'],'d@100')

    def test_normalization_does_not_accept_paraphrases(self):
        p,r=self.make();r['metrics']['repetition_efficiency']={'status':'assessed','score':1,'reason':'mixed','citations':[{'evidence_id':'d','quote':'The evidence was useful'}]}
        fixed,changes=normalize_citations(r,p)
        self.assertEqual(changes,[])
        with self.assertRaises(ValueError):validate(fixed,p)


if __name__=='__main__':unittest.main()
