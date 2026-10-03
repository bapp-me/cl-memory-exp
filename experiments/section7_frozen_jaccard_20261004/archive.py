"""Archive or verify/restore only this experiment's raw audit evidence."""
import argparse
import hashlib
from pathlib import Path
import tarfile

from run_frozen import ROOT, REPO, RUNS, read, save, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    archive = ROOT / "artifacts/frozen-jaccard-raw.tar.gz"
    index_path = ROOT / "records/raw-archive.json"
    if not (args.verify or args.restore):
        result = read(ROOT / "records/results.json")
        assert result["status"] == "all_48_completed_and_audited"
        from launch import credential
        secret, _ = credential()
        secret_bytes = secret.encode()
        assert secret_bytes
        files = sorted(path for path in RUNS.rglob("*") if path.is_file())
        files.append(ROOT / ".runtime/sandbox-spans.jsonl")
        files.append(ROOT / ".runtime/fixtures/controller-events.jsonl")
        entries = []
        for path in files:
            assert path.suffix in (".json", ".jsonl", ".py")
            data = path.read_bytes()
            if secret_bytes in data:
                raise RuntimeError("Credential present; refuse archive: " + path.name)
            entries.append({"path": path.relative_to(REPO).as_posix(),
                            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        archive.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "w:gz") as tar:
            for path, entry in zip(files, entries):
                tar.add(path, arcname=entry["path"], recursive=False)
        index = {"path": archive.relative_to(ROOT).as_posix(), "bytes": archive.stat().st_size,
                 "sha256": sha(archive), "files": len(entries), "members": entries,
                 "exact_glm_credential_scan": "passed", "model_calls": 0,
                 "scope": "This run's sanitized payloads/trace/memory snapshots/submissions/evaluator and sandbox audit; no workspaces or credential files"}
        save(index_path, index)
    index = read(index_path)
    assert sha(archive) == index["sha256"]
    expected = {entry["path"]: entry for entry in index["members"]}
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        assert len(members) == len(expected) and {member.name for member in members} == set(expected)
        for member in members:
            target = (REPO / member.name).resolve()
            assert member.isfile() and target.is_relative_to(REPO.resolve())
            assert target.is_relative_to(RUNS.resolve()) or target in {
                (ROOT / ".runtime/sandbox-spans.jsonl").resolve(),
                (ROOT / ".runtime/fixtures/controller-events.jsonl").resolve()}
            data = tar.extractfile(member).read()
            assert len(data) == expected[member.name]["bytes"]
            assert hashlib.sha256(data).hexdigest() == expected[member.name]["sha256"]
            if target.exists():
                assert sha(target) == expected[member.name]["sha256"], "Existing evidence differs"
        if args.restore:
            for member in members:
                target = REPO / member.name
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
    if not (args.verify or args.restore):
        index.update(all_members_hash_verified=True, safe_restore_preflight_passed=True)
        save(index_path, index)
    print({key: index[key] for key in ("files", "bytes", "sha256", "exact_glm_credential_scan")})


if __name__ == "__main__":
    main()
