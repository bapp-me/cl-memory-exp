"""Preserve pending extraction; expose only the last committed memory workspace."""
from datetime import datetime, timezone
import tarfile
from prepare import ROOT, read, save, sha
from native_evidence import archive, memory_snapshot


def main():
    policy = read(ROOT / 'records/codex-batch-policy.json')
    if policy['status'] != 'approved':
        raise RuntimeError('No user authorization')
    evidence = []
    prefix = 'home/.codex/memories/'
    for stopped in read(ROOT / 'records/native-user-pause.json')['streams']:
        directory = ROOT / 'private-runs' / stopped['run_id']
        pending = read(directory / 'boundary.json')['pending']
        if not pending or pending['index'] != stopped['pending_index']:
            raise RuntimeError('Stopped instance changed')
        out = directory / f"task-{pending['index']:03d}"
        source = ROOT / stopped['archive']
        if sha(source) != stopped['archive_sha256'] or sha(out / 'submission.json') != stopped['submission_sha256']:
            raise RuntimeError('Frozen recovery evidence changed')
        previous = directory / f"task-{pending['index']-1:03d}"
        expected = read(previous / 'memory-after.json')
        candidates = [previous / name for name in ['native-state.tar.gz', 'recovered-native-state.tar.gz'] if (previous / name).exists()]
        matching = [p for p in candidates if memory_snapshot(archive(p), 'codex') == expected]
        if not matching:
            raise RuntimeError('No proven committed memory workspace')
        baseline = max(matching, key=lambda p: p.stat().st_mtime_ns)
        destination = out / 'batched-resume-state.tar.gz'
        if destination.exists():
            raise RuntimeError('Prepared resume snapshot already exists; do not overwrite')
        with tarfile.open(destination, 'w:gz') as target:
            for path, keep_memory in [(source, False), (baseline, True)]:
                with tarfile.open(path) as src:
                    for member in src.getmembers():
                        name = member.name.removeprefix('./')
                        if not member.isfile():
                            if not member.isdir():
                                raise RuntimeError('Unsupported link in native state')
                            continue
                        if name.startswith(prefix) != keep_memory:
                            continue
                        target.addfile(member, src.extractfile(member))
        old, new = archive(source), archive(destination)
        assert {k:v for k,v in old.items() if not k.startswith(prefix)} == {k:v for k,v in new.items() if not k.startswith(prefix)}
        assert memory_snapshot(new, 'codex') == expected
        proof = {'run_id': stopped['run_id'], 'index': pending['index'],
                 'original_archive': source.relative_to(ROOT).as_posix(), 'original_sha256': sha(source),
                 'committed_memory_source': baseline.relative_to(ROOT).as_posix(), 'committed_memory_source_sha256': sha(baseline),
                 'resume_archive': destination.relative_to(ROOT).as_posix(), 'resume_archive_sha256': sha(destination),
                 'extraction_databases_and_conversations_unchanged': True,
                 'visible_memory_matches_last_successful_barrier': True, 'business_replayed': False}
        save(out / 'batch-transition.json', proof)
        evidence.append(proof)
    save(ROOT / 'records/codex-batch-transition.json', {'at': datetime.now(timezone.utc).isoformat(),
         'status': 'prepared', 'model_calls': 0, 'streams': evidence})
    print({'prepared': len(evidence), 'model_calls': 0})


if __name__ == '__main__':
    main()
