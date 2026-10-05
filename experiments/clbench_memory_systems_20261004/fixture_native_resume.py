"""Real isolated-container recovery fixture, without a model or benchmark task."""
import base64
import io
import tarfile
from prepare import ROOT,save
import native_client
from native_evidence import archive


def blob(name,data=b'fixture-only'):
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w:gz') as tar:
        info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644
        tar.addfile(info,io.BytesIO(data))
    return buffer.getvalue()


def main():
    checks=[]
    for kind in ['default','codex']:
        native_client.BROKER_KIND=kind
        created=native_client.broker({'op':'create','runtime_hash':native_client.freeze_runtime()})
        c=created['container_id']
        try:
            native_client.broker({'op':'restore','container_id':c,'data':base64.b64encode(blob('home/restored-marker.txt')).decode()})
            native_client.broker({'op':'quiesce','container_id':c})
            path=ROOT/'.local'/f'restore-fixture-{kind}.tar.gz'
            native_client.snapshot(c,path)
            assert archive(path)['home/restored-marker.txt']==b'fixture-only'
            try:native_client.broker({'op':'restore','container_id':c,'data':base64.b64encode(blob('../escape')).decode()})
            except RuntimeError as exc:assert 'Unsafe state archive' in str(exc)
            else:raise AssertionError('Traversal archive admitted')
            checks.append({'broker':kind,'state_roundtrip':True,'quiesced_snapshot':True,'traversal_rejected':True})
        finally:native_client.broker({'op':'remove','container_id':c})
    save(ROOT/'records/native-resume-fixture.json',{'status':'passed','model_calls':0,'checks':checks})
    print({'resume_fixtures':'passed','model_calls':0})


if __name__=='__main__':main()
