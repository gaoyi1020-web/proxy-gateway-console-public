#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="${1:---dry-run}"
TOOLCHAIN_DIR="${PROXY_GATEWAY_DESKTOP_TOOLCHAIN:-${HOME}/.local/share/proxy-gateway-desktop-toolchain}"
PYINSTALLER_VENV="${PYINSTALLER_VENV:-${TOOLCHAIN_DIR}/pyinstaller-venv}"
PYINSTALLER_PYTHON="${PYINSTALLER_VENV}/bin/python"
TARGET_TRIPLE="${TARGET_TRIPLE:-$(rustc --print host-tuple 2>/dev/null || rustc -Vv | awk '/host:/ {print $2}')}"
EXT=""
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) EXT=".exe" ;;
esac

OUT_DIR="${ROOT_DIR}/src-tauri/binaries"
OUT="${OUT_DIR}/gateway-agent-${TARGET_TRIPLE}${EXT}"

echo "target: ${TARGET_TRIPLE}"
echo "output: ${OUT}"

create_pyinstaller_venv() {
  rm -rf "${PYINSTALLER_VENV}"
  if python3 -m venv "${PYINSTALLER_VENV}"; then
    return 0
  fi

  rm -rf "${PYINSTALLER_VENV}"
  if command -v virtualenv >/dev/null 2>&1; then
    virtualenv -q -p python3 "${PYINSTALLER_VENV}"
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    uv venv --seed --python python3 "${PYINSTALLER_VENV}"
    return 0
  fi

  echo "failed to create PyInstaller virtual environment; install python3-venv, virtualenv, or uv" >&2
  return 1
}

if [[ "${MODE}" == "--dry-run" ]]; then
  echo "dry-run only; install pyinstaller and run with --apply to build"
  exit 0
fi

if [[ "${MODE}" != "--apply" ]]; then
  echo "usage: $0 [--dry-run|--apply]" >&2
  exit 2
fi

mkdir -p "${TOOLCHAIN_DIR}"
if [[ ! -x "${PYINSTALLER_PYTHON}" ]] || ! "${PYINSTALLER_PYTHON}" -m pip --version >/dev/null 2>&1; then
  create_pyinstaller_venv
fi

if ! "${PYINSTALLER_PYTHON}" -m PyInstaller --version >/dev/null 2>&1 || \
   ! "${PYINSTALLER_PYTHON}" -c 'import cryptography' >/dev/null 2>&1; then
  "${PYINSTALLER_PYTHON}" -m pip install --upgrade pip
  "${PYINSTALLER_PYTHON}" -m pip install --upgrade pyinstaller cryptography
fi

mkdir -p "${OUT_DIR}"
AGENT_HIDDEN_IMPORTS=(
  port_registry
  health
  diagnostics
  profile_crypto
  profile_schema
  runtime_launcher
  session_store
  linux_lifecycle
  unlock_server
  usb_identity
)
PYINSTALLER_ARGS=(
  --clean
  --onefile
  --name "gateway-agent-${TARGET_TRIPLE}"
  --distpath "${OUT_DIR}"
  --workpath /tmp/proxy-gateway-pyinstaller-work
  --specpath /tmp/proxy-gateway-pyinstaller-spec
  --paths "${ROOT_DIR}"
  --paths "${ROOT_DIR}/agent"
)
for module in "${AGENT_HIDDEN_IMPORTS[@]}"; do
  PYINSTALLER_ARGS+=(--hidden-import "${module}")
done
"${PYINSTALLER_PYTHON}" -m PyInstaller \
  "${PYINSTALLER_ARGS[@]}" \
  "${ROOT_DIR}/agent/gateway_agent.py"
chmod +x "${OUT}"
echo "${OUT}"
