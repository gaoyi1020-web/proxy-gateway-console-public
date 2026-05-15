#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLCHAIN_DIR="${PROXY_GATEWAY_DESKTOP_TOOLCHAIN:-${HOME}/.local/share/proxy-gateway-desktop-toolchain}"
NODE_VERSION="${NODE_VERSION:-20.20.2}"
NODE_ARCHIVE="node-v${NODE_VERSION}-darwin-x64.tar.gz"
NODE_DIR="${TOOLCHAIN_DIR}/node-v${NODE_VERSION}-darwin-x64"
NODE_URL="https://nodejs.org/dist/v${NODE_VERSION}/${NODE_ARCHIVE}"
RUSTUP_DIST_SERVER="${RUSTUP_DIST_SERVER:-https://mirrors.ustc.edu.cn/rust-static}"
RUSTUP_UPDATE_ROOT="${RUSTUP_UPDATE_ROOT:-https://mirrors.ustc.edu.cn/rust-static/rustup}"
RUSTUP_INIT_URL="${RUSTUP_UPDATE_ROOT}/dist/x86_64-apple-darwin/rustup-init"
CARGO_REGISTRY_MIRROR="${CARGO_REGISTRY_MIRROR:-sparse+https://mirrors.ustc.edu.cn/crates.io-index/}"

usage() {
  cat <<EOF
usage: $0 [--check|--install-toolchain|--setup|--run]

commands:
  --check             report current Mac build prerequisites
  --install-toolchain install project-local Node and user-local Rust toolchain
  --setup            install missing toolchain, npm deps, and macOS sidecar
  --run              setup, then launch the Tauri desktop app
EOF
}

log() {
  printf '[mac-desktop] %s\n' "$*"
}

ensure_macos_x64() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "this bootstrap is macOS-only" >&2
    exit 2
  fi
  if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "this bootstrap currently targets the 2017 Intel MacBook Pro only" >&2
    exit 2
  fi
}

prepend_toolchain_path() {
  export PATH="${NODE_DIR}/bin:${HOME}/.cargo/bin:${PATH}"
}

have_node() {
  command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1
}

have_rust() {
  command -v cargo >/dev/null 2>&1 \
    && command -v rustc >/dev/null 2>&1 \
    && cargo --version >/dev/null 2>&1 \
    && rustc --version >/dev/null 2>&1
}

print_check() {
  ensure_macos_x64
  prepend_toolchain_path
  log "host: $(sw_vers -productVersion) $(uname -m)"
  if command -v xcodebuild >/dev/null 2>&1; then
    log "xcodebuild: $(command -v xcodebuild)"
  else
    log "xcodebuild: missing"
  fi
  if command -v clang >/dev/null 2>&1; then
    log "clang: $(command -v clang)"
  else
    log "clang: missing"
  fi
  if have_node; then
    log "node: $(node --version)"
    log "npm: $(npm --version)"
  else
    log "node/npm: missing"
  fi
  if have_rust; then
    log "rustc: $(rustc --version)"
    log "cargo: $(cargo --version)"
  elif command -v rustup >/dev/null 2>&1; then
    log "rust/cargo: incomplete ($(rustup --version | head -n 1))"
  else
    log "rust/cargo: missing"
  fi
  if python3 -m pip --version >/dev/null 2>&1; then
    log "pip: $(python3 -m pip --version)"
  else
    log "pip: missing"
  fi
}

install_node() {
  prepend_toolchain_path
  if have_node; then
    log "node/npm already available"
    return 0
  fi
  mkdir -p "${TOOLCHAIN_DIR}"
  local archive="${TOOLCHAIN_DIR}/${NODE_ARCHIVE}"
  log "downloading Node ${NODE_VERSION}"
  curl --fail --location --show-error --retry 5 --retry-all-errors --connect-timeout 20 --max-time 600 "${NODE_URL}" -o "${archive}"
  tar -xzf "${archive}" -C "${TOOLCHAIN_DIR}"
  prepend_toolchain_path
  node --version
  npm --version
}

install_rust() {
  prepend_toolchain_path
  if have_rust; then
    log "rust/cargo already available"
    return 0
  fi
  mkdir -p "${TOOLCHAIN_DIR}"
  export RUSTUP_DIST_SERVER RUSTUP_UPDATE_ROOT
  if command -v rustup >/dev/null 2>&1; then
    log "configuring existing Rust toolchain through ${RUSTUP_DIST_SERVER}"
    rustup default stable
  else
    local rustup_init="${TOOLCHAIN_DIR}/rustup-init-x86_64-apple-darwin"
    log "installing Rust toolchain through ${RUSTUP_DIST_SERVER}"
    curl --fail --location --show-error --retry 5 --retry-all-errors --connect-timeout 20 --max-time 600 "${RUSTUP_INIT_URL}" -o "${rustup_init}"
    chmod +x "${rustup_init}"
    "${rustup_init}" -y --profile minimal --default-toolchain stable
  fi
  prepend_toolchain_path
  rustc --version
  cargo --version
}

configure_cargo_registry() {
  mkdir -p "${ROOT_DIR}/.cargo"
  local cargo_config="${ROOT_DIR}/.cargo/config.toml"
  if [[ -d "${ROOT_DIR}/vendor" ]]; then
    export CARGO_NET_OFFLINE="${CARGO_NET_OFFLINE:-true}"
    log "cargo vendor directory detected; using offline vendored dependencies"
    return 0
  fi
  if [[ -f "${cargo_config}" ]] && ! grep -q "proxy-gateway-desktop generated cargo registry mirror" "${cargo_config}"; then
    log "cargo registry config already exists; leaving ${cargo_config} unchanged"
    return 0
  fi
  cat >"${cargo_config}" <<EOF
# proxy-gateway-desktop generated cargo registry mirror
[source.crates-io]
replace-with = "ustc"

[source.ustc]
registry = "${CARGO_REGISTRY_MIRROR}"

[net]
git-fetch-with-cli = true
EOF
  log "cargo registry mirror: ${CARGO_REGISTRY_MIRROR}"
}

install_toolchain() {
  ensure_macos_x64
  install_node
  install_rust
}

setup_app() {
  install_toolchain
  cd "${ROOT_DIR}"
  configure_cargo_registry
  log "installing npm dependencies"
  npm ci
  log "building macOS gateway-agent sidecar"
  scripts/desktop/build-agent-sidecar.sh --apply
  log "checking Tauri desktop app"
  npm run desktop:check
}

run_app() {
  setup_app
  cd "${ROOT_DIR}"
  log "launching Proxy Gateway Desktop"
  exec npm run desktop:dev
}

command="${1:---check}"
case "${command}" in
  --check) print_check ;;
  --install-toolchain) install_toolchain ;;
  --setup) setup_app ;;
  --run) run_app ;;
  -h|--help|help) usage ;;
  *)
    echo "unknown command: ${command}" >&2
    usage >&2
    exit 2
    ;;
esac
