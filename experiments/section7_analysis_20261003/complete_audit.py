"""Check the authorized deliverables without calling any model or mutating baseline."""
from common import *
from audit_reviews import get_review


def main():
    m=read(ROOT/'records/manifest.json');a=read(ROOT/'records/review-audit.json');v=read(ROOT/'records/verification.json')
    assert a['complete'] and len(a['cases'])==324
    assert v['status']=='passed' and v['baseline_source_files_unchanged']==7924
    assert len(read(ROOT/'records/control-36-adjudication.json')['records'])==36
    assert len(read(ROOT/'records/priority-16-adjudication.json')['records'])==16
    assert len(read(ROOT/'records/babyai-protocol-audit.json')['records'])==48
    assert not any(read(ROOT/'records/pilot-comparison.json')['gold_validation'].values())
    for x in m['cases']:
        assert get_review(x)['case_id']==x['case_id']
        assert get_review(x)['causal_claim'] is False
    repeated=[]
    for cid in read(ROOT/'records/balance-resume.json')['case_ids']:
        prior=ROOT/'api/formal/deepseek'/cid
        latter=ROOT/'api/formal_balance_retry/deepseek'/cid
        assert read(prior/'terminal.json')['http_status']==402
        assert read(latter/'terminal.json')['http_status']==200
        assert read(prior/'request.json')==read(latter/'request.json')
        repeated.append(cid)
    archive=read(ROOT/'records/review-evidence-archive.json')
    assert archive['all_members_verified'] and archive['exact_two_credentials_scan']=='passed'
    assert sha(ROOT/archive['path'])==archive['sha256']
    costs=read(ROOT/'records/review-costs.json')
    assert costs['http_attempts']==362 and costs['unknown_usage_requests']==20
    assert costs['known_total_tokens']==costs['known_prompt_tokens_including_cache']+costs['known_completion_tokens_including_reasoning']
    record={'section':'7.2','status':'completed_authorized_offline_analysis_and_llm_review_scope','date_hong_kong':'2026-10-03',
            'D0_matrix_tasks':624,'D1_reviews':324,'golden_reference_cases':6,'golden_model':'gpt-6.1-sol xhigh',
            'selected_model':'deepseek-flash (DeepSeek V4.1 Flash)','selected_model_coverage':324,
            'syntax_only_repaired_formal_outputs':1,'calibration_comparison':'DeepSeek/GLM on the same six frozen inputs; all failed configurations retained',
            'priority_cases_adjudicated':16,'preregistered_control_cases_adjudicated':36,'babyai_protocol_checks':48,
            'human_signoff':'not performed; AI reference/adjudication explicitly identified',
            'strict_schema_and_raw_quotes_passed':a['strict_valid_total'],
            'unresolved_quote_fragments':read(ROOT/'records/citation-resolution.json')['summary']['unresolved'],
            'all_labels_human_validated':False,'unresolved_interpretations_retained':True,
            'original_baseline_source_files_unchanged':v['baseline_source_files_unchanged'],
            'original_scores_masks_memory_unchanged':True,'new_agent_rollouts':0,'new_D2_interventions':0,
            'new_external_validation':0,'section7_3_or_later_executed':False,
            'offline_review_http_attempts':costs['http_attempts'],'offline_review_known_tokens':costs['known_total_tokens'],
            'user_authorized_identical_balance_reissues':repeated,'archive_sha256':archive['sha256'],
            'remaining_boundaries':['R=1, historical descriptive baseline limits','D1 judgments not causal truth','No exact block-token/cache attribution or verified dollar invoice','Human signoff unperformed','No project/global scenario or independent final validation']}
    save(ROOT/'records/section7.2-completion-audit.json',record)
    print(json.dumps({k:val for k,val in record.items() if k not in ['user_authorized_identical_balance_reissues','remaining_boundaries']},ensure_ascii=False))


if __name__=='__main__':main()
