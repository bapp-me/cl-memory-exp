"""Archive/restore offline review evidence with exact per-member checks."""
import argparse
import tarfile
from common import *


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--restore',action='store_true');args=ap.parse_args()
    archive=ROOT/'artifacts/review-evidence.tar.gz';index_path=ROOT/'records/review-evidence-archive.json'
    if args.restore:
        index=read(index_path);assert sha(archive)==index['sha256']
        expected={x['path']:x['sha256'] for x in index['members']}
        with tarfile.open(archive,'r:gz') as tar:
            members=tar.getmembers();assert {x.name for x in members}==set(expected)
            for member in members:
                dest=(ROOT/member.name).resolve()
                if not member.isfile() or not dest.is_relative_to(ROOT) or member.name.split('/')[0] not in ['api','packets']:
                    raise ValueError('Unsafe archive member')
                data=tar.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==expected[member.name]
                if dest.exists():assert sha(dest)==expected[member.name],'Existing evidence differs'
            for member in members:
                dest=ROOT/member.name
                if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(member).read())
        print(json.dumps({'restored_and_verified_members':len(members)}));return
    files=sorted([p for top in ['api','packets'] for p in (ROOT/top).rglob('*') if p.is_file()])
    assert all(p.suffix in ['.json','.txt'] for p in files)
    # Exact credential scan, in memory, no secret or decrypting command output printed.
    from review import secret
    keys=[secret(p).encode() for p in ['deepseek','glm']]
    hits=[]
    for p in files:
        content=p.read_bytes()
        if any(k and k in content for k in keys):hits.append(p.relative_to(ROOT).as_posix())
    if hits:raise RuntimeError('Credential scan failed; archive not written')
    archive.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive,'w:gz') as tar:
        for p in files:tar.add(p,arcname=p.relative_to(ROOT).as_posix(),recursive=False)
    index={'path':archive.relative_to(ROOT).as_posix(),'sha256':sha(archive),'files':len(files),
           'bytes':archive.stat().st_size,'members':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in files],
           'exact_two_credentials_scan':'passed','baseline_mutated':False,'model_calls':0}
    with tarfile.open(archive,'r:gz') as tar:
        for entry,member in zip(index['members'],tar.getmembers()):
            assert entry['path']==member.name and hashlib.sha256(tar.extractfile(member).read()).hexdigest()==entry['sha256']
    index['all_members_verified']=True;save(index_path,index)
    print(json.dumps({k:v for k,v in index.items() if k!='members'}))


if __name__=='__main__':main()
