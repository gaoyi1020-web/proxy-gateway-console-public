#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE="${PACKAGE:-${ROOT_DIR}/dist/self-use/ProxyGateway-Mac-SelfUse-0.2.0.zip}"
MAC_HOST="${MAC_HOST:-example-mac.local}"
MAC_USER="${MAC_USER:-${USER:-user}}"
MAC_SSH_KEY="${MAC_SSH_KEY:-${HOME}/.ssh/proxy_gateway_mac_ed25519}"
KEEP_REMOTE="${KEEP_REMOTE:-0}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REMOTE_DIR="/tmp/proxygateway-package-smoke-${STAMP}-$$"
REMOTE="${MAC_USER}@${MAC_HOST}"
SSH_OPTS=(-i "${MAC_SSH_KEY}" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)

if [[ ! -f "${PACKAGE}" ]]; then
  echo "package missing: ${PACKAGE}" >&2
  exit 2
fi

package_sha="$(shasum -a 256 "${PACKAGE}" | awk '{print $1}')"

printf 'Mac self-use package sandbox target: %s\n' "${REMOTE}"
printf 'package: %s\n' "${PACKAGE}"
printf 'sha256: %s\n' "${package_sha}"
printf 'remote sandbox: %s\n' "${REMOTE_DIR}"

ssh "${SSH_OPTS[@]}" "${REMOTE}" "mkdir -p '${REMOTE_DIR}'"
scp -q "${SSH_OPTS[@]}" "${PACKAGE}" "${REMOTE}:${REMOTE_DIR}/package.zip"

ssh "${SSH_OPTS[@]}" "${REMOTE}" \
  "PACKAGE_SHA256='${package_sha}' KEEP_REMOTE='${KEEP_REMOTE}' bash -s -- '${REMOTE_DIR}'" <<'REMOTE_SCRIPT'
set -euo pipefail

REMOTE_DIR="$1"
ZIP_PATH="${REMOTE_DIR}/package.zip"
UNPACK_DIR="${REMOTE_DIR}/unpack"
SMOKE_HOME="${REMOTE_DIR}/home"
SMOKE_TARGET="${SMOKE_HOME}/ProxyGatewayMacVPN"

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
    printf 'remote sandbox kept: %s\n' "${REMOTE_DIR}"
  fi
}
trap cleanup EXIT

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

require_missing() {
  local label="$1"
  local path="$2"
  if [[ ! -e "${path}" ]]; then
    note "PASS: ${label}"
  else
    record_failure "${label}: still exists ${path}"
  fi
}

