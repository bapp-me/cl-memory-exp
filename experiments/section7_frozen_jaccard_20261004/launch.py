"""Credential bootstrap; no secrets printed or written to experiment artifacts."""
import argparse
import os
import subprocess

import run_frozen
from audit import verify_task
from run_frozen import ROOT, RUNS, check_freeze, run, save


def credential():
    if os.environ.get("GLM_API_KEY", "").strip():
        return os.environ["GLM_API_KEY"].strip(), "process_environment"
    # Existing user/machine variables may have been configured after Codex start.
    for scope in ("User", "Machine"):
        script = "[Console]::Write([Environment]::GetEnvironmentVariable('GLM_API_KEY','" + scope + "'))"
        result = subprocess.run(["pwsh.exe", "-NoProfile", "-Command", script], capture_output=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.decode().strip(), scope.lower() + "_environment"
    eng, _, _ = check_freeze()
    try:
        return eng.secret(), "existing_encrypted_file"
    except Exception:
        raise RuntimeError("GLM credential unavailable; no model request attempted") from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["check", "first", "remaining"])
    args = parser.parse_args()
    check_freeze()
    # Passive audit correction only; frozen solver/retrieval/config are untouched.
    run_frozen.verify_task = verify_task
    try:
        key, source = credential()
    except RuntimeError:
        status = {"status": "waiting_for_local_glm_credential", "model_requests_from_this_startup": 0,
                  "committed_tasks": len(list(RUNS.glob("*/commit.json"))),
                  "credential_value_logged": False}
        save(ROOT / "records/credential-status.json", status)
        print("GLM credential unavailable; no model request attempted.")
        raise SystemExit(3) from None
    os.environ["GLM_API_KEY"] = key
    save(ROOT / "records/credential-status.json", {"status": "available", "source": source,
                                                 "credential_value_logged": False})
    if args.mode == "check":
        print("GLM credential loaded locally; no model request made.")
    else:
        run(args.mode)


if __name__ == "__main__":
    main()
