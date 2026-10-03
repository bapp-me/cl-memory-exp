"""Protocol-aware review of all 48 BabyAI tasks from actual system/tool records."""
import re
from common import *
from audit_reviews import get_review


def main():
    rows=read(ROOT/'records/d0-tasks.json');manifest={c['case_id']:c for c in read(ROOT/'records/manifest.json')['cases']};out=[]
    for row in rows:
        if row['benchmark']!='babyai':continue
        folder=REPO/row['source_path'];pi=read(folder/'pi-result.json');system=pi['messages'][0]
        tools=system.get('toolsAdded') or read(folder/'legal-task.json')['tools']
        actions=[c['arguments']['action'] for m in pi['messages'] if m['role']=='assistant' for c in m.get('content',[]) if c.get('type')=='toolCall' and c['name']=='ACTION']
        observations=[m for m in pi['messages'] if m['role']=='toolResult']
        texts=[c.get('text','') for m in pi['messages'] if m['role']=='assistant' for c in m.get('content',[]) if c.get('type')=='text']
        obj=get_review(manifest[row['case_id']]);flags=[]
        if obj:
            for i,label in enumerate(obj['labels']):
                if re.search(r'submit|提交|artifact',label.get('reason',''),re.I):
                    flags.append({'label_index':i,'label':label,'adjudication':'Recheck against ACTION-only automatic terminal protocol; lack of SUBMIT is not a defect. Native submitted flag is a terminal-state proxy, not a file/submit-tool requirement.'})
        packet=read(ROOT/'packets'/f'{row["case_id"]}.json')
        goal=next(e['text'] for e in packet['evidence'] if e['id']=='target_prompt')
        out.append({'case_id':row['case_id'],'method':row['method'],'task_id':row['task_id'],'correct':row['correct'],
                    'goal':goal,'legal_tool_names':[t['name'] for t in tools],
                    'system_instruction_without_memory':system['content'].split(' Previous episodes below')[0],
                    'system_record_path':(folder/'pi-result.json').relative_to(REPO).as_posix(),'system_record_sha256':sha(folder/'pi-result.json'),
                    'action_calls':len(actions),'action_sequence':actions,'last_observations':observations[-2:],
                    'final_visible_text':texts[-1] if texts else None,'native_submitted_flag':row['submitted'],'stop_reason':row['stop_reason'],
                    'repeated_arguments_excess':row['tool_metrics']['same_working_arguments_excess'],'injected_entries':row['injection_count'],
                    'budget_20_reached':len(actions)>=20,'suspect_submit_based_labels':flags,
                    'correct_interpretation':'Goal success is native environment done. No explicit SUBMIT tool exists. Repeating navigation/check actions may be necessary; no causal memory attribution.',
                    'human_reviewed':False,'reviewer':'primary Codex agent plus deterministic protocol audit'})
        assert [t['name'] for t in tools]==['ACTION']
    save(ROOT/'records/babyai-protocol-audit.json',{'records':out,'tasks':len(out),'all_action_only':True,
         'packet_limitation':'Original frozen reviewer packets included target visible trajectory and score flags, but did not separately include the system/tool declaration. No rerun; augment analysis from actual original system records.',
         'all_llm_submit_defect_claims_rejected':True,'causal_claim':False})
    print(json.dumps({'tasks':len(out),'submit_related_label_candidates':sum(len(r['suspect_submit_based_labels']) for r in out)}))


if __name__=='__main__':main()