require_contains() {
  local label="$1"
  local path="$2"
  local pattern="$3"
  if grep -Fq "${pattern}" "${path}"; then
    note "PASS: ${label}"
  else
    record_failure "${label}: missing '${pattern}' in ${path}"
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

mkdir -p "${UNPACK_DIR}" "${SMOKE_HOME}"

actual_sha="$(shasum -a 256 "${ZIP_PATH}" | awk '{print $1}')"
if [[ "${actual_sha}" == "${PACKAGE_SHA256}" ]]; then
  note "PASS: package sha256"
else
  record_failure "package sha256 mismatch: ${actual_sha}"
fi

unzip -q "${ZIP_PATH}" -d "${UNPACK_DIR}"
package_root="$(find "${UNPACK_DIR}" -mindepth 1 -maxdepth 1 -type d -name 'ProxyGateway-Mac-SelfUse-*' | head -n 1)"
if [[ -n "${package_root}" && -d "${package_root}" ]]; then
  note "PASS: package root"
else
  record_failure "package root missing"
  package_root="${UNPACK_DIR}"
fi

if find "${package_root}" -type f \( -name 'upstream.json' -o -name 'sing-box.json' -o -name 'profile.json.enc' -o -name '*.log' -o -name 'verify-mac-desktop-state.sh' -o -name 'verify-mac-ui-closeout.sh' -o -name 'package-self-use-installer.sh' \) | grep -q .; then
  record_failure "package contains private or runtime artifacts"
else
  note "PASS: package private artifact exclusion"
fi

install_cmd="${package_root}/Install Proxy Gateway.command"
uninstall_cmd="${package_root}/Uninstall Proxy Gateway.command"
require_executable "install command mode" "${install_cmd}"
require_executable "uninstall command mode" "${uninstall_cmd}"
require_file "project license notice" "${package_root}/notices/LICENSE"
require_file "third-party notices" "${package_root}/notices/THIRD_PARTY_NOTICES.md"
if bash -n "${install_cmd}" && bash -n "${uninstall_cmd}"; then
  note "PASS: install/uninstall command syntax"
else
  record_failure "install/uninstall command syntax failed"
fi
require_contains "installer includes app install" "${install_cmd}" 'APP_TARGET="${HOME}/Applications/Proxy Gateway Desktop.app"'
require_contains "installer includes kit install" "${install_cmd}" 'install-macvpn-kit.sh'
require_contains "installer gates rootctl to Darwin" "${install_cmd}" 'uname -s'
require_contains "uninstaller disables login agent" "${uninstall_cmd}" 'local.proxygateway.desktop.login.plist'
require_contains "uninstaller clears app preferences" "${uninstall_cmd}" 'defaults delete local.proxygateway.desktop'
require_contains "uninstaller delegates full kit cleanup" "${uninstall_cmd}" 'macvpnctl.sh" uninstall'

app="${package_root}/payload/app/Proxy Gateway Desktop.app"
app_binary="${app}/Contents/MacOS/ProxyGatewayDesktop"
require_dir "app bundle payload" "${app}"
require_file "app Info.plist" "${app}/Contents/Info.plist"
require_file "app icon" "${app}/Contents/Resources/AppIcon.icns"
require_executable "app binary" "${app_binary}"
if plutil -lint "${app}/Contents/Info.plist" >/dev/null; then
  note "PASS: app Info.plist lint"
else
  record_failure "app Info.plist lint failed"
fi
short_version="$(plist_value "${app}/Contents/Info.plist" "CFBundleShortVersionString" | tr -d '\r')"
if [[ "${short_version}" == "0.2.0" ]]; then
  note "PASS: app short version"
else
  record_failure "app short version mismatch: ${short_version:-empty}"
fi
if grep -a -Fq "Proxy Gateway" "${app_binary}"; then
  note "PASS: app binary UI strings"
else
  record_failure "app binary missing expected UI strings"
fi
if grep -a -Fq "导入配置" "${app_binary}"; then
  note "PASS: app binary import UI string"
else
  record_failure "app binary missing 导入配置"
fi
if grep -a -Fq "卸载" "${app_binary}"; then
  note "PASS: app binary uninstall UI string"
else
  record_failure "app binary missing 卸载"
fi
if grep -a -Fq "需要配置" "${app_binary}"; then
  note "PASS: app binary v3 needs-config UI string"
else
  record_failure "app binary missing 需要配置"
fi
if grep -a -Fq "诊断详情" "${app_binary}"; then
  note "PASS: app binary v3 details UI string"
else
  record_failure "app binary missing 诊断详情"
fi
if codesign -dv "${app}" >/tmp/proxygateway-package-codesign.out 2>&1; then
  record_warning "app is signed; self-use package was expected to be unsigned"
else
  if grep -Fq "code object is not signed" /tmp/proxygateway-package-codesign.out; then
    note "PASS: unsigned self-use app boundary"
  else
    record_warning "codesign inspection returned non-signing failure: $(tr '\n' ' ' </tmp/proxygateway-package-codesign.out)"
  fi
fi

macvpn_payload="${package_root}/payload/macvpn"
require_executable "payload macvpnctl" "${macvpn_payload}/macvpnctl.sh"
require_executable "payload install-macvpn-kit" "${macvpn_payload}/install-macvpn-kit.sh"
require_executable "payload install-macvpn-rootctl" "${macvpn_payload}/install-macvpn-rootctl.sh"
require_file "payload sing-box template" "${macvpn_payload}/sing-box.tun.template.json"
require_executable "payload sing-box binary" "${macvpn_payload}/bin/sing-box"

if "${macvpn_payload}/bin/sing-box" version | grep -Fq "sing-box version"; then
  note "PASS: bundled sing-box runs"
else
  record_failure "bundled sing-box version failed"
fi

if python3 -m json.tool "${macvpn_payload}/sing-box.tun.template.json" >/dev/null; then
  note "PASS: sing-box template JSON"
else
  record_failure "sing-box template JSON invalid"
fi
if python3 -m json.tool "${package_root}/payload/profile/profile.template.json" >/dev/null; then
  note "PASS: profile template JSON"
else
  record_failure "profile template JSON invalid"
fi

"${macvpn_payload}/install-macvpn-kit.sh" --target "${SMOKE_TARGET}" >/tmp/proxygateway-package-kit-install.out
require_executable "sandbox installed macvpnctl" "${SMOKE_TARGET}/macvpnctl.sh"
require_file "sandbox installed template" "${SMOKE_TARGET}/sing-box.tun.template.json"
require_executable "sandbox installed sing-box" "${SMOKE_TARGET}/bin/sing-box"

HOME="${SMOKE_HOME}" "${SMOKE_TARGET}/macvpnctl.sh" profile-status | tee "${REMOTE_DIR}/profile-status-before.txt"
if grep -Fq "profile-source: missing" "${REMOTE_DIR}/profile-status-before.txt"; then
  note "PASS: sandbox initial profile missing"
else
  record_failure "sandbox initial profile state was not missing"
fi

cat >"${SMOKE_HOME}/upstream.json" <<'JSON'
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
HOME="${SMOKE_HOME}" "${SMOKE_TARGET}/macvpnctl.sh" import-upstream --from "${SMOKE_HOME}/upstream.json" | tee "${REMOTE_DIR}/import-upstream.txt"
HOME="${SMOKE_HOME}" "${SMOKE_TARGET}/macvpnctl.sh" validate | tee "${REMOTE_DIR}/validate.txt"
require_file "sandbox rendered sing-box config" "${SMOKE_TARGET}/config/sing-box.json"
require_contains "sandbox rendered direct smoke outbound" "${SMOKE_TARGET}/config/sing-box.json" "direct-smoke"

cat >"${SMOKE_HOME}/profile.json.enc" <<'JSON'
{
  "product": "PROXY_GATEWAY_PROFILE",
  "version": 2,
  "algorithm": "AES-256-GCM",
  "kdf": "PBKDF2-HMAC-SHA256",
  "iterations": 1000,
  "salt": "sandbox-salt",
  "nonce": "sandbox-nonce",
  "ciphertext": "sandbox-ciphertext"
}
JSON
HOME="${SMOKE_HOME}" "${SMOKE_TARGET}/macvpnctl.sh" import-encrypted-profile --from "${SMOKE_HOME}/profile.json.enc" | tee "${REMOTE_DIR}/import-encrypted-profile.txt"
HOME="${SMOKE_HOME}" "${SMOKE_TARGET}/macvpnctl.sh" profile-status | tee "${REMOTE_DIR}/profile-status-after.txt"
if grep -Fq "profile-source: encrypted" "${REMOTE_DIR}/profile-status-after.txt"; then
  note "PASS: sandbox encrypted profile precedence"
else
  record_failure "sandbox encrypted profile status missing"
fi

HOME="${SMOKE_HOME}" PROXY_GATEWAY_SKIP_ROOT_UNINSTALL=1 "${SMOKE_TARGET}/macvpnctl.sh" stop | tee "${REMOTE_DIR}/stop.txt"
require_file "stop preserves upstream profile" "${SMOKE_TARGET}/config/upstream.json"
require_file "stop preserves encrypted profile" "${SMOKE_TARGET}/config/profile.json.enc"
require_file "stop preserves rendered config" "${SMOKE_TARGET}/config/sing-box.json"

mkdir -p \
  "${SMOKE_HOME}/Applications/Proxy Gateway Desktop.app" \
  "${SMOKE_HOME}/Desktop/Proxy Gateway Desktop.app" \
  "${SMOKE_HOME}/Library/LaunchAgents" \
  "${SMOKE_HOME}/Library/Application Support/Proxy Gateway" \
  "${SMOKE_HOME}/Library/Caches/local.proxygateway.desktop" \
  "${SMOKE_HOME}/Library/Preferences" \
  "${SMOKE_HOME}/Library/Saved Application State/local.proxygateway.desktop.savedState"
touch \
  "${SMOKE_HOME}/Library/LaunchAgents/local.proxygateway.desktop.login.plist" \
  "${SMOKE_HOME}/Library/LaunchAgents/com.proxygateway.macvpn.plist" \
  "${SMOKE_HOME}/Library/Preferences/local.proxygateway.desktop.plist"

HOME="${SMOKE_HOME}" PROXY_GATEWAY_SKIP_ROOT_UNINSTALL=1 "${SMOKE_TARGET}/macvpnctl.sh" uninstall | tee "${REMOTE_DIR}/uninstall.txt"
require_missing "uninstall removes Mac VPN kit and config" "${SMOKE_TARGET}"
require_missing "uninstall removes installed app" "${SMOKE_HOME}/Applications/Proxy Gateway Desktop.app"
require_missing "uninstall removes desktop app copy" "${SMOKE_HOME}/Desktop/Proxy Gateway Desktop.app"
require_missing "uninstall removes desktop login agent" "${SMOKE_HOME}/Library/LaunchAgents/local.proxygateway.desktop.login.plist"
require_missing "uninstall removes user VPN launch agent" "${SMOKE_HOME}/Library/LaunchAgents/com.proxygateway.macvpn.plist"
require_missing "uninstall removes app support" "${SMOKE_HOME}/Library/Application Support/Proxy Gateway"
require_missing "uninstall removes app cache" "${SMOKE_HOME}/Library/Caches/local.proxygateway.desktop"
require_missing "uninstall removes app preferences plist" "${SMOKE_HOME}/Library/Preferences/local.proxygateway.desktop.plist"
require_missing "uninstall removes saved state" "${SMOKE_HOME}/Library/Saved Application State/local.proxygateway.desktop.savedState"

if [[ -x "${HOME}/ProxyGatewayMacVPN/macvpnctl.sh" ]]; then
  if "${HOME}/ProxyGatewayMacVPN/macvpnctl.sh" status | sed -n '1,12p' >"${REMOTE_DIR}/current-kit-status.txt"; then
    note "PASS: current Mac kit status still queryable"
  else
    record_warning "current Mac kit status was not queryable"
  fi
fi

if ((${#failures[@]})); then
  printf '\nMac self-use package sandbox verification: fail\n' >&2
  printf ' - %s\n' "${failures[@]}" >&2
  exit 1
fi

if ((${#warnings[@]})); then
  printf '\nMac self-use package sandbox verification: pass with warnings\n'
  printf ' - %s\n' "${warnings[@]}"
  exit 0
fi

printf '\nMac self-use package sandbox verification: pass\n'
REMOTE_SCRIPT
