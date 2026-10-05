"""Drain the legacy pre-submitted queue without killing any API request.

Moves only derived, future input packets. The old worker fails before calling
the provider for an absent input. Its current inputs remain byte-identical.
The new controller reads an immutable copy. No experiment source is touched.
"""
import argparse
from datetime import datetime,timezone
import shutil
from prepare import ROOT,read,save,sha
from analysis_provider import PRIVATE
from judge_full_analysis import validate


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--restore',action='store_true');args=parser.parse_args()
    original=(PRIVATE/'packets').resolve();snapshot=(PRIVATE/'packets-concurrency-snapshot').resolve();held=(PRIVATE/'packets-concurrency-held').resolve()
    for p in [original,snapshot,held]:assert p.is_relative_to(PRIVATE.resolve()) and p!=PRIVATE.resolve()
    statepath=ROOT/'records/judge-controller-handoff.json'
    if args.restore:
        state=read(statepath)
        for item in state['packet_hashes']:
            dest=original/(item['packet_id']+'.json');src=held/dest.name
            if src.exists():
                assert not dest.exists() and sha(src)==item['sha256']
                src.rename(dest)
            assert sha(dest)==item['sha256'] and sha(snapshot/dest.name)==item['sha256']
        state.update(status='packet_paths_restored_after_legacy_exit',restored_at=datetime.now(timezone.utc).isoformat())
        save(statepath,state);print({'restored_and_hash_verified':len(state['packet_hashes'])});return
    assert not statepath.exists(),'Handoff already prepared; inspect state instead of repeating'
    entries=read(ROOT/'records/full-judge-packet-index.json');position={e['packet_id']:i for i,e in enumerate(entries)}
    side_names=['full-judge-v4-grounding-front-progress','full-judge-v4-front2-progress']
    side=set();reserved=8
    for name in side_names:
        s=read(ROOT/'records'/(name+'.json'));side.update(read(ROOT/'records'/(name+'-dispatch.json'))['packets'])
        reserved+=s['total_packets']-s.get('processed',0)
    repeat=read(ROOT/'records/full-judge-repeat-progress.json');reserved+=repeat['total_packets']-repeat.get('processed',0)
    def current():return [read(p) for p in (PRIVATE/'requests').glob('*.attempt.json') if read(p)['phase']=='started']
    live=current();legacy=[a for a in live if a['role']=='llm_judge' and a['unit_id'] not in side]
    assert 1<=len(legacy)<=8
    frontier=max(position[a['unit_id']] for a in legacy)
    snapshot.mkdir();held.mkdir();hashes=[]
    for e in entries:
        p=original/(e['packet_id']+'.json');target=snapshot/p.name
        shutil.copy2(p,target);digest=sha(p);assert sha(target)==digest
        hashes.append({'packet_id':e['packet_id'],'sha256':digest})
    moved=[]
    for e in entries[frontier+1:]:
        ident=e['packet_id']
        # Finite side batches have all started, but retain every one defensively.
        if ident in side or ident in {a['unit_id'] for a in live}:continue
        src=original/(ident+'.json');src.rename(held/src.name);moved.append(ident)
    # A legacy request could have crossed the frontier while files were moved.
    # Restore that exact input so its end-of-call hash check remains valid.
    live=current()
    for a in live:
        src=held/(a['unit_id']+'.json')
        if src.exists():src.rename(original/src.name);moved.remove(a['unit_id'])
    live_ids={a['unit_id'] for a in live};selected=[]
    for e in entries:
        ident=e['packet_id']
        if ident in side or ident in live_ids:continue
        result=PRIVATE/'judge'/(ident+'.json');packet=read(snapshot/(ident+'.json'))
        if result.exists():
            r=read(result)
            try:
                assert r['status']=='valid' and r['packet_sha256']==sha(snapshot/(ident+'.json'))
                validate(r['judgement'],packet);continue
            except (AssertionError,ValueError):pass
        selected.append(ident)
    assert 0<75-reserved<=75
    save(ROOT/'records/judge-handoff-packets.json',selected)
    state={'at':datetime.now(timezone.utc).isoformat(),'status':'legacy_queue_draining',
        'legacy_inflight_at_start':[a['attempt_id'] for a in legacy],'reserved_capacity':reserved,
        'new_worker_capacity':min(75-reserved,len(selected)),'selected_new_packets':len(selected),
        'original_frontier':frontier,'held_future_packets':moved,'packet_hashes':hashes,
        'snapshot_path':snapshot.relative_to(ROOT).as_posix(),'original_sources_changed':False,
        'expected_legacy_exit':'Missing future derived input raises FileNotFoundError before any API call; in-flight calls finish and save normally. Restore paths only after legacy process exits.'}
    save(statepath,state)
    print({k:state[k] for k in ['status','reserved_capacity','new_worker_capacity','selected_new_packets','original_frontier']})


if __name__=='__main__':main()
