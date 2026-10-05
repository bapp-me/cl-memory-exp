"""Reconstruct the timed-out review from immutable wire and native snapshots."""
from collections import Counter
from datetime import datetime,timezone
import json
import re
from statistics import median
from prepare import ROOT,read,save,sha
from native_evidence import archive
from summarize_results import response_usage


def tool_output(path):
    calls={};visible='';reasoning=''
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.startswith('data: '):continue
        try:chunk=json.loads(line[6:])
        except json.JSONDecodeError:continue
        for choice in chunk.get('choices',[]):
            delta=choice.get('delta',{})
            visible+=delta.get('content') or '';reasoning+=delta.get('reasoning_content') or ''
            for tool in delta.get('tool_calls',[]):
                value=calls.setdefault(tool.get('index',0),{'name':'','arguments':''})
                value['name']+=tool.get('function',{}).get('name') or ''
                value['arguments']+=tool.get('function',{}).get('arguments') or ''
    return calls,visible,reasoning


def main():
    directory=ROOT/'private-runs/formal-db-hermes-r1';out=directory/'task-009'
    submission_time=(out/'submission.json').stat().st_mtime
    configured_deadline=submission_time+600
    stages={
        'c3c9e598655d432495119407517500a0':'main_turn_finalization_after_submission',
        '2975d356640a47cf88a3db1aefce39a9':'parallel_session_title_generation',
        'd53ce83e4e5b48279fa9176c0dbb0a4a':'skill_review_first_response_and_skill_view',
        '41ff6d3327514ac792de3ec85a1a2de9':'provider_error_500_inside_http_200',
        '35caaf2d69994fe689a85b4ba276e436':'repetitive_tool_arguments_exhaust_16384',
        'c537277a3016403ebc526783be77319c':'32768_retry_finishes_after_supervisor_deadline'}
    timeline=[]
    for ident,stage in stages.items():
        meta=read(out/'requests'/f'{ident}.attempt.json');request=read(out/'requests'/f'{ident}.request.json')
        response=out/'requests'/f'{ident}.response.bin'
        usage,model,finish,_=response_usage(response)
        start=datetime.fromisoformat(meta['timestamp']).timestamp();end=start+meta['seconds']
        timeline.append({'stage':stage,'attempt_id':ident,'start_hkt':datetime.fromtimestamp(start,timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Hong_Kong')).isoformat(),
            'start_after_submission_seconds':round(start-submission_time,3),'duration_seconds':round(meta['seconds'],3),
            'end_after_submission_seconds':round(end-submission_time,3),'time_inside_600s_window':round(max(0,min(end,configured_deadline)-max(start,submission_time)),3),
            'gate_wait_seconds':meta['gate_wait_seconds'],'max_tokens':request['max_tokens'],
            'reasoning_effort':request.get('reasoning_effort'),'http_status':meta['http_status'],
            'finish_reason':finish,'usage':usage,'response_sha256':sha(response)})
    repeated_id='35caaf2d69994fe689a85b4ba276e436';recovered_id='c537277a3016403ebc526783be77319c'
    bad,visible,reasoning=tool_output(out/'requests'/f'{repeated_id}.response.bin');badargs=bad[0]['arguments']
    good,_,_=tool_output(out/'requests'/f'{recovered_id}.response.bin');goodargs=good[0]['arguments']
    decoder=json.JSONDecoder();strings=[]
    for match in re.finditer(r'"new_string"\s*:\s*',badargs):
        try:value,_=decoder.raw_decode(badargs[match.end():]);strings.append(value)
        except json.JSONDecodeError:pass
    repetitions=Counter(strings)
    try:json.loads(badargs);invalid=False
    except json.JSONDecodeError:invalid=True
    before=archive(directory/'task-008/native-state.tar.gz');stopped=archive(out/'timeout-state.tar.gz')
    skill='home/.hermes/skills/benchmarks/clbench-db-quiz/SKILL.md'
    durations=[r['maintenance_seconds'] for r in read(directory/'results.json')]
    result={'status':'diagnosed','diagnostic_model_calls':0,'run_id':directory.name,'index':9,
        'submission_time_basis':'Original unchanged submission.json modification timestamp, consistent with final ANSWER response time.',
        'deadline_seconds':600,'timeline':timeline,
        'previous_completed_maintenance':{'tasks':len(durations),'median_seconds':median(durations),'max_seconds':max(durations),'individual_seconds':durations},
        'repetition':{'tool':bad[0]['name'],'argument_characters':len(badargs),'operations_key_count':badargs.count('"operations"'),
            'complete_repeated_new_string_count':len(strings),'distinct_complete_new_strings':len(repetitions),
            'largest_identical_repeat_count':max(repetitions.values()),'repeated_string_characters':len(repetitions.most_common(1)[0][0]),
            'invalid_truncated_json':invalid,'assistant_visible_text_characters':len(visible),'reported_reasoning_tokens':644,
            'reported_total_output_tokens':16384},
        'later_retry':{'output_cap':32768,'reported_output_tokens':1906,'argument_characters':len(goodargs),
            'valid_json':True,'patch_operations':len(json.loads(goodargs)['operations']),
            'seconds_remaining_at_start':round(configured_deadline-datetime.fromisoformat(read(out/'requests'/f'{recovered_id}.attempt.json')['timestamp']).timestamp(),3),
            'skill_file_unchanged_in_stopped_snapshot':before[skill]==stopped[skill]},
        'source_findings':[
            {'file':'agent/turn_truncation.py','lines':'184-198','finding':'The native repetition guard returns early when tool calls are present; it does not examine these repeated tool arguments.'},
            {'file':'agent/turn_truncation.py','lines':'319-346','finding':'Truncated tool calls are retried with a larger requested output budget.'},
            {'file':'agent/background_review.py','lines':'417-420','finding':'Native skill review is an active read/edit workflow, not merely a short prose summary.'}],
        'conclusions':['The review encountered a slow provider error and a degenerate repeated patch, then ran out of the shared post-submission waiting window.',
            'All six post-submission gate waits were zero; the local 50-request semaphore was not the delay.',
            'The 1.3-second auxiliary call generated a session title; it was not a memory writer.',
            'The later valid JSON arrived after the supervisor deadline; a valid model response is not proof of applied or durable memory.',
            'Increasing the ceiling alone cannot be assumed to cure repetition.'],
        'unknowns':['No per-chunk arrival or first-token timestamp was recorded, so remote queueing, generation and network time cannot be separated exactly.',
            'The source trace does not prove the network-recovery prompt caused the repetition.',
            'The mechanism of the provider Operation failed response is not observable locally.'],
        'changes_made_by_diagnosis':[],
        'runtime_source_verification':'records/hermes-image-source-verification.json'}
    save(ROOT/'records/hermes-maintenance-latency-diagnosis.json',result)
    print(json.dumps({'status':result['status'],'median_prior_seconds':median(durations),'identical_patch_repeats':max(repetitions.values()),
                      'retry_seconds_remaining':result['later_retry']['seconds_remaining_at_start'],'model_calls':0}))


if __name__=='__main__':main()
