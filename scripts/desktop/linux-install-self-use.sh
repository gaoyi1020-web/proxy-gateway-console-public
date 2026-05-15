#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="${1:---install}"
INSTALL_ROOT="${PROXY_GATEWAY_DESKTOP_INSTALL_ROOT:-${HOME}/.local/share/proxy-gateway-desktop/self-use}"
VERSION="${PROXY_GATEWAY_DESKTOP_VERSION:-$(sed -n 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${ROOT_DIR}/package.json" | head -n 1)}"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
LAUNCHER="${BIN_DIR}/proxy-gateway-desktop"
DESKTOP_FILE="${APP_DIR}/proxy-gateway-desktop.desktop"
LEGACY_ARCHIVE_DIR="${HOME}/.local/share/proxy-gateway-desktop/legacy-launchers"
ICON_NAME="proxy-gateway-desktop"
ICON_ROOT="${HOME}/.local/share/icons/hicolor"
LOG_DIR_EXPR='${XDG_STATE_HOME:-${HOME}/.local/state}/proxy-gateway-console'
LEGACY_DESKTOP_FILES=(
  "${APP_DIR}/proxy-app.desktop"
  "${APP_DIR}/proxy-dashboard.desktop"
  "${HOME}/Desktop/Proxy Gateway Desktop.desktop"
)

usage() {
  cat <<'EOF'
usage: scripts/desktop/linux-install-self-use.sh [--dry-run|--install]

Installs the Linux self-use desktop app for the current user.

--dry-run  print install paths without writing files
--install  install/update release binary, launcher, and desktop entries
EOF
}

if [[ "${MODE}" == "-h" || "${MODE}" == "--help" || "${MODE}" == "help" ]]; then
  usage
  exit 0
fi

if [[ "${MODE}" != "--dry-run" && "${MODE}" != "--install" ]]; then
  usage >&2
  exit 2
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "linux self-use installer can only run on Linux" >&2
  exit 2
fi

cd "${ROOT_DIR}"
RELEASE_BIN="${ROOT_DIR}/src-tauri/target/release/proxy-gateway-test"
RELEASE_SIDECAR="${ROOT_DIR}/src-tauri/target/release/gateway-agent"

if [[ "${MODE}" == "--dry-run" ]]; then
  cat <<EOF
install-root: ${INSTALL_ROOT}
release-binary: ${RELEASE_BIN}
release-sidecar: ${RELEASE_SIDECAR}
launcher: ${LAUNCHER}
desktop-file: ${DESKTOP_FILE}
legacy-launcher-archive: ${LEGACY_ARCHIVE_DIR}
icon: ${ICON_ROOT}/128x128/apps/${ICON_NAME}.png
EOF
  exit 0
fi

if [[ ! -x "${RELEASE_BIN}" ]]; then
  echo "missing release binary; run scripts/desktop/linux-build-self-use.sh --build first: ${RELEASE_BIN}" >&2
  exit 1
fi

if [[ ! -x "${RELEASE_SIDECAR}" ]]; then
  echo "missing release sidecar; run scripts/desktop/linux-build-self-use.sh --build first: ${RELEASE_SIDECAR}" >&2
  exit 1
fi

mkdir -p "${INSTALL_ROOT}/bin" "${INSTALL_ROOT}/notices" "${BIN_DIR}" "${APP_DIR}" "${LEGACY_ARCHIVE_DIR}"
install -m 0755 "${RELEASE_BIN}" "${INSTALL_ROOT}/bin/proxy-gateway-test"
install -m 0755 "${RELEASE_SIDECAR}" "${INSTALL_ROOT}/bin/gateway-agent"
install -m 0644 "${ROOT_DIR}/LICENSE" "${INSTALL_ROOT}/notices/LICENSE"
install -m 0644 "${ROOT_DIR}/docs/THIRD_PARTY_NOTICES.md" "${INSTALL_ROOT}/notices/THIRD_PARTY_NOTICES.md"
printf '%s\n' "${VERSION:-unknown}" >"${INSTALL_ROOT}/VERSION"

if [[ -e "${LAUNCHER}" && ! -L "${LAUNCHER}" ]]; then
  cp "${LAUNCHER}" "${LEGACY_ARCHIVE_DIR}/proxy-gateway-desktop.bak.$(date +%Y%m%d%H%M%S)"
fi

shopt -s nullglob
for launcher_backup in "${BIN_DIR}"/proxy-gateway-desktop.bak.*; do
  mv "${launcher_backup}" "${LEGACY_ARCHIVE_DIR}/$(basename "${launcher_backup}")"
done
shopt -u nullglob

for size in 32 64 128; do
  icon_source="${ROOT_DIR}/src-tauri/icons/${size}x${size}.png"
  icon_target_dir="${ICON_ROOT}/${size}x${size}/apps"
  if [[ -f "${icon_source}" ]]; then
    mkdir -p "${icon_target_dir}"
    install -m 0644 "${icon_source}" "${icon_target_dir}/${ICON_NAME}.png"
  fi
done

cat >"${LAUNCHER}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

APP_BIN="${INSTALL_ROOT}/bin/proxy-gateway-test"
LOG_DIR="${LOG_DIR_EXPR}"
LOG_FILE="\${LOG_DIR}/desktop-app.log"
LOCK_FILE="\${LOG_DIR}/desktop-app.lock"

mkdir -p "\${LOG_DIR}"

if [[ "\${PROXY_GATEWAY_DESKTOP_CHILD:-0}" != "1" ]]; then
  export PROXY_GATEWAY_DESKTOP_CHILD=1
  setsid -f "\$0" "\$@" >/dev/null 2>&1
  exit 0
fi

exec 9>"\${LOCK_FILE}"
if ! flock -n 9; then
  printf '[%s] Proxy Gateway Desktop already appears to be running\n' "\$(date -Is)" >>"\${LOG_FILE}"
  exit 0
fi

if [[ ! -x "\${APP_BIN}" ]]; then
  printf '[%s] missing release binary: %s\n' "\$(date -Is)" "\${APP_BIN}" >>"\${LOG_FILE}"
  exit 127
fi

cd "${INSTALL_ROOT}"
exec env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY "\${APP_BIN}" >>"\${LOG_FILE}" 2>&1
EOF
chmod +x "${LAUNCHER}"

cat >"${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=Proxy Gateway Desktop
Comment=Open the Proxy Gateway desktop controller
Exec=${LAUNCHER}
Icon=${ICON_NAME}
Terminal=false
Categories=Network;
StartupNotify=true
EOF

for legacy_file in "${LEGACY_DESKTOP_FILES[@]}"; do
  if [[ -f "${legacy_file}" ]]; then
    legacy_name="$(basename "${legacy_file}")"
    mv "${legacy_file}" "${LEGACY_ARCHIVE_DIR}/${legacy_name}.bak.$(date +%Y%m%d%H%M%S)"
  fi
done

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache "${ICON_ROOT}" >/dev/null 2>&1 || true
fi

printf 'Linux self-use desktop app installed at %s\n' "${INSTALL_ROOT}"
