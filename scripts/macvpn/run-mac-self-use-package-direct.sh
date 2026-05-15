#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE="${PACKAGE:-${ROOT_DIR}/dist/self-use/ProxyGateway-Mac-SelfUse-0.2.0.zip}"
MAC_HOST="${MAC_HOST:-example-mac.local}"
MAC_USER="${MAC_USER:-${USER:-user}}"
MAC_SSH_KEY="${MAC_SSH_KEY:-${HOME}/.ssh/proxy_gateway_mac_ed25519}"
KEEP_REMOTE="${KEEP_REMOTE:-0}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REMOTE_DIR="/tmp/proxygateway-direct-install-${STAMP}-$$"
REMOTE="${MAC_USER}@${MAC_HOST}"
SSH_OPTS=(-i "${MAC_SSH_KEY}" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)

if [[ ! -f "${PACKAGE}" ]]; then
  echo "package missing: ${PACKAGE}" >&2
  exit 2
fi

if [[ -z "${MAC_SUDO_PASSWORD:-}" ]]; then
  cat >&2 <<'EOF'
MAC_SUDO_PASSWORD is required for the direct installer test because the
one-click installer installs the root controller through sudo.
EOF
  exit 2
fi

package_sha="$(shasum -a 256 "${PACKAGE}" | awk '{print $1}')"

printf 'Mac self-use direct install target: %s\n' "${REMOTE}"
printf 'package: %s\n' "${PACKAGE}"
printf 'sha256: %s\n' "${package_sha}"
printf 'remote workdir: %s\n' "${REMOTE_DIR}"

ssh "${SSH_OPTS[@]}" "${REMOTE}" "mkdir -p '${REMOTE_DIR}'"
scp -q "${SSH_OPTS[@]}" "${PACKAGE}" "${REMOTE}:${REMOTE_DIR}/package.zip"

ssh "${SSH_OPTS[@]}" "${REMOTE}" \
  "PACKAGE_SHA256='${package_sha}' KEEP_REMOTE='${KEEP_REMOTE}' MAC_SUDO_PASSWORD='${MAC_SUDO_PASSWORD}' bash -s -- '${REMOTE_DIR}'" <<'REMOTE_SCRIPT'
set -euo pipefail

REMOTE_DIR="$1"
ZIP_PATH="${REMOTE_DIR}/package.zip"
UNPACK_DIR="${REMOTE_DIR}/unpack"
BACKUP_ROOT="${HOME}/ProxyGatewayBackups"
BACKUP_DIR="${BACKUP_ROOT}/pre-direct-install-$(date -u +%Y%m%dT%H%M%SZ)"
APP_PATH="${HOME}/Applications/Proxy Gateway Desktop.app"
DESKTOP_APP_PATH="${HOME}/Desktop/Proxy Gateway Desktop.app"
KIT_PATH="${HOME}/ProxyGatewayMacVPN"
LOGIN_AGENT="${HOME}/Library/LaunchAgents/local.proxygateway.desktop.login.plist"
MACVPN_AGENT="${HOME}/Library/LaunchAgents/com.proxygateway.macvpn.plist"
ROOTCTL="/usr/local/sbin/proxygateway-macvpn-rootctl"

failures=()
warnings=()

note() {
  printf '%s\n' "$*"
}

record_failure() {
  failures+=("$*")
  printf 'FAIL: %s\n' "$*" >&2
}

record_warning() {
  warnings+=("$*")
  printf 'WARN: %s\n' "$*" >&2
}

cleanup() {
  if [[ "${KEEP_REMOTE:-0}" != "1" ]]; then
    rm -rf "${REMOTE_DIR}"
  else
    printf 'remote workdir kept: %s\n' "${REMOTE_DIR}"
  fi
}
trap cleanup EXIT

sudo_with_password() {
  printf '%s\n' "${MAC_SUDO_PASSWORD}" | sudo -S -p '' "$@"
}

