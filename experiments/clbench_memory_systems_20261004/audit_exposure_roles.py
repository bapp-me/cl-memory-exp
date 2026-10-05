"""Corroborate Hermes input exposure using exact emitted main-session call IDs."""
from collections import Counter
from datetime import datetime,timezone
import json
from prepare import ROOT,read,save
from analysis_provider import PRIVATE,packet_path
from native_evidence import archive
from full_analysis import wire_tool_calls,texts


def main():
    entries=read(ROOT/'records/full-judge-packet-index.json');rows=[]
    for r in read(ROOT/'records/corrected-task-index.json'):
        if r['method']!='hermes_memory_ready':continue
        unit=f"{r['run_id']}-{r['index']:03d}";out=ROOT/'private-runs'/r['source_run_id']/f"task-{r['index']:03d}"
        lines=set()
        for e in entries:
            if e['unit_id']!=unit or e['kind']!='task_review':continue
            for d in read(packet_path(e['packet_id']))['documents']:
                if d['id'].startswith('exposed_memory_lines@'):lines.update(d['text'].splitlines())
        name='recovered-native-state.tar.gz' if r.get('recovered_maintenance') or r.get('recovered_solver') else 'native-state.tar.gz'
        files=archive(out/name);main=json.loads(files.get(f"tasks/task-{r['index']:03d}/main-result.json",b'{}'))
        main_ids={t['id'] for m in main.get('messages',[]) for t in m.get('tool_calls') or []}
        submission=(out/'submission.json').stat().st_mtime;confirmed=set();matched=[]
        for ident in r['attempt_ids']:
            meta=read(out/'requests'/(ident+'.attempt.json'))
            if datetime.fromisoformat(meta['timestamp'].replace('Z','+00:00')).timestamp()>=submission:continue
            emitted=wire_tool_calls(out/'requests'/(ident+'.response.bin'))
            if not main_ids & {c['id'] for c in emitted}:continue
            request=read(out/'requests'/(ident+'.request.json'))
            body='\n'.join(texts(request.get('messages',request.get('input',[]))))
            if request.get('instructions'):body+='\n'+request['instructions']
            matched.append(ident);confirmed.update(line for line in lines if line in body)
        rows.append({'unit_id':unit,'environment':r['environment'],'recorded_exposed_long_lines':len(lines),
            'confirmed_in_input_to_main_session_call':len(confirmed),'unconfirmed_lines':len(lines-confirmed),
            'exact_call_id_matched_attempts':len(matched),'matched_attempt_ids':matched})
        save(PRIVATE/'main-exposure-corroboration'/(unit+'.json'),{'unit_id':unit,'confirmed':sorted(confirmed),'unconfirmed':sorted(lines-confirmed)})
    report={'as_of':datetime.now(timezone.utc).isoformat(),'model_calls':0,'tasks':rows,
        'scored_hermes_tasks':len(rows),'exposed_lines':sum(r['recorded_exposed_long_lines'] for r in rows),
        'main_session_confirmed_lines':sum(r['confirmed_in_input_to_main_session_call'] for r in rows),
        'unconfirmed_lines':sum(r['unconfirmed_lines'] for r in rows),
        'notes':['Exact equality between response-emitted tool call IDs and the saved main-session transcript corroborates the actor for those input payloads.',
                 'No matching emitted call does not prove a request is auxiliary; final-text and missing/compacted transcript cases remain unassigned.',
                 'Long-line exposure does not establish causal dependence. The interrupted task has no comparable complete main result and is outside this corroboration.']}
    save(ROOT/'records/long-line-exposure-role-audit.json',report)
    print({k:v for k,v in report.items() if k not in {'tasks','notes'}})


if __name__=='__main__':main()
