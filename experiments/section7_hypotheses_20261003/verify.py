"""Offline integrity and completeness checks; no paid or task-execution tools."""
import ast
from build_evidence import ROOT,REPO,read,save,sha


def main():
    sources=read(ROOT/'records/source-hashes.json')
    for p,h in sources.items():assert sha(REPO/p)==h,p
    registry=read(ROOT/'records/hypotheses.json')
    fields=['phenomenon_and_evidence_level','applicable_tasks_history_and_config','main_hypothesis_and_competing_explanations',
            'single_changed_factor','expected_changes_and_invariants','falsification','calls_budget_and_stop_rules']
    assert [h['id'] for h in registry['hypotheses']]==['H1','H2','H3','H4','H5']
    for h in registry['hypotheses']:
        assert all(h.get(k) for k in fields)
        assert h['main_hypothesis_and_competing_explanations']['alternatives']
    cards=read(ROOT/'records/candidate-snapshots.json')['candidates']
    assert len(cards)==8 and len([c for c in cards if c['proposal_role']=='H1_candidate'])==4
    assert all(c['eligibility']=='pending_G0_review_not_execution_approved' for c in cards)
    for c in cards:
        for v in c['snapshot_files'].values():assert sha(REPO/v['path'])==v['sha256']
    budget=read(ROOT/'records/proposed-budget.json')
    assert budget['current_turn_model_calls']==budget['current_turn_rollouts']==0
    assert budget['H1_primary']['max_solver_tasks']==8
    assert budget['H1_primary']['conditional_output_token_envelope']==8*18*3*8192
    # Verify these offline scripts contain no executable network/model subprocess entry.
    for p in ROOT.glob('*.py'):
        tree=ast.parse(p.read_text(encoding='utf-8'))
        for n in ast.walk(tree):
            if isinstance(n,(ast.Import,ast.ImportFrom)):
                names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module or '']
                assert not any(x.split('.')[0] in ['requests','urllib','httpx','subprocess','openai'] for x in names)
    record={'section':'7.3','status':'analysis_complete_proposals_not_execution_approved','hypotheses':5,'quality_gate':'G0',
            'recommended_priority':'H1 reversible source-only representation deduplication after G0',
            'source_files_hash_verified_unchanged':len(sources),'candidate_cards':8,'approved_7_4_tasks':0,
            'new_external_model_calls':0,'new_agent_rollouts':0,'candidate_code_executions':0,'rescoring':0,'online_memory_writes':0,
            'original_scores_masks_retained':True,'human_signoff':'not performed','hypotheses_causally_confirmed':0,
            'budget_status':'proposed ceilings and historical reference only; future spend not authorized'}
    save(ROOT/'records/section7.3-completion-audit.json',record)
    print(record)


if __name__=='__main__':main()
