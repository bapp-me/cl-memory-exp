"""Local experiment utilities. Never log credentials or authorization headers."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def get_secret(provider: str) -> str:
    # DPAPI decryption stays in a child process with captured stdout, never logs.
    if provider not in {'glm', 'deepseek'}:
        raise ValueError('Unknown provider')
    script = (
        "$d=Get-Content -Raw -LiteralPath '" + str(ROOT / '.private/credentials.json').replace("'", "''") + "'|ConvertFrom-Json;"
        "$s=ConvertTo-SecureString $d." + provider + ";"
        "$p=[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s);"
        "try{[Console]::Write([System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($p))}"
        "finally{[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}"
    )
    result = subprocess.run(['pwsh.exe', '-NoProfile', '-Command', script],
                            capture_output=True, check=True)
    return result.stdout.decode('utf-8').strip()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
