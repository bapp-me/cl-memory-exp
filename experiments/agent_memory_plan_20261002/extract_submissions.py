"""Recover the exact acknowledged code submission without executing it."""
import hashlib
import json
from core import ROOT,save

def main():
    rows=[]
    for result_path in sorted((ROOT/'runs').glob('**/pi-result.json')):
        if 'codeeval' not in str(result_path.relative_to(ROOT/'runs')):continue
        folder=result_path.parent
        if not (folder/'execution.json').exists():continue
        execution=json.loads((folder/'execution.json').read_text(encoding='utf-8'))
        result=json.loads(result_path.read_text(encoding='utf-8'))
        calls={c['id']:c for m in result['messages'] if m['role']=='assistant' for c in m.get('content',[]) if c.get('type')=='toolCall'}
        acknowledged=[]
        for line in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            if event.get('type')!='tool_execution_end' or event.get('toolName')!='SUBMIT' or event.get('isError'):continue
            texts=event['result'].get('content',[])
            for text in texts:
                try:feedback=json.loads(text.get('text',''))
                except json.JSONDecodeError:continue
                if feedback.get('submitted') and feedback.get('feedback','').startswith('Submission recorded.'):
                    acknowledged.append(calls[event['toolCallId']])
        assert bool(acknowledged)==execution['submitted'],str(folder)
        assert len(acknowledged)<=1,str(folder)
        if acknowledged:
            data=acknowledged[0]['arguments']['code'].encode('utf-8')
            path=folder/'submission.py'
            if path.exists():assert path.read_bytes()==data
            else:path.write_bytes(data)
            digest=hashlib.sha256(data).hexdigest()
        else:digest=None
        status={'submitted':bool(acknowledged),'sha256':digest,'tool_call_id':acknowledged[0]['id'] if acknowledged else None,
                'evidence':'first successful SUBMIT tool_execution_end acknowledgement; no guesses from unsubmitted final text'}
        save(folder/'submission-status.json',status)
        rows.append({'folder':str(folder.relative_to(ROOT)),**status})
    save(ROOT/'records/submission-index.json',{'tasks':len(rows),'submissions':sum(x['submitted'] for x in rows),'rows':rows})
    print(json.dumps({'tasks':len(rows),'submissions':sum(x['submitted'] for x in rows)}))

if __name__=='__main__':main()
