#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-/tmp/proxy-gateway-desktop-cargo-vendor.tar.gz}"

log() {
  printf '[cargo-vendor] %s\n' "$*"
}

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo is required to package Rust dependencies" >&2
  exit 2
fi

work_dir="$(mktemp -d)"
cleanup() {
  rm -rf "${work_dir}"
}
trap cleanup EXIT

mkdir -p "${work_dir}/.cargo"
cd "${work_dir}"

log "vendoring Rust dependencies from src-tauri/Cargo.lock"
cargo vendor --locked --manifest-path "${ROOT_DIR}/src-tauri/Cargo.toml" vendor > ".cargo/config.toml"
mkdir -p notices
install -m 0644 "${ROOT_DIR}/LICENSE" notices/LICENSE
install -m 0644 "${ROOT_DIR}/docs/THIRD_PARTY_NOTICES.md" notices/THIRD_PARTY_NOTICES.md

mkdir -p "$(dirname "${OUT}")"
tar -czf "${OUT}" -C "${work_dir}" vendor .cargo notices

log "created ${OUT}"
tar -tzf "${OUT}" vendor .cargo/config.toml notices/LICENSE notices/THIRD_PARTY_NOTICES.md >/dev/null
du -h "${OUT}"
