"""Rebuild derived packets in a separate private directory; zero API calls."""
from datetime import datetime,timezone
from pathlib import Path
import uuid
import prepare
import analysis_provider


def main():
    root=prepare.ROOT.resolve();records=(root/'records').resolve();original_private=analysis_provider.PRIVATE.resolve()
    scratch=(original_private.parent/('reproduction-'+uuid.uuid4().hex)).resolve()
    assert scratch.is_relative_to(original_private.parent) and not scratch.exists()
    scratch.mkdir();scratch_records=scratch/'records'
    original_read=prepare.read;original_save=prepare.save
    def isolated_read(path):
        path=Path(path).resolve()
        if path.is_relative_to(records):
            alternative=scratch_records/path.relative_to(records)
            if alternative.exists():return original_read(alternative)
        return original_read(path)
    def isolated_save(path,value):
        path=Path(path).resolve()
        if path.is_relative_to(records):path=scratch_records/path.relative_to(records)
        assert path.is_relative_to(scratch),'Reproduction may only write derived scratch files'
        return original_save(path,value)
    def no_model(*args,**kwargs):raise RuntimeError('Reproduction must not invoke a model or credential loader')
    prepare.read=isolated_read;prepare.save=isolated_save
    analysis_provider.PRIVATE=scratch;analysis_provider.call=no_model;analysis_provider.secret=no_model
    import full_analysis
    full_analysis.main()
    current=original_read(records/'full-judge-packet-index.json');rebuilt=original_read(scratch_records/'full-judge-packet-index.json')
    assert {r['packet_id'] for r in current}=={r['packet_id'] for r in rebuilt}
    different_objects=[];different_bytes=[]
    for r in current:
        name=r['packet_id']+'.json';a=original_private/'packets'/name;b=scratch/'packets'/name
        if original_read(a)!=original_read(b):different_objects.append(r['packet_id'])
        if prepare.sha(a)!=prepare.sha(b):different_bytes.append(r['packet_id'])
    report={'as_of':datetime.now(timezone.utc).isoformat(),'status':'pass' if not different_objects and not different_bytes else 'mismatch',
        'packets':len(current),'object_mismatches':different_objects,'byte_mismatches':different_bytes,
        'model_calls':0,'source_writes':0,'scratch':scratch.relative_to(root).as_posix(),
        'frozen_manifest_matches':original_read(original_private/'frozen-evidence.json')==original_read(scratch/'frozen-evidence.json')}
    original_save(records/'analysis-reproduction.json',report)
    print(report)


if __name__=='__main__':main()
