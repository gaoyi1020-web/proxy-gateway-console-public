#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-${HOME}/proxy-gateway-console}"
NODE_VERSION="${NODE_VERSION:-20.20.2}"
TEST_ROOT="/tmp/proxy-gateway-v2-cloud-check"
PASSPHRASE="cloud-v2-test-passphrase"
UPSTREAM_STUB_PID=""

log() {
  printf '\n==> %s\n' "$*"
}

need_node_install() {
  if ! command -v node >/dev/null 2>&1; then
    return 0
  fi
  local major
  major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
  [[ "${major}" -lt 20 ]]
}

install_basics() {
  log "Installing base packages"
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    bash \
    build-essential \
    ca-certificates \
    curl \
    git \
    iproute2 \
    python3 \
    tar \
    unzip
}

install_node_if_needed() {
  if ! need_node_install; then
    log "Node already available: $(node --version)"
    return
  fi
  log "Installing Node.js ${NODE_VERSION} with nvm"
  export NVM_DIR="${HOME}/.nvm"
  mkdir -p "${NVM_DIR}"
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh -o /tmp/install-nvm.sh
  bash /tmp/install-nvm.sh
  # shellcheck disable=SC1091
  . "${NVM_DIR}/nvm.sh"
  nvm install "${NODE_VERSION}"
  nvm use "${NODE_VERSION}"
  nvm alias default "${NODE_VERSION}"
}

load_node_env() {
  export NVM_DIR="${HOME}/.nvm"
  if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
    # shellcheck disable=SC1091
    . "${NVM_DIR}/nvm.sh"
    nvm use "${NODE_VERSION}" >/dev/null
  fi
}

run_project_checks() {
  log "Running project checks"
  cd "${PROJECT_DIR}"
  load_node_env
  npm ci
  npm test
  npm run build
}

run_install_checks() {
  log "Running v2 install checks"
  cd "${PROJECT_DIR}"
  scripts/install-v2.sh --dry-run
  scripts/install-v2.sh --apply
  test -x "${HOME}/.local/bin/gateway-agent"
  "${HOME}/.local/bin/gateway-agent" status
}

run_runtime_child_check() {
  log "Running controlled runtime child check"
  cd "${PROJECT_DIR}"
  rm -rf "${TEST_ROOT}"
  start_upstream_stub
  scripts/stage-usb-v2.sh "${TEST_ROOT}"
  "${HOME}/.local/bin/gateway-agent" profile-encrypt \
    --usb-root "${TEST_ROOT}/PROXY_GATEWAY" \
    --passphrase "${PASSPHRASE}"
  "${HOME}/.local/bin/gateway-agent" profile-import \
    --from "${TEST_ROOT}/PROXY_GATEWAY/profile/profile.json.enc" \
    --profile-path "${TEST_ROOT}/local/profile.json.enc"

  env GATEWAY_AGENT_RUNTIME_DIR="${TEST_ROOT}/runtime" GATEWAY_AGENT_V2=1 \
    "${HOME}/.local/bin/gateway-agent" start --lan-host 127.0.0.1
  env GATEWAY_AGENT_RUNTIME_DIR="${TEST_ROOT}/runtime" GATEWAY_AGENT_V2=1 \
    "${HOME}/.local/bin/gateway-agent" runtime-start \
    --profile-path "${TEST_ROOT}/local/profile.json.enc" \
    --passphrase "${PASSPHRASE}" \
    --allow-child

  local port
  port="$(python3 - <<'PY'
import json
from pathlib import Path
session = json.loads(Path("/tmp/proxy-gateway-v2-cloud-check/runtime/session.json").read_text())
print(session["listeners"]["lanProxy"]["port"])
PY
)"
  curl -sS -I -x "http://127.0.0.1:${port}" http://example.com --max-time 12
  env GATEWAY_AGENT_RUNTIME_DIR="${TEST_ROOT}/runtime" GATEWAY_AGENT_V2=1 \
    "${HOME}/.local/bin/gateway-agent" stop
  stop_upstream_stub
}

start_upstream_stub() {
  log "Starting local upstream stub on 127.0.0.1:18180"
  python3 - <<'PY' &
import socketserver

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.rfile.readline()
        while True:
            line = self.rfile.readline()
            if line in (b"\r\n", b"\n", b""):
                break
        self.wfile.write(
            b"HTTP/1.1 204 No Content\r\n"
            b"Connection: close\r\n"
            b"Content-Length: 0\r\n"
            b"\r\n"
        )

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

with Server(("127.0.0.1", 18180), Handler) as server:
    server.serve_forever()
PY
  UPSTREAM_STUB_PID="$!"
  sleep 1
}

stop_upstream_stub() {
  if [[ -n "${UPSTREAM_STUB_PID}" ]]; then
    kill "${UPSTREAM_STUB_PID}" 2>/dev/null || true
    wait "${UPSTREAM_STUB_PID}" 2>/dev/null || true
    UPSTREAM_STUB_PID=""
  fi
}

run_uninstall_checks() {
  log "Running v2 uninstall checks"
  cd "${PROJECT_DIR}"
  scripts/uninstall-v2.sh --apply
  test ! -e "${HOME}/.local/bin/gateway-agent"
  test ! -e "${HOME}/.config/systemd/user/gateway-agent.service"
}

main() {
  trap stop_upstream_stub EXIT
  install_basics
  install_node_if_needed
  run_project_checks
  run_install_checks
  run_runtime_child_check
  run_uninstall_checks
  log "AWS v2 cloud smoke test completed"
}

main "$@"
