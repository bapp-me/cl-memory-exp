#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends pkg-config libssl-dev libcap-dev libseccomp-dev clang cmake protobuf-compiler python3 python3-pip git curl zstd
rustup component add rustfmt clippy
cargo install --locked just cargo-nextest dotslash
pip3 install --break-system-packages uv==0.12.23
mkdir -p /build/source
tar -xf /input/source.tar -C /build/source
cd /build/source
git init -q
git -c user.name=CLBench -c user.email=clbench@localhost add .
git -c user.name=CLBench -c user.email=clbench@localhost commit -qm 'Pinned upstream snapshot'
git apply /input/boundary.patch
export CARGO_BUILD_JOBS=2
export CARGO_PROFILE_DEV_DEBUG=0
export CARGO_PROFILE_TEST_DEBUG=0
just fmt
git diff -- codex-rs/memories/write/src/start.rs codex-rs/memories/write/src/phase1.rs codex-rs/state/src/runtime/memories.rs > /build/formatted-boundary.patch
just test -p codex-state -p codex-memories-write
cd codex-rs
cargo build -p codex-cli --bin codex
cp target/debug/codex /build/codex-clbench
sha256sum /build/codex-clbench > /build/codex-clbench.sha256
echo CLBENCH_CODEX_BUILD_COMPLETE
