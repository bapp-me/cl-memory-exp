"""Refresh derived execution signatures/basis labels without changing packets."""
from collections import Counter
from prepare import ROOT,read,save
from full_analysis import business_signature


def main():
    path=ROOT/'records/full-mechanical-task-metrics.json';rows=read(path)
    roles={r['unit_id']:r for r in read(ROOT/'records/long-line-exposure-role-audit.json')['tasks']}
    for r in rows:
        out=ROOT/'private-runs'/r['source_run_id']/f"task-{r['index']:03d}"
        tools=read(out/'legal-episode.json')['tools'] if (out/'legal-episode.json').exists() else read(out/'business-actions.json')
        counts=Counter(business_signature(t['action']) for t in tools)
        r['exact_repeated_actions']=sum(c-1 for c in counts.values())
        r['business_repetition_definition']='Identical executable command or action/content, excluding thought text; not automatically waste'
        r['memory_byte_basis']='canonicalized_persisted_state_payload' if r['method'].startswith('pi_') else 'native_file_payload'
        r['exposure_definition']='Exact pre-task lines >=60 characters found in pre-submission provider input; Hermes actor corroboration is separately audited, not semantic use'
        if r['unit_id'] in roles:
            r['hermes_main_actor_confirmed_long_lines']=roles[r['unit_id']]['confirmed_in_input_to_main_session_call']
            r['hermes_actor_unconfirmed_long_lines']=roles[r['unit_id']]['unconfirmed_lines']
    save(path,rows)
    print({'tasks':len(rows),'exact_repeated_business_actions':sum(r['exact_repeated_actions'] for r in rows),'model_calls':0})


if __name__=='__main__':main()