require_file() {
  local label="$1"
  local path="$2"
  if [[ -f "${path}" ]]; then
    note "PASS: ${label}"
  else
    record_failure "${label}: missing ${path}"
  fi
}

require_dir() {
  local label="$1"
  local path="$2"
  if [[ -d "${path}" ]]; then
    note "PASS: ${label}"
  else
    record_failure "${label}: missing ${path}"
  fi
}

require_executable() {
  local label="$1"
  local path="$2"
  if [[ -x "${path}" ]]; then
    note "PASS: ${label}"
  else
    record_failure "${label}: not executable ${path}"
  fi
}

plist_value() {
  local path="$1"
  local key="$2"
  local value=""
  value="$(plutil -extract "${key}" raw -o - "${path}" 2>/dev/null || true)"
  if [[ -n "${value}" ]]; then
    printf '%s\n' "${value}"
    return 0
  fi
  plutil -p "${path}" | awk -F '=> ' -v key="\"${key}\"" '$1 ~ key {gsub(/"/, "", $2); print $2; exit}'
}

actual_sha="$(shasum -a 256 "${ZIP_PATH}" | awk '{print $1}')"
if [[ "${actual_sha}" == "${PACKAGE_SHA256}" ]]; then
  note "PASS: package sha256"
else
  record_failure "package sha256 mismatch: ${actual_sha}"
fi

mkdir -p "${UNPACK_DIR}" "${BACKUP_DIR}"

if [[ -x "${ROOTCTL}" ]]; then
  sudo -n "${ROOTCTL}" stop >/tmp/proxygateway-direct-rootctl-stop.out 2>&1 || record_warning "passwordless rootctl stop failed"
fi

backup_item() {
  local label="$1"
  local path="$2"
  if [[ -e "${path}" ]]; then
    local target="${BACKUP_DIR}/${label}"
    if command -v ditto >/dev/null 2>&1; then
      if ! ditto "${path}" "${target}" 2>/tmp/proxygateway-direct-backup.err; then
        record_warning "user backup for ${label} needed sudo: $(tr '\n' ' ' </tmp/proxygateway-direct-backup.err)"
        sudo_with_password ditto "${path}" "${target}"
        sudo_with_password chown -R "$(id -un):staff" "${target}" || true
      fi
    else
      if ! cp -R "${path}" "${target}" 2>/tmp/proxygateway-direct-backup.err; then
        record_warning "user backup for ${label} needed sudo: $(tr '\n' ' ' </tmp/proxygateway-direct-backup.err)"
        sudo_with_password cp -R "${path}" "${target}"
        sudo_with_password chown -R "$(id -un):staff" "${target}" || true
      fi
    fi
    note "PASS: backed up ${label}"
  fi
}

backup_item "ProxyGatewayMacVPN" "${KIT_PATH}"
backup_item "Applications-Proxy-Gateway-Desktop.app" "${APP_PATH}"
backup_item "Desktop-Proxy-Gateway-Desktop.app" "${DESKTOP_APP_PATH}"
backup_item "login-launch-agent.plist" "${LOGIN_AGENT}"
backup_item "macvpn-launch-agent.plist" "${MACVPN_AGENT}"
if [[ -x "${ROOTCTL}" ]]; then
  cp "${ROOTCTL}" "${BACKUP_DIR}/proxygateway-macvpn-rootctl" || true
fi

rm -rf "${KIT_PATH}" "${APP_PATH}" "${DESKTOP_APP_PATH}"
rm -f "${LOGIN_AGENT}" "${MACVPN_AGENT}"
defaults delete local.proxygateway.desktop runInBackground >/dev/null 2>&1 || true

unzip -q "${ZIP_PATH}" -d "${UNPACK_DIR}"
package_root="$(find "${UNPACK_DIR}" -mindepth 1 -maxdepth 1 -type d -name 'ProxyGateway-Mac-SelfUse-*' | head -n 1)"
if [[ -n "${package_root}" && -d "${package_root}" ]]; then
  note "PASS: package root"
