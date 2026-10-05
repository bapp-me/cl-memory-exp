"""Inspect structure and size of frozen selected evidence, without printing content."""
from collections import Counter
import json
from prepare import ROOT,read,save
from native_evidence import archive


def main():
    selected=read(ROOT/'records/corrected-task-index.json')
    result=[]
    for method in sorted({x['method'] for x in selected}):
        rows=[r for r in selected if r['method']==method]
        shapes=[]
        for row in [rows[0],rows[-1]]:
            out=ROOT/'private-runs'/row['source_run_id']/f"task-{row['index']:03d}"
            episode=read(out/'legal-episode.json')
            cfg=read(out/'input.json')
            sample={'run_id':row['source_run_id'],'index':row['index'],'episode_keys':list(episode),
                    'episode_bytes':(out/'legal-episode.json').stat().st_size,'input_keys':list(cfg),
                    'files':[p.name for p in out.iterdir() if p.is_file()],
                    'action_keys':list(episode.get('tools',[{}])[0]) if episode.get('tools') else []}
            if not method.startswith('pi_'):
                snap=out/('recovered-native-state.tar.gz' if row['recovered_maintenance'] or row['recovered_solver'] else 'native-state.tar.gz')
                files=archive(snap)
                sample['archive_paths']=list(files)[:22]
                sample['archive_file_count']=len(files)
                sample['managed_memory_paths']=list(read(out/'memory-after.json'))[:15]
                sample['native_event_types']=dict(Counter(json.loads(l).get('type') for l in files.get(f'tasks/{out.name}/events.jsonl',b'').decode().splitlines() if l.strip()))
            shapes.append(sample)
        result.append({'method':method,'tasks':len(rows),'examples':shapes,
                       'episode_bytes_total':sum((ROOT/'private-runs'/r['source_run_id']/f"task-{r['index']:03d}"/'legal-episode.json').stat().st_size for r in rows)})
    save(ROOT/'records/full-analysis-inventory.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
