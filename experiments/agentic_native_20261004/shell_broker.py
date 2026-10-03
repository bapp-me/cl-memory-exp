"""Loopback service: arbitrary agent command runs only inside the memory-only chroot."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import posixpath
from pathlib import Path
import re
import secrets
import subprocess

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)


def linux(path):
    value = Path(path).resolve().as_posix()
    return "/mnt/" + value[0].lower() + value[2:]


def accessed_paths(text):
    """Resolve observed opens; retain raw strace as authority, never infer semantic use."""
    cwd, known, unresolved, pending = {}, set(), [], {}
    for line in text.splitlines():
        pid_match = re.match(r"(\d+)\s+(.*)", line)
        if not pid_match:
            continue
        pid, call = pid_match.groups()
        if "<unfinished ...>" in call:
            pending[pid] = call.split("<unfinished ...>")[0]
            continue
        resumed = re.match(r"<\.\.\. \w+ resumed>(.*)", call)
        if resumed:
            call = pending.pop(pid, "") + resumed.group(1)
        chdir = re.match(r'chdir\("([^"\n]*)"\)\s+= 0', call)
        if chdir:
            path = chdir.group(1)
            cwd[pid] = path if path.startswith("/") else posixpath.join(cwd.get(pid, "/memory"), path)
        fork = re.search(r'(?:clone|clone3|fork|vfork)\(.*\)\s+= (\d+)', call)
        if fork:
            cwd[fork.group(1)] = cwd.get(pid, "/memory")
        opened = re.search(r'openat(?:2)?\(([^,]+), "([^"\n]*)".*\)\s+= (\d+)', call)
        if not opened:
            continue
        fd, path, _ = opened.groups()
        if not path.startswith("/"):
            anchor = re.search(r'<([^>]+)>', fd)
            base = anchor.group(1) if anchor else cwd.get(pid, "/memory")
            # -yy reports the host mount spelling for dirfds observed outside chroot.
            if "/.runtime/shell-root/" in base:
                base = "/" + base.split("/.runtime/shell-root/", 1)[1]
            path = posixpath.join(base, path)
        if path.startswith("/memory/"):
            # No filesystem resolution on host: normalize only within the sandbox namespace.
            known.add(posixpath.normpath(path))
        elif "/memory" in call:
            unresolved.append(call[:800])
    return sorted(known), unresolved


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        if self.headers.get("X-Broker-Token") != TOKEN:
            self.send_error(403)
            return
        size = int(self.headers.get("Content-Length", 0))
        if size > 16000:
            self.send_error(413)
            return
        data = json.loads(self.rfile.read(size))
        ticket, command = data.get("ticket"), data.get("command")
        if not isinstance(ticket, str) or not re.fullmatch(r"[a-f0-9]{32}", ticket) or not isinstance(command, str) or len(command) > 8000:
            self.send_error(400)
            return
        work, audit = ROOT / ".runtime/shell-work" / ticket, ROOT / ".runtime/shell-audit" / ticket
        if work.exists() or audit.exists():
            self.send_error(409)
            return
        work.mkdir(parents=True)
        audit.mkdir(parents=True)
        (work / "command.sh").write_bytes(("cd /memory\n" + command + "\n").encode())
        mount = ROOT / ".runtime/shell-root"
        mount.mkdir(parents=True, exist_ok=True)
        trace = audit / "access.strace"
        args = ["wsl.exe", "-d", "Ubuntu", "--exec", "unshare", "-Urnmpf", "sh", linux(ROOT / "sandbox.sh"),
                linux(mount), linux(work), linux(ROOT / ".runtime/corpus"), linux(trace)]
        timed_out = False
        with (audit / "stdout.txt").open("wb") as stdout, (audit / "stderr.txt").open("wb") as stderr:
            try:
                process = subprocess.run(args, stdout=stdout, stderr=stderr, timeout=35)
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                returncode, timed_out = 124, True
        raw_trace = trace.read_text(encoding="utf-8", errors="replace") if trace.exists() else ""
        opened, unresolved = accessed_paths(raw_trace)
        stdout_bytes = (audit / "stdout.txt").read_bytes()
        stderr_bytes = (audit / "stderr.txt").read_bytes()
        files = [p for p in opened if (ROOT / ".runtime/corpus" / p.removeprefix("/memory/")).is_file()
                 and ".." not in Path(p).parts]
        source_ids = sorted({m.group(0) for p in files for m in re.finditer(r"s\d{3}", p)})
        result = dict(ticket=ticket, returncode=returncode, timeout=timed_out,
            stdout=stdout_bytes[:64000].decode("utf-8", errors="replace"),
            stderr=stderr_bytes[:16000].decode("utf-8", errors="replace"),
            raw_stdout_bytes=len(stdout_bytes), raw_stderr_bytes=len(stderr_bytes),
            broker_output_truncated=len(stdout_bytes) > 64000 or len(stderr_bytes) > 16000,
            opened_memory_files=files, source_ids=source_ids, unresolved_open_examples=unresolved[:5],
            trace_present=bool(raw_trace), trace_sha256=hashlib.sha256(raw_trace.encode()).hexdigest(),
            audit_relative_path=audit.relative_to(ROOT).as_posix())
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state = ROOT / ".runtime/shell-broker.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(dict(url=f"http://127.0.0.1:{server.server_port}", token=TOKEN)), encoding="utf-8")
    print("Native memory-only shell broker ready; no model or credential access.", flush=True)
    server.serve_forever()
