import json
from pathlib import Path
import tempfile
import unittest
from full_analysis import wire_tool_calls,packets,memory_kind,business_signature
from judge_full_analysis import validate,METRICS,normalize_citations


class EvidenceTests(unittest.TestCase):
    def test_thought_wording_does_not_hide_repeated_command(self):
        self.assertEqual(business_signature({'command':'pytest -q','thought':'first run'}),
                         business_signature({'command':'pytest -q','thought':'verify again'}))
        self.assertNotEqual(business_signature({'action':'QUERY','content':'SELECT a'}),
                            business_signature({'action':'QUERY','content':'SELECT b'}))
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

    def test_exact_quote_can_move_within_same_source(self):
        p,r=self.make();p['documents']=[{'id':'d@0','text':'abcdefgh evidence'},{'id':'d@100','text':'other text'}]
        r['metrics']['repetition_efficiency']={'status':'assessed','score':1,'reason':'mixed','citations':[{'evidence_id':'d@100','quote':'abcdefgh evidence'}]}
        fixed,changes=normalize_citations(r,p)
        self.assertEqual(len(changes),1);self.assertTrue(validate(fixed,p))
        self.assertEqual(r['metrics']['repetition_efficiency']['citations'][0]['evidence_id'],'d@100')

    def test_cross_document_quote_requires_unique_exact_owner(self):
        p,r=self.make();p['documents']=[{'id':'a','text':'a different passage'},{'id':'b','text':'the only exact evidence'}]
        r['metrics']['repetition_efficiency']={'status':'assessed','score':1,'reason':'mixed','citations':[{'evidence_id':'a','quote':'the only exact evidence'}]}
        fixed,changes=normalize_citations(r,p)
        self.assertEqual(fixed['metrics']['repetition_efficiency']['citations'][0]['evidence_id'],'b')
        self.assertEqual(len(changes),1)
        p['documents'].append({'id':'c','text':'the only exact evidence'})
        fixed,changes=normalize_citations(r,p)
        self.assertEqual(changes,[])
        with self.assertRaises(ValueError):validate(fixed,p)

    def test_normalization_does_not_accept_paraphrases(self):
        p,r=self.make();r['metrics']['repetition_efficiency']={'status':'assessed','score':1,'reason':'mixed','citations':[{'evidence_id':'d','quote':'The evidence was useful'}]}
        fixed,changes=normalize_citations(r,p)
        self.assertEqual(changes,[])
        with self.assertRaises(ValueError):validate(fixed,p)

    def test_new_plan_cannot_stand_in_for_prior_memory_reuse(self):
        p,r=self.make();p['scope']['visible_memory_evidence']=True
        p['documents']=[{'id':'m','kind':'visible_memory','text':'Previous task documented a different operation.'},
                        {'id':'a','kind':'current_trajectory','text':'The new plan says inspect formatter before editing.'}]
        r['metrics']['visible_reuse']={'status':'assessed','score':2,'reason':'plan matches action',
            'citations':[{'evidence_id':'a','quote':'inspect formatter before editing'}]}
        with self.assertRaises(ValueError):validate(r,p)

    def test_concrete_reuse_requires_memory_and_action_evidence(self):
        p,r=self.make();p['scope']['visible_memory_evidence']=True
        p['documents']=[{'id':'m','kind':'visible_memory','text':'Use ref_id as the join key for this dataset.'},
                        {'id':'a','kind':'current_trajectory','text':'SELECT ref_id FROM dataset WHERE ref_id IS NOT NULL'}]
        r['metrics']['visible_reuse']={'status':'assessed','score':2,'reason':'documented key matches query',
            'citations':[{'evidence_id':'m','quote':'Use ref_id as the join key'}]}
        with self.assertRaises(ValueError):validate(r,p)
        r['metrics']['visible_reuse']['citations'].append({'evidence_id':'a','quote':'SELECT ref_id FROM dataset'})
        self.assertTrue(validate(r,p))


if __name__=='__main__':unittest.main()
