#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${PROXY_GATEWAY_DESKTOP_INSTALL_ROOT:-${HOME}/.local/share/proxy-gateway-desktop/self-use}"
LAUNCHER="${HOME}/.local/bin/proxy-gateway-desktop"
DESKTOP_FILE="${HOME}/.local/share/applications/proxy-gateway-desktop.desktop"
DESKTOP_COPY="${HOME}/Desktop/Proxy Gateway Desktop.desktop"
LEGACY_PROXY_APP="${HOME}/.local/share/applications/proxy-app.desktop"
LEGACY_PROXY_DASHBOARD="${HOME}/.local/share/applications/proxy-dashboard.desktop"
APP_BIN="${INSTALL_ROOT}/bin/proxy-gateway-test"
SIDECAR_BIN="${INSTALL_ROOT}/bin/gateway-agent"
ICON_FILE="${HOME}/.local/share/icons/hicolor/128x128/apps/proxy-gateway-desktop.png"
LICENSE_FILE="${INSTALL_ROOT}/notices/LICENSE"
THIRD_PARTY_NOTICES="${INSTALL_ROOT}/notices/THIRD_PARTY_NOTICES.md"

failures=0

check() {
  local label="$1"
  shift
  if "$@"; then
    printf 'PASS: %s\n' "${label}"
  else
    printf 'FAIL: %s\n' "${label}" >&2
    failures=$((failures + 1))
  fi
}

check "launcher exists" test -x "${LAUNCHER}"
check "desktop entry exists" test -f "${DESKTOP_FILE}"
check "desktop copy is not installed" test ! -f "${DESKTOP_COPY}"
check "legacy proxy app entry is absent" test ! -f "${LEGACY_PROXY_APP}"
check "legacy proxy dashboard entry is absent" test ! -f "${LEGACY_PROXY_DASHBOARD}"
check "release binary exists" test -x "${APP_BIN}"
check "sidecar binary exists" test -x "${SIDECAR_BIN}"
check "project license notice exists" test -f "${LICENSE_FILE}"
check "third-party notices exist" test -f "${THIRD_PARTY_NOTICES}"
check "app icon exists" test -f "${ICON_FILE}"
check "launcher does not use dev command" bash -c "! rg -q 'desktop:dev|tauri dev|npm run desktop:dev' '${LAUNCHER}'"

shopt -s nullglob
launcher_backups=("${HOME}/.local/bin/proxy-gateway-desktop.bak."*)
shopt -u nullglob
if [[ "${#launcher_backups[@]}" -eq 0 ]]; then
  printf 'PASS: launcher backups are archived\n'
else
  printf 'FAIL: launcher backups remain in ~/.local/bin\n' >&2
  failures=$((failures + 1))
fi

if [[ -x "${LAUNCHER}" ]]; then
  if rg -q 'desktop:dev|tauri dev|npm run desktop:dev' "${LAUNCHER}"; then
    echo "launcher must not launch npm run desktop:dev" >&2
    failures=$((failures + 1))
  fi
fi

if [[ -f "${DESKTOP_FILE}" ]]; then
  check "desktop entry uses stable launcher" grep -Fxq "Exec=${LAUNCHER}" "${DESKTOP_FILE}"
  check "desktop entry uses installed app icon" rg -q '^Icon=proxy-gateway-desktop$' "${DESKTOP_FILE}"
fi

if [[ "${failures}" -ne 0 ]]; then
  printf 'Linux self-use desktop verification: fail (%s)\n' "${failures}" >&2
  exit 1
fi

printf 'Linux self-use desktop verification: pass\n'
