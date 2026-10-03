"""Create/verify/restore a credential-scanned archive of the 240 formal runs only."""
import argparse
import hashlib
from pathlib import Path
import tarfile

from native_memory import ROOT, BASE, METHODS
from run_native import REPO, OBS, PREFIX, read, save, sha, engine
import run as initial
from audit import rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    archive = ROOT / "artifacts/five-modes-raw.tar.gz"
    manifest = ROOT / "records/raw-archive.json"
    allowed = [OBS / ".runtime/runs" / f"{prefix}-codeeval-{method}"
               for prefix, methods in ((initial.PREFIX, initial.METHODS), (PREFIX, METHODS)) for method in methods]
    allowed += [ROOT / ".runtime/corpus", ROOT / ".runtime/shell-audit"]
    single_files = {BASE / ".runtime/sandbox-spans.jsonl", ROOT / ".runtime/sandbox-spans.jsonl"}
    if not (args.verify or args.restore):
        result = read(ROOT / "records/analysis.json")
        assert result["total_new_tasks"] == 240 and result["source_only_invariant_passed"]
        eng, _ = engine()
        key = eng.secret().encode()
        assert len(key) > 10
        paths = set()
        shell_audits = set()
        for directory in allowed[:5]:
            commits = list(directory.glob("*/commit.json"))
            assert len(commits) == 48
            paths.update(p for p in directory.rglob("*") if p.is_file())
            for access in directory.glob("*/memory-access.jsonl"):
                for row in rows(access):
                    diagnostic = row.get("diagnostics", {})
                    if diagnostic.get("audit_relative_path"):
                        shell_audits.add((ROOT / diagnostic["audit_relative_path"]).resolve())
        for directory in shell_audits:
            assert directory.is_relative_to((ROOT / ".runtime/shell-audit").resolve())
            paths.update(p for p in directory.rglob("*") if p.is_file())
        paths.update(p for p in (ROOT / ".runtime/corpus").rglob("*") if p.is_file())
        paths.update(p for p in single_files if p.exists())
        paths = sorted(paths)
        entries = []
        for path in paths:
            assert path.suffix in (".json", ".jsonl", ".py", ".txt", ".strace", ".md")
            data = path.read_bytes()
            if key in data:
                raise RuntimeError("Credential scan failed; archive refused: " + path.name)
            entries.append(dict(path=path.relative_to(REPO).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
        archive.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "w:gz") as tar:
            for path, entry in zip(paths, entries):
                tar.add(path, arcname=entry["path"], recursive=False)
        index = dict(path=archive.relative_to(ROOT).as_posix(), files=len(entries), bytes=archive.stat().st_size,
            sha256=sha(archive), members=entries, exact_glm_credential_scan="passed", model_calls=0,
            formal_tasks=240, formal_shell_audit_directories=len(shell_audits),
            scope="Formal solver inputs/payloads/tool traces/submissions/evaluations; read-only native corpus and formal shell access/output logs; no credentials, caches, workspaces or unrelated data")
        save(manifest, index)
    index = read(manifest)
    assert sha(archive) == index["sha256"]
    expected = {row["path"]: row for row in index["members"]}
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        assert len(members) == len(expected) and {m.name for m in members} == set(expected)
        for member in members:
            path = (REPO / member.name).resolve()
            assert member.isfile() and path.is_relative_to(REPO.resolve())
            assert any(path.is_relative_to(p.resolve()) for p in allowed) or path in {p.resolve() for p in single_files}
            data = tar.extractfile(member).read()
            assert len(data) == expected[member.name]["bytes"] and hashlib.sha256(data).hexdigest() == expected[member.name]["sha256"]
            if path.exists():
                assert sha(path) == expected[member.name]["sha256"], "Existing evidence differs"
        if args.restore:
            for member in members:
                path = REPO / member.name
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(tar.extractfile(member).read())
    if not (args.verify or args.restore):
        index.update(all_members_hash_verified=True, safe_restore_preflight_passed=True)
        save(manifest, index)
    print({key: index[key] for key in ("files", "bytes", "sha256", "formal_tasks", "exact_glm_credential_scan")})


if __name__ == "__main__":
    main()
