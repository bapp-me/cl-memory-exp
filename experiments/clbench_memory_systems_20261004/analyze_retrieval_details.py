"""Recompute recorded Jaccard selection and summarize LLM-reference retrieval."""
from collections import Counter
from datetime import datetime, timezone
import math
import re
from statistics import mean
from prepare import ROOT, read, save
from protocol import jaccard


def project(prompt):
    m=re.search(r'^Repository: (.+)$',prompt,re.M)
    return m.group(1).strip() if m else None


def main():
    labels={r['unit_id']:r for r in read(ROOT/'records/full-retrieval-relevance.json')}
    rows=[]
    for r in read(ROOT/'records/corrected-task-index.json'):
        if r['method']!='pi_jaccard':continue
        unit=f"{r['run_id']}-{r['index']:03d}"
        out=ROOT/'private-runs'/r['source_run_id']/f"task-{r['index']:03d}"
        before=read(out/'memory-before.json');cfg=read(out/'input.json');episode=read(out/'legal-episode.json')
        selected,ranked=jaccard(before['history'],episode['prompt'],namespace=before['namespace'],current_index=r['index'])
        assert [x['source_id'] for x in selected]==[x['source_id'] for x in cfg['sources']]
        recorded=read(out/'retrieval.json')
        assert ranked==recorded['ranked']
        sem=labels.get(unit);known=bool(sem and sem['all_candidate_labels_known'])
        ndcg=None
        if known:
            scores=sem['candidate_labels'];k=len(selected)
            gains=[2**scores[f"candidate:{v['index']}"]-1 for v in ranked[:k]]
            ideal=sorted([2**v-1 for v in scores.values()],reverse=True)[:k]
            dcg=sum(g/math.log2(i+2) for i,g in enumerate(gains))
            idcg=sum(g/math.log2(i+2) for i,g in enumerate(ideal))
            ndcg=dcg/idcg if idcg else None
        rows.append({'unit_id':unit,'environment':r['environment'],'index':r['index'],
            'candidate_count':len(ranked),'selected_count':len(selected),'selection_recomputed_matches':True,
            'selected_indices':[s['episode']['index'] for s in selected],
            'selected_ages':[r['index']-s['episode']['index'] for s in selected],
            'selected_jaccard_scores':[s['score'] for s in selected],
            'selected_from_wrong_episodes':sum('INCORRECT' in s['episode']['feedback'] or 'Submission FAILED' in s['episode']['feedback'] or 'Assigning zero credit' in s['episode']['feedback'] for s in selected),
            'selected_cross_repository':sum(project(s['episode']['prompt'])!=project(episode['prompt']) for s in selected) if r['environment']=='codebase_adaptation' else None,
            'selected_pre_migration_after_migration':sum(s['episode']['index']<20 for s in selected) if r['environment']=='database_exploration' and r['index']>=20 else None,
            'all_semantic_labels_known':known,'ndcg_at_k_jaccard_rank':ndcg,
            'thresholds':sem['thresholds'] if sem else None})
    groups=[]
    for env in sorted({r['environment'] for r in rows}):
        group=[r for r in rows if r['environment']==env];eligible=[r for r in group if r['candidate_count']];known=[r for r in eligible if r['all_semantic_labels_known']]
        thresholds={}
        for threshold in ['1','2']:
            values=[r['thresholds'][threshold] for r in known]
            precisions=[v['precision'] for v in values if v['precision'] is not None]
            recalls=[v['recall'] for v in values if v['recall'] is not None]
            positive=sum(v['known_positive_candidates'] for v in values);hits=sum(v['known_selected_positive'] for v in values)
            selected=sum(r['selected_count'] for r in known)
            thresholds[threshold]={'tasks_complete_labels':len(known),'macro_precision':mean(precisions) if precisions else None,
                'macro_recall':mean(recalls) if recalls else None,'recall_defined_tasks':len(recalls),
                'micro_precision':hits/selected if selected else None,'micro_recall':hits/positive if positive else None,
                'positive_candidates':positive,'selected_positives':hits,'selected_candidates_in_complete_tasks':selected}
        nd=[r['ndcg_at_k_jaccard_rank'] for r in known if r['ndcg_at_k_jaccard_rank'] is not None]
        groups.append({'environment':env,'tasks':len(group),'tasks_with_candidates':len(eligible),'all_semantic_labels_known_tasks':len(known),
            'candidate_pairs':sum(r['candidate_count'] for r in group),'selected_pairs':sum(r['selected_count'] for r in group),
            'selected_wrong_episode_pairs':sum(r['selected_from_wrong_episodes'] for r in group),
            'cross_repository_selected_pairs':sum(r['selected_cross_repository'] or 0 for r in group) if env=='codebase_adaptation' else None,
            'pre_migration_selected_pairs_after_migration':sum(r['selected_pre_migration_after_migration'] or 0 for r in group) if env=='database_exploration' else None,
            'mean_ndcg_at_k_jaccard_rank':mean(nd) if nd else None,'ndcg_defined_tasks':len(nd),'thresholds':thresholds})
    save(ROOT/'records/full-retrieval-details.json',{'as_of':datetime.now(timezone.utc).isoformat(),'tasks':rows,'groups':groups,
        'model_calls':0,'all_59_selections_recomputed':len(rows)==59,
        'notes':['Same frozen candidate history and lexical code; no new retrieval or solver experiment.',
                 'LLM relevance labels, not human ground truth. Undefined recall/nDCG when no positive reference candidate.',
                 'Jaccard top-k is ranked by score but actual injection is chronological; nDCG here refers to similarity ranking.',
                 'Cross-repository, pre-migration or wrong-answer exposure is not itself proven harmful.']})
    print({'tasks':len(rows),'candidate_pairs':sum(r['candidate_count'] for r in rows),'groups':groups})


if __name__=='__main__':main()