else
  record_failure "package root missing"
  package_root="${UNPACK_DIR}"
fi

install_cmd="${package_root}/Install Proxy Gateway.command"
require_executable "install command mode" "${install_cmd}"

PROXY_GATEWAY_SUDO_PASSWORD="${MAC_SUDO_PASSWORD}" bash "${install_cmd}" | tee "${REMOTE_DIR}/install.log"

require_dir "installed app" "${APP_PATH}"
require_file "installed app Info.plist" "${APP_PATH}/Contents/Info.plist"
require_file "installed app icon" "${APP_PATH}/Contents/Resources/AppIcon.icns"
require_executable "installed app binary" "${APP_PATH}/Contents/MacOS/ProxyGatewayDesktop"
short_version="$(plist_value "${APP_PATH}/Contents/Info.plist" "CFBundleShortVersionString" | tr -d '\r')"
if [[ "${short_version}" == "0.2.0" ]]; then
  note "PASS: installed app short version"
else
  record_failure "installed app short version mismatch: ${short_version:-empty}"
fi

require_dir "installed Mac VPN kit" "${KIT_PATH}"
require_executable "installed macvpnctl" "${KIT_PATH}/macvpnctl.sh"
require_file "installed sing-box template" "${KIT_PATH}/sing-box.tun.template.json"
require_executable "installed sing-box" "${KIT_PATH}/bin/sing-box"
require_executable "installed rootctl" "${ROOTCTL}"

if sudo -n "${ROOTCTL}" status | tee "${REMOTE_DIR}/rootctl-status.txt"; then
  note "PASS: passwordless rootctl status"
else
  record_failure "passwordless rootctl status failed"
fi

"${KIT_PATH}/macvpnctl.sh" profile-status | tee "${REMOTE_DIR}/profile-status-before.txt"
if grep -Fq "profile-source: missing" "${REMOTE_DIR}/profile-status-before.txt"; then
  note "PASS: fresh install profile missing"
else
  record_failure "fresh install profile source was not missing"
fi

cat >"${REMOTE_DIR}/direct-upstream.json" <<'JSON'
{
  "outbounds": [
    {
      "type": "direct",
      "tag": "direct-smoke"
    }
  ],
  "final": "direct-smoke"
}
JSON
"${KIT_PATH}/macvpnctl.sh" import-upstream --from "${REMOTE_DIR}/direct-upstream.json" | tee "${REMOTE_DIR}/import-upstream.txt"
"${KIT_PATH}/macvpnctl.sh" validate | tee "${REMOTE_DIR}/validate.txt"
require_file "fresh install rendered config" "${KIT_PATH}/config/sing-box.json"

if [[ -f "${DESKTOP_APP_PATH}/Contents/Info.plist" ]]; then
  note "PASS: desktop app copy present"
else
  record_warning "desktop app copy not present after installer"
fi

if [[ -f "${LOGIN_AGENT}" ]]; then
  note "PASS: login launch agent present"
else
  record_warning "login launch agent not present after installer"
fi

if defaults read local.proxygateway.desktop runInBackground >/tmp/proxygateway-direct-background.out 2>&1; then
  note "PASS: background preference present"
else
  record_warning "background preference not present after installer"
fi

if ((${#failures[@]})); then
  printf '\nMac self-use direct install verification: fail\n' >&2
  printf 'backup: %s\n' "${BACKUP_DIR}" >&2
  printf ' - %s\n' "${failures[@]}" >&2
  exit 1
fi

printf '\nMac self-use direct install verification: pass'
if ((${#warnings[@]})); then
  printf ' with warnings'
fi
printf '\n'
printf 'backup: %s\n' "${BACKUP_DIR}"
if ((${#warnings[@]})); then
  printf 'warnings:\n'
  printf ' - %s\n' "${warnings[@]}"
fi
REMOTE_SCRIPT
