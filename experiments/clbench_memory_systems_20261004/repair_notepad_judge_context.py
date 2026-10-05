"""Correct judge evidence for Notepad timing and companion feedback, no model call."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import json
from prepare import ROOT,read,save,sha
from analysis_provider import PRIVATE
from full_analysis import packets,canonical


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--defer-loadtest-tail',action='store_true');args=parser.parse_args(argv)
    index=read(ROOT/'records/full-judge-packet-index.json')
    rows={f"{r['run_id']}-{r['index']:03d}":r for r in read(ROOT/'records/corrected-task-index.json') if r['method']=='pi_notepad'}
    live={read(p)['unit_id'] for p in (PRIVATE/'requests').glob('*.attempt.json') if read(p)['phase']=='started'}
    deferred={f'formal-db-pi-notepad-r1-{i:03d}' for i in [9,21,38]} if args.defer_loadtest_tail else set()
    revised=[];pending=[]
    for unit,row in rows.items():
        entries=[e for e in index if e['unit_id']==unit and e['kind']=='task_review']
        old=[read(PRIVATE/'packets'/(e['packet_id']+'.json')) for e in entries]
        if all(p['scope'].get('notepad_timing_contract')=='corrected_v2' for p in old):continue
        if unit in deferred or any(e['packet_id'] in live for e in entries):pending.append(unit);continue
        pieces=defaultdict(dict);templates={}
        for p in old:
            for d in p['documents']:
                base=d['id'].rsplit('@',1)[0];pieces[base][d['character_start']]=d
                templates[base]=d
        docs=[]
        for base,parts in pieces.items():
            text='';cursor=0
            for start,d in sorted(parts.items()):
                assert start==cursor,'Cannot reassemble exact original evidence'
                text+=d['text'];cursor=d['character_end']
            template=templates[base]
            docs.append({'id':base,'kind':template['kind'],'path':template['path'],'text':text})
        out=ROOT/'private-runs'/row['source_run_id']/f"task-{row['index']:03d}"
        cfg=read(out/'input.json');before=read(out/'memory-before.json');after=read(out/'memory-after.json')
        events=[json.loads(line) for line in (out/'tools.jsonl').read_text(encoding='utf8').splitlines() if line]
        transitions=[];previous=before.get('notepad','')
        for i,event in enumerate(events):
            note=event.get('notepad',previous)
            if note!=previous:
                transitions.append({'business_action_index':i,'action':event['action'],'notepad_after_update':note,
                                    'instance_complete_after_action':event['instance_complete'],
                                    'timing':'Update applied before THIS action was executed and before its observation/grade was returned.'})
                previous=note
        if cfg.get('previous_feedback'):
            docs.append({'id':'previous_feedback_visible','kind':'visible_memory','path':'input.previous_feedback actually prefixed to the solver input',
                         'text':cfg['previous_feedback']})
        docs.append({'id':'companion_feedback_for_next_task','kind':'post_task_companion_feedback','path':'memory-after.previous_feedback',
                     'text':after.get('previous_feedback','')})
        docs.append({'id':'notepad_update_timeline','kind':'write_timing_evidence','path':'tools.jsonl plus locked pi_session.mjs update-before-tool semantics',
                     'text':canonical(transitions)})
        scope=dict(old[0]['scope'],notepad_timing_contract='corrected_v2',
            visible_memory_evidence=bool(before.get('notepad') or cfg.get('previous_feedback')),
            companion_feedback_before_nonempty=bool(cfg.get('previous_feedback')),
            post_task_feedback_carried_separately=True,
            judging_rules=("Notepad updates occur BEFORE the associated action response; the note in the final ANSWER call cannot know that call's later grade. "
                           "Grade feedback is saved separately and automatically shown next task. Do not claim that the full memory bundle drops failure feedback merely because notepad text omits it. "
                           "Faithfulness is to source information available at write time: copying a query's wrong result is not by itself fabrication. "
                           "You may flag post-hoc inconsistency or stale assertions, but distinguish this from knowingly ignoring available feedback and from causal harm."))
        for e in entries:
            original=PRIVATE/'packets'/(e['packet_id']+'.json')
            save(PRIVATE/'packet-history/notepad-v1'/(e['packet_id']+'.json'),read(original))
        new=packets(unit,'task_review',old[0]['task_prompt'],docs,scope)
        index=[e for e in index if not(e['unit_id']==unit and e['kind']=='task_review')]+new
        revised.append({'unit_id':unit,'old_packets':len(entries),'new_packets':len(new),'previous_feedback_visible':bool(cfg.get('previous_feedback'))})
    index.sort(key=lambda e:(e['unit_id'],e['kind'],e['part']))
    save(ROOT/'records/full-judge-packet-index.json',index)
    path=ROOT/'records/notepad-judge-context-correction.json'
    prior=read(path) if path.exists() else {'revisions':[]}
    prior.update(as_of=datetime.now(timezone.utc).isoformat(),status='pending_active_or_queued_units' if pending else 'all_notepad_packets_corrected',
                 pending_units=pending,model_calls_in_correction=0,original_experiment_records_changed=False,
                 issue='Initial judge packets omitted separate previous_feedback and write-before-action-result timing',
                 invalidation='Old judge outputs retained privately; packet hash mismatch excludes them from selected semantic analysis',
                 source_evidence=['pi_session.mjs:123-141','pi_session.mjs:206-207','run_pi_database.py:187-188'])
    prior['revisions'].extend(revised);save(path,prior)
    print(json.dumps({'revised_units':len(revised),'pending_units':pending,'total_packets':len(index)}))


if __name__=='__main__':main()
