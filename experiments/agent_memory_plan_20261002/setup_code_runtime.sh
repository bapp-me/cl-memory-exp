#!/bin/sh
# Run within WSL Ubuntu. Installs only in a dedicated user cache directory.
set -eu
project_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
runtime_dir="$HOME/.cache/agent-memory-plan-20261002"
mkdir -p "$runtime_dir/python310" "$runtime_dir/deps310"
printf '%s  %s\n' '260dfddbb52f238f0a8023c95141a28ae110d9a91946a326a4400cefb3e84118' "$project_dir/.cache/python310.tar.gz" | sha256sum -c -
tar -xzf "$project_dir/.cache/python310.tar.gz" -C "$runtime_dir/python310" --strip-components=1
"$runtime_dir/python310/bin/python3.10" -m pip install --target "$runtime_dir/deps310" -r "$project_dir/requirements-codeeval-lock.txt"
