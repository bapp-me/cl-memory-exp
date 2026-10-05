"""Count recorded lifecycle facts without inferring hidden actors or costs."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from prepare import ROOT,read,save,sha


def main():
    rows=[]
    for r in read(ROOT/'records/corrected-task-index.json'):
        out=ROOT/'private-runs'/r['source_run_id']/f"task-{r['index']:03d}"
        barrier=read(out/'barrier.json')
        row={'run_id':r['run_id'],'method':r['method'],'environment':r['environment'],'index':r['index'],
             'barrier_status':barrier['status'],'durable':barrier['durable'],'task_seconds':r['seconds'],
             'maintenance_seconds':r['maintenance_seconds'],'maintenance_recovery_seconds':r.get('maintenance_recovery_seconds'),
             'solver_recovery_seconds':r.get('solver_recovery_seconds')}
        if r['method']=='pi_notepad':
            cfg=read(out/'input.json');before=read(out/'memory-before.json');after=read(out/'memory-after.json')
            assert cfg['previous_feedback']==before['previous_feedback']
            row.update(companion_feedback_before_bytes=len(before['previous_feedback'].encode('utf8')),
                       companion_feedback_after_bytes=len(after['previous_feedback'].encode('utf8')),
                       notepad_write_order='before response to its associated action',feedback_handoff_verified=True)
        if not r['method'].startswith('pi_'):
            value=read(out/'native-completion.json');row['native_completion_sha256']=sha(out/'native-completion.json')
            if r['method']=='claude_memory_ready':
                result=value['result'];row.update(subagent_stats=result['subagent_stats'],
                    queued_turn_count=result['queued_turn_count'],observed_turns=result['num_turns'],
                    native_reported_ttft_ms=result.get('ttft_ms'),native_reported_api_duration_ms=result.get('duration_api_ms'))
            elif r['method']=='codex_memory_ready':
                jobs=value['jobs'];row.update(stage1_output_nonempty=jobs['has_stage1_output'],
                    stage1_current_source_statuses=dict(Counter(j['status'] for j in jobs['stage1'])),
                    global_stage2_statuses=dict(Counter(j['status'] for j in jobs['phase2'])),
                    extracted_source_rows=len(jobs.get('extracted_sources',[])),
                    consolidation_required=jobs.get('schedule',{}).get('consolidation_required',True))
            else:
                jobs=value['jobs'];row.update(review_jobs=len(jobs),review_job_statuses=dict(Counter(j['status'] for j in jobs)),
                    requested_memory_reviews=sum(j.get('review_memory') is True for j in jobs),
                    requested_skills_reviews=sum(j.get('review_skills') is True for j in jobs),
                    review_scope_unknown_jobs=sum('review_memory' not in j or 'review_skills' not in j for j in jobs),
                    native_result_categories=dict(Counter(str(j['native_result']) for j in jobs)),
                    parent_sessions_recorded=len({j['parent_session_id'] for j in jobs}),
                    parent_matches_instance=all(j['parent_session_id']==r['session_id'] for j in jobs))
        rows.append(row)
    groups=[]
    keys=sorted({(r['method'],r['environment']) for r in rows})
    for method,env in keys:
        selected=[r for r in rows if (r['method'],r['environment'])==(method,env)]
        group={'method':method,'environment':env,'scored_tasks':len(selected),
               'barrier_statuses':dict(Counter(r['barrier_status'] for r in selected)),
               'task_seconds_known_sum':sum(r['task_seconds'] or 0 for r in selected),
               'task_seconds_unknown_count':sum(r['task_seconds'] is None for r in selected),
               'maintenance_seconds_known_sum':sum(r['maintenance_seconds'] or 0 for r in selected),
               'maintenance_seconds_unknown_count':sum(r['maintenance_seconds'] is None for r in selected)}
        if method=='claude_memory_ready':
            group['reported_subagents_spawned']=sum(r['subagent_stats']['spawned'] for r in selected)
            group['reported_subagents_completed']=sum(r['subagent_stats']['completed'] for r in selected)
        if method=='codex_memory_ready':
            group['nonempty_extractions']=sum(r['stage1_output_nonempty'] for r in selected)
            group['required_consolidation_boundaries']=sum(r['consolidation_required'] for r in selected)
        if method=='hermes_memory_ready':
            group['review_jobs']=sum(r['review_jobs'] for r in selected)
            group['requested_memory_reviews']=sum(r['requested_memory_reviews'] for r in selected)
            group['requested_skills_reviews']=sum(r['requested_skills_reviews'] for r in selected)
            group['review_scope_unknown_jobs']=sum(r['review_scope_unknown_jobs'] for r in selected)
            cats=Counter()
            for r in selected:cats.update(r['native_result_categories'])
            group['native_result_categories']=dict(cats)
        groups.append(group)
    report={'as_of':datetime.now(timezone.utc).isoformat(),'model_calls':0,'tasks':rows,'groups':groups,
            'notes':['Native subagent/job counters and gateway attempts are different inventories; do not sum both as API calls.',
                     'Final job states do not erase historical failures, retries, interrupted or superseded jobs.',
                     'Absent standardized parent/child tracing remains unknown, not zero.',
                     'Native duration sums include framework-specific accounting and concurrency; not campaign wall time.',
                     'No independent claim that a subagent changed the final answer; causal effect was not tested.']}
    save(ROOT/'records/full-lifecycle-metrics.json',report)
    print({'scored_tasks':len(rows),'groups':len(groups),'model_calls':0})


if __name__=='__main__':main()
