"""Scoped archive, exact credential scan, hash verification and non-overwriting restore."""
import argparse
import tarfile
from common_opt import *
from round_runner import folder
import run_native


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    archive = ROOT / "artifacts/optimization-raw.tar.gz"
    manifest = ROOT / "records/raw-archive.json"
    allowed = [folder(rid, 48).parent.resolve() for rid in ("r1", "r2", "r3")]
    allowed += [(ROOT / p).resolve() for p in ("api", "packets", "reviews")]
    allowed += [(NATIVE / ".runtime/corpus").resolve()]
    if not (args.verify or args.restore):
        completion = read(ROOT / "records/completion-audit.json")
        assert completion["passed"] and completion["total_solver_tasks"] == 144 and completion["study_closed"]
        eng, _ = run_native.engine()
        key = eng.secret().encode()
        assert len(key) > 10
        paths = sorted({p for directory in allowed for p in directory.rglob("*") if p.is_file()})
        entries = []
        for path in paths:
            assert path.suffix in (".json", ".jsonl", ".txt", ".py", ".md")
            data = path.read_bytes()
            assert key not in data, "Credential found; refusing archive"
            entries.append(dict(path=path.relative_to(REPO).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
        # Also scan current study source and reports, not just archived runtime evidence.
        source_scan = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".json", ".jsonl", ".txt")
                       and ".runtime" not in p.parts and "__pycache__" not in p.parts]
        for path in source_scan:
            assert key not in path.read_bytes(), "Credential found in study files"
        archive.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "w:gz") as tar:
            for path, entry in zip(paths, entries):
                tar.add(path, arcname=entry["path"], recursive=False)
        save(manifest, dict(path=archive.relative_to(ROOT).as_posix(), files=len(entries), bytes=archive.stat().st_size,
            sha256=sha(archive), members=entries, exact_glm_credential_scan="passed", source_files_scanned=len(source_scan),
            formal_solver_tasks=144, reviewer_responses=264, reviewer_http_attempts=269, model_calls=0,
            previous_five_modes_archive_sha256="3368476126412083cf65281e0425e31815da5e4eeea413ab8e8a33f0393b537b",
            scope="New144 solver traces/payloads/submissions/evaluations;264 GLM raw responses and269 attempt records,264 evidence packets and parseable review files, immutable98-file corpus. No credentials/caches/workspaces or unrelated files."))
    index = read(manifest)
    assert sha(archive) == index["sha256"]
    expected = {r["path"]: r for r in index["members"]}
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        assert len(members) == len(expected) and {m.name for m in members} == set(expected)
        for member in members:
            path = (REPO / member.name).resolve()
            assert member.isfile() and path.is_relative_to(REPO.resolve())
            assert any(path.is_relative_to(directory) for directory in allowed)
            data = tar.extractfile(member).read()
            assert len(data) == expected[member.name]["bytes"] and hashlib.sha256(data).hexdigest() == expected[member.name]["sha256"]
            if path.exists():
                assert sha(path) == expected[member.name]["sha256"], "Existing evidence differs; refusing overwrite"
        if args.restore:
            for member in members:
                path = REPO / member.name
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(tar.extractfile(member).read())
    if not (args.verify or args.restore):
        index.update(all_members_hash_verified=True, safe_restore_preflight_passed=True)
        save(manifest, index)
    print({k:index[k] for k in ("files", "bytes", "sha256", "formal_solver_tasks", "exact_glm_credential_scan")})


if __name__ == "__main__":
    main()
