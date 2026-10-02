"""Verify exact fragment provenance and read-only branch isolation."""
import json
from core import ROOT,digest,save

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    checks=[];reviews=[]
    for p in sorted((ROOT/'runs').glob('diagnostic-*/*/card.json')):
        card=read(p);history=read(ROOT/card['source_snapshot']/'memory-before.json')
        if not all(k in card['branches'] for k in ['normal','related','irrelevant']):continue
        assert digest(history)==card['snapshot_hash'] and card['snapshot_unchanged']
        for branch in ['related','irrelevant']:
            s=card['selection'];fragment=s[branch+'_fragment'];original=json.loads(history[s[branch+'_index']]['text']);selected=json.loads(fragment['episode']['text'])
            assert original['task']==selected['task']
            assert [original['trajectory'][i] for i in fragment['indices']]==selected['trajectory']
            assert read(p.parent/branch/'injected.json')==[fragment['episode']]
            assert digest(read(p.parent/branch/'memory-before.json'))==card['snapshot_hash']
            assert not (p.parent/branch/'memory-after.json').exists()
        n=card['branches']['normal']['source_result']['correct'];r=card['branches']['related']['score']['correct'];u=card['branches']['irrelevant']['score']['correct']
        source=ROOT/card['source_snapshot'];source_episode=card['selection']['related_index']
        source_score=read(source.parent/f'{source_episode:03d}'/'commit.json')['result']['correct']
        if r and not u and not n:reading='Relevant-history condition helped here; one draw cannot establish stability or unique cause.'
        elif r and u and not n:reading='Both history interventions helped; cannot attribute this to relevance alone.'
        elif not r and not u and not n:reading='All branches failed; inspect source quality, target contract, model capability and budget before blaming retrieval.'
        elif n and r and u:reading='No correctness discrimination; inspect query/cost differences separately.'
        elif u and not r:reading='Control outperformed relevant-history condition; relevance-specific benefit is unsupported in this case.'
        else:reading='Mixed outcome; requires trace review and is not stable causal evidence.'
        reviews.append({'benchmark':card['benchmark'],'target':card['target_index'],'normal_correct':n,'related_correct':r,'control_correct':u,
                        'related_source_correct':source_score,'interpretation_for_review':reading,'card':str(p.relative_to(ROOT))})
        checks.append({'benchmark':card['benchmark'],'target':card['target_index'],'exact_provenance':True,'frozen_state_unchanged':True,'no_branch_memory_writeback':True})
    save(ROOT/'records/diagnostic-audit.json',{'completed_targets':len(checks),'checks':checks,'reviews':reviews,
         'limits':['Control histories may share generic skills.', 'Related source correctness does not guarantee all selected facts are useful or correct for the current target.', 'One repetition; intervention directions may reflect stochastic variation.']})
    print(json.dumps({'completed_targets':len(checks),'all_checks_passed':True}))

if __name__=='__main__':main()
