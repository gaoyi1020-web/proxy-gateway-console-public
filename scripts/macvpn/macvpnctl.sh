#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${HOME}/ProxyGatewayMacVPN"
CONFIG_DIR="${APP_DIR}/config"
STATE_DIR="${APP_DIR}/state"
LOG_DIR="${APP_DIR}/logs"
BIN_DIR="${APP_DIR}/bin"
UPSTREAM_PROFILE="${CONFIG_DIR}/upstream.json"
ENCRYPTED_PROFILE="${CONFIG_DIR}/profile.json.enc"
RENDERED_CONFIG="${CONFIG_DIR}/sing-box.json"
TEMPLATE_CONFIG="${APP_DIR}/sing-box.tun.template.json"
UPDATE_SCRIPT="${APP_DIR}/proxy-gateway-self-update.sh"
PLIST="${HOME}/Library/LaunchAgents/com.proxygateway.macvpn.plist"
ROOT_PLIST="/Library/LaunchDaemons/com.proxygateway.macvpn.plist"
LABEL="com.proxygateway.macvpn"
ROOTCTL="/usr/local/sbin/proxygateway-macvpn-rootctl"
ROOTCTL_SUDOERS="/etc/sudoers.d/proxygateway-macvpn-rootctl"
DESKTOP_APP="${HOME}/Applications/Proxy Gateway Desktop.app"
DESKTOP_COPY="${HOME}/Desktop/Proxy Gateway Desktop.app"
DESKTOP_LOGIN_AGENT="${HOME}/Library/LaunchAgents/local.proxygateway.desktop.login.plist"
DESKTOP_BUNDLE_ID="local.proxygateway.desktop"
DESKTOP_SUPPORT_DIR="${HOME}/Library/Application Support/Proxy Gateway"
DESKTOP_CACHE_DIR="${HOME}/Library/Caches/local.proxygateway.desktop"
DESKTOP_PREFS="${HOME}/Library/Preferences/local.proxygateway.desktop.plist"
DESKTOP_SAVED_STATE="${HOME}/Library/Saved Application State/local.proxygateway.desktop.savedState"

require_env_value() {
  local name="$1"
  local value="${!name:-}"
  if [[ -z "${value}" ]]; then
    printf 'missing required environment variable: %s\n' "${name}" >&2
    return 2
  fi
  printf '%s' "${value}"
}

usage() {
  cat <<EOF
usage: $0 <command> [args]

commands:
  status
  profile-status
  import-upstream --from <path>
  import-encrypted-profile --from <path>
  render-config
  validate
  install-binary --url <url> --sha256 <expected_sha256>
  install-binary --archive <path> --sha256 <expected_sha256>
  install-launchd
  install-daemon
  start
  start-root
  stop
  stop-root
  test
  snapshot
  update-check
  update-download
  update-install
  prepare-independent-underlay
  restore-lan-gateway
  uninstall
EOF
}

ensure_dirs() {
  install -d "${CONFIG_DIR}" "${STATE_DIR}" "${LOG_DIR}" "${BIN_DIR}"
}

redact_json_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    printf 'missing\n'
    return 0
  fi
  python3 - "$path" <<'PY'
import json
import sys

path = sys.argv[1]
redact_keys = {"password", "auth", "token", "uuid", "server", "server_port", "username"}

def scrub(value):
    if isinstance(value, dict):
        return {key: ("<redacted>" if key.lower() in redact_keys else scrub(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value

with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
print(json.dumps(scrub(data), indent=2, sort_keys=True))
PY
}

status() {
  ensure_dirs
  local upstream_state rendered_state binary_state plist_state launchd_state root_process_state mode_state
  local user_launchd_state root_launchd_state rootctl_status
  upstream_state="$([[ -f "${UPSTREAM_PROFILE}" ]] && printf present || printf missing)"
  rendered_state="$([[ -f "${RENDERED_CONFIG}" ]] && printf present || printf missing)"
  binary_state="$([[ -x "${BIN_DIR}/sing-box" ]] && printf present || printf missing)"
  plist_state="$([[ -f "${PLIST}" ]] && printf present || printf missing)"
  mode_state="staged"
  user_launchd_state="not loaded"
  root_launchd_state="unknown"
  printf 'Mac VPN kit status:\n'
  if command -v launchctl >/dev/null 2>&1; then
    if launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1; then
      user_launchd_state="loaded"
      mode_state="running"
    fi
  else
    user_launchd_state="launchctl unavailable"
  fi
  if [[ -x "${ROOTCTL}" ]]; then
    rootctl_status="$(sudo -n "${ROOTCTL}" status 2>/dev/null || true)"
    if printf '%s\n' "${rootctl_status}" | grep -F "rootctl: loaded" >/dev/null 2>&1; then
      root_launchd_state="loaded"
    elif printf '%s\n' "${rootctl_status}" | grep -F "rootctl: not loaded" >/dev/null 2>&1; then
      root_launchd_state="not loaded"
    else
      root_launchd_state="not accessible"
    fi
  elif [[ -f "${ROOT_PLIST}" ]]; then
    root_launchd_state="rootctl missing"
  else
    root_launchd_state="not staged"
  fi
  launchd_state="user=${user_launchd_state}, root=${root_launchd_state}"
  if ps ax -o command= | grep -F "${BIN_DIR}/sing-box run -c ${RENDERED_CONFIG}" | grep -v grep >/dev/null 2>&1; then
    root_process_state="running"
    mode_state="root-running"
  else
    root_process_state="not running"
  fi
  printf '  mode: %s\n' "${mode_state}"
  printf '  app_dir: %s\n' "${APP_DIR}"
  printf '  upstream profile: %s\n' "${upstream_state}"
  printf '  rendered config: %s\n' "${rendered_state}"
  printf '  sing-box: %s\n' "${binary_state}"
  printf '  launchd plist: %s\n' "${plist_state}"
  printf '  launchd: %s\n' "${launchd_state}"
  printf '  root process: %s\n' "${root_process_state}"
  if [[ -f "${UPSTREAM_PROFILE}" ]]; then
    printf '  upstream_profile_redacted:\n'
    redact_json_file "${UPSTREAM_PROFILE}" | sed 's/^/    /'
  fi
}

snapshot() {
  ensure_dirs
  {
    printf '## networksetup -getinfo Wi-Fi\n'
    networksetup -getinfo Wi-Fi || true
    printf '\n## networksetup -getwebproxy Wi-Fi\n'
    networksetup -getwebproxy Wi-Fi || true
    printf '\n## networksetup -getsecurewebproxy Wi-Fi\n'
    networksetup -getsecurewebproxy Wi-Fi || true
    printf '\n## netstat -rn -f inet\n'
    netstat -rn -f inet || true
    printf '\n## scutil --dns\n'
    scutil --dns || true
  } > "${STATE_DIR}/network-snapshot.txt"
  printf 'snapshot written: %s\n' "${STATE_DIR}/network-snapshot.txt"
}

run_update() {
  local mode="$1"
  shift || true
  if [[ ! -x "${UPDATE_SCRIPT}" ]]; then
    printf 'updater missing: %s\n' "${UPDATE_SCRIPT}" >&2
    return 1
  fi
  "${UPDATE_SCRIPT}" "${mode}" "$@"
}

profile_status() {
  ensure_dirs
  printf 'Mac VPN profile status:\n'
  if [[ -f "${ENCRYPTED_PROFILE}" ]]; then
    printf '  profile-source: encrypted\n'
  elif [[ -f "${UPSTREAM_PROFILE}" ]]; then
    printf '  profile-source: mac-adapter\n'
  else
    printf '  profile-source: missing\n'
  fi
  printf '  upstream profile: %s\n' "$([[ -f "${UPSTREAM_PROFILE}" ]] && printf present || printf missing)"
  printf '  encrypted profile: %s\n' "$([[ -f "${ENCRYPTED_PROFILE}" ]] && printf present || printf missing)"
}

import_upstream() {
  local source=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --from)
        [[ $# -ge 2 && -n "${2:-}" ]] || { echo "--from requires a path" >&2; exit 2; }
        source="$2"
        shift 2
        ;;
      *)
        echo "unknown import-upstream argument: $1" >&2
        exit 2
        ;;
    esac
  done
  [[ -n "${source}" ]] || { echo "import-upstream requires --from" >&2; exit 2; }
  [[ -f "${source}" ]] || { echo "upstream source missing: ${source}" >&2; exit 2; }
  ensure_dirs
  python3 -m json.tool "${source}" >/dev/null
  install -m 0600 "${source}" "${UPSTREAM_PROFILE}"
  "$0" render-config
  printf 'import-upstream: ok\n'
}

import_encrypted_profile() {
  local source=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --from)
        [[ $# -ge 2 && -n "${2:-}" ]] || { echo "--from requires a path" >&2; exit 2; }
        source="$2"
        shift 2
        ;;
      *)
        echo "unknown import-encrypted-profile argument: $1" >&2
        exit 2
        ;;
    esac
  done
  [[ -n "${source}" ]] || { echo "import-encrypted-profile requires --from" >&2; exit 2; }
  [[ -f "${source}" ]] || { echo "encrypted profile source missing: ${source}" >&2; exit 2; }
  ensure_dirs
  python3 - "${source}" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    envelope = json.load(handle)
required = {"product", "version", "algorithm", "kdf", "iterations", "salt", "nonce", "ciphertext"}
missing = sorted(required - set(envelope))
if missing:
    raise SystemExit("encrypted profile missing fields: " + ", ".join(missing))
if envelope.get("product") != "PROXY_GATEWAY_PROFILE":
    raise SystemExit("encrypted profile product mismatch")
PY
  install -m 0600 "${source}" "${ENCRYPTED_PROFILE}"
  printf 'import-encrypted-profile: ok\n'
}

render_config() {
  ensure_dirs
  python3 - "${TEMPLATE_CONFIG}" "${UPSTREAM_PROFILE}" "${RENDERED_CONFIG}" "${LOG_DIR}/sing-box.log" <<'PY'
import json
import os
import sys
import tempfile

template_path, profile_path, output_path, log_path = sys.argv[1:5]

with open(template_path, "r", encoding="utf-8") as handle:
    config = json.load(handle)
with open(profile_path, "r", encoding="utf-8") as handle:
    profile = json.load(handle)

if isinstance(profile, dict):
    upstreams = profile.get("outbounds")
    selected = profile.get("final") or profile.get("selected") or profile.get("tag")
elif isinstance(profile, list):
    upstreams = profile
    selected = None
else:
    raise SystemExit("upstream profile must be an object or array")

if not isinstance(upstreams, list) or len(upstreams) < 1:
    raise SystemExit("upstream profile requires at least one outbound")

for index, outbound in enumerate(upstreams):
    if not isinstance(outbound, dict):
        raise SystemExit(f"outbound #{index + 1} must be an object")
    tag = outbound.get("tag")
    if not isinstance(tag, str) or not tag:
        raise SystemExit(f"outbound #{index + 1} requires a non-empty tag")

if selected is None:
    selected = upstreams[0]["tag"]
if selected not in {outbound["tag"] for outbound in upstreams}:
    raise SystemExit("selected upstream tag is not present in outbounds")

config.setdefault("log", {})["output"] = log_path
config.setdefault("outbounds", []).extend(upstreams)
config.setdefault("route", {})["final"] = selected

directory = os.path.dirname(output_path)
os.makedirs(directory, exist_ok=True)
fd, tmp_path = tempfile.mkstemp(prefix=".sing-box.", suffix=".json", dir=directory)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp_path, output_path)
finally:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
PY
  printf 'render-config: ok\n'
  printf 'rendered config: %s\n' "${RENDERED_CONFIG}"
}

validate() {
  if [[ ! -f "${RENDERED_CONFIG}" ]]; then
    echo "rendered config missing; run render-config first" >&2
    exit 2
  fi
  python3 -m json.tool "${RENDERED_CONFIG}" >/dev/null
  if [[ -x "${BIN_DIR}/sing-box" ]]; then
    "${BIN_DIR}/sing-box" check -c "${RENDERED_CONFIG}"
  else
    echo "sing-box binary missing; JSON validation only"
  fi
  printf 'validate: ok\n'
}

install_binary() {
  local url=""
  local archive_source=""
  local expected_sha256=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --url)
        [[ $# -ge 2 ]] || { echo "--url requires a value" >&2; exit 2; }
        url="$2"
        shift 2
        ;;
      --archive)
        [[ $# -ge 2 ]] || { echo "--archive requires a value" >&2; exit 2; }
        archive_source="$2"
        shift 2
        ;;
      --sha256)
        [[ $# -ge 2 ]] || { echo "sha256 required" >&2; exit 2; }
        expected_sha256="$2"
        shift 2
        ;;
      *)
        echo "unknown install-binary argument: $1" >&2
        exit 2
        ;;
    esac
  done
  if [[ -n "${url}" && -n "${archive_source}" ]]; then
    echo "use either --url or --archive, not both" >&2
    exit 2
  fi
  if [[ -z "${url}" && -z "${archive_source}" ]]; then
    echo "url or archive required" >&2
    exit 2
  fi
  if [[ -z "${expected_sha256}" ]]; then
    echo "sha256 required" >&2
    exit 2
  fi
  expected_sha256="${expected_sha256#sha256:}"

  ensure_dirs
  local work_dir archive actual_sha
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/macvpn-sing-box.XXXXXX")"
  trap 'rm -rf "${work_dir}"' RETURN
  archive="${work_dir}/sing-box.tar.gz"
  if [[ -n "${archive_source}" ]]; then
    if [[ ! -f "${archive_source}" ]]; then
      echo "archive not found: ${archive_source}" >&2
      exit 2
    fi
    cp "${archive_source}" "${archive}"
  else
    curl --fail --location --show-error --retry 5 --retry-all-errors --connect-timeout 20 --max-time 300 "${url}" -o "${archive}"
  fi
  actual_sha="$(shasum -a 256 "${archive}" | awk '{print $1}')"
  if [[ "${actual_sha}" != "${expected_sha256}" ]]; then
    echo "sha256 mismatch" >&2
    exit 1
  fi
  tar -xzf "${archive}" -C "${work_dir}"
  local found
  found="$(find "${work_dir}" -type f -name sing-box -perm -111 | head -n 1)"
  if [[ -z "${found}" ]]; then
    echo "sing-box executable not found in archive" >&2
    exit 1
  fi
  install -m 0755 "${found}" "${BIN_DIR}/sing-box"
  printf 'installed binary: %s\n' "${BIN_DIR}/sing-box"
}

install_launchd() {
  ensure_dirs
  install -d "$(dirname "${PLIST}")"
  cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${BIN_DIR}/sing-box</string>
    <string>run</string>
    <string>-c</string>
    <string>${RENDERED_CONFIG}</string>
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/launchd.err.log</string>
</dict>
</plist>
EOF
  printf 'launchd plist staged: %s\n' "${PLIST}"
}

install_daemon() {
  ensure_dirs
  local staged_plist="${STATE_DIR}/com.proxygateway.macvpn.daemon.plist"
  cat > "${staged_plist}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${BIN_DIR}/sing-box</string>
    <string>run</string>
    <string>-c</string>
    <string>${RENDERED_CONFIG}</string>
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/daemon.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/daemon.err.log</string>
</dict>
</plist>
EOF
  sudo install -m 0644 -o root -g wheel "${staged_plist}" "${ROOT_PLIST}"
  printf 'launchd daemon staged: %s\n' "${ROOT_PLIST}"
}

start_service() {
  "$0" snapshot
  "$0" render-config
  "$0" validate
  if [[ ! -f "${PLIST}" ]]; then
    "$0" install-launchd
  fi
  if launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1; then
    launchctl kickstart -k "gui/$(id -u)/${LABEL}"
  else
    launchctl bootstrap "gui/$(id -u)" "${PLIST}"
    launchctl kickstart -k "gui/$(id -u)/${LABEL}"
  fi
  printf 'launchd: started\n'
}

stop_service() {
  if command -v launchctl >/dev/null 2>&1; then
    launchctl bootout "gui/$(id -u)" "${PLIST}" >/dev/null 2>&1 || true
  fi
  printf 'launchd: stopped\n'
}

start_root_service() {
  "$0" snapshot
  "$0" render-config
  "$0" validate
  "$0" install-daemon
  if sudo launchctl print "system/${LABEL}" >/dev/null 2>&1; then
    sudo launchctl kickstart -k "system/${LABEL}"
  else
    sudo launchctl bootstrap system "${ROOT_PLIST}" || true
    sudo launchctl kickstart -k "system/${LABEL}"
  fi
  printf 'launchd root: started\n'
}

stop_root_service() {
  sudo launchctl bootout system "${ROOT_PLIST}" >/dev/null 2>&1 || true
  printf 'launchd root: stopped\n'
}

restore_lan_gateway() {
  local client_ip router_ip subnet_mask proxy_host
  client_ip="$(require_env_value LAN_GATEWAY_CLIENT_IP)"
  router_ip="$(require_env_value LAN_GATEWAY_ROUTER_IP)"
  proxy_host="${LAN_GATEWAY_PROXY_HOST:-${router_ip}}"
  subnet_mask="${LAN_GATEWAY_SUBNET_MASK:-255.255.255.0}"
  networksetup -setmanual Wi-Fi "${client_ip}" "${subnet_mask}" "${router_ip}"
  networksetup -setdnsservers Wi-Fi "${router_ip}"
  networksetup -setwebproxy Wi-Fi "${proxy_host}" 18181
  networksetup -setsecurewebproxy Wi-Fi "${proxy_host}" 18181
  networksetup -setwebproxystate Wi-Fi on
  networksetup -setsecurewebproxystate Wi-Fi on
  printf 'lan gateway: restored\n'
}

prepare_independent_underlay() {
  local client_ip router_ip subnet_mask
  client_ip="$(require_env_value LAN_GATEWAY_CLIENT_IP)"
  router_ip="$(require_env_value LAN_GATEWAY_UPSTREAM_ROUTER_IP)"
  subnet_mask="${LAN_GATEWAY_SUBNET_MASK:-255.255.255.0}"
  "$0" snapshot
  networksetup -setmanual Wi-Fi "${client_ip}" "${subnet_mask}" "${router_ip}"
  networksetup -setdnsservers Wi-Fi "${router_ip}"
  networksetup -setwebproxystate Wi-Fi off
  networksetup -setsecurewebproxystate Wi-Fi off
  printf 'independent underlay: prepared\n'
}

test_config() {
  "$0" validate
  local user_loaded="no"
  local root_running="no"
  if command -v launchctl >/dev/null 2>&1 && launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1; then
    user_loaded="yes"
  fi
  if ps ax -o command= | grep -F "${BIN_DIR}/sing-box run -c ${RENDERED_CONFIG}" | grep -v grep >/dev/null 2>&1; then
    root_running="yes"
  fi
  if [[ "${user_loaded}" != "yes" && "${root_running}" != "yes" ]]; then
    printf 'connectivity: not verified (launchd not loaded)\n'
    return 1
  fi
  if command -v curl >/dev/null 2>&1; then
    if curl -4 -fsS --max-time 12 https://www.google.com/generate_204 >/dev/null; then
      printf 'connectivity: pass\n'
    else
      printf 'connectivity: not verified\n'
      return 1
    fi
  else
    printf 'connectivity: curl unavailable\n'
    return 1
  fi
}

sudo_available() {
  if [[ "${PROXY_GATEWAY_SKIP_ROOT_UNINSTALL:-0}" == "1" ]]; then
    return 1
  fi
  if [[ "$(uname -s)" != "Darwin" ]]; then
    return 1
  fi
  if [[ -n "${PROXY_GATEWAY_SUDO_PASSWORD:-}" ]]; then
    return 0
  fi
  sudo -n true >/dev/null 2>&1
}

sudo_run() {
  if [[ "${PROXY_GATEWAY_SKIP_ROOT_UNINSTALL:-0}" == "1" ]]; then
    return 1
  fi
  if [[ "$(uname -s)" != "Darwin" ]]; then
    return 1
  fi
  if [[ -n "${PROXY_GATEWAY_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "${PROXY_GATEWAY_SUDO_PASSWORD}" | sudo -S -p '' "$@"
    return $?
  fi
  if sudo -n true >/dev/null 2>&1; then
    sudo -n "$@"
    return $?
  fi
  if [[ -t 0 ]]; then
    sudo "$@"
    return $?
  fi
  return 1
}

remove_path() {
  local path="$1"
  rm -rf "${path}"
  printf 'removed: %s\n' "${path}"
}

remove_root_path() {
  local path="$1"
  if sudo_run rm -rf "${path}"; then
    printf 'removed root path: %s\n' "${path}"
  else
    printf 'root cleanup skipped or failed: %s\n' "${path}"
  fi
}

uninstall() {
  "$0" stop

  if command -v launchctl >/dev/null 2>&1; then
    launchctl bootout "gui/$(id -u)" "${DESKTOP_LOGIN_AGENT}" >/dev/null 2>&1 || true
    launchctl bootout "gui/$(id -u)" "${PLIST}" >/dev/null 2>&1 || true
  fi

  if sudo_available; then
    sudo_run launchctl bootout system "${ROOT_PLIST}" >/dev/null 2>&1 || true
  fi

  rm -f "${PLIST}" "${DESKTOP_LOGIN_AGENT}"
  defaults delete "${DESKTOP_BUNDLE_ID}" >/dev/null 2>&1 || true

  remove_path "${DESKTOP_APP}"
  remove_path "${DESKTOP_COPY}"
  remove_path "${DESKTOP_SUPPORT_DIR}"
  remove_path "${DESKTOP_CACHE_DIR}"
  remove_path "${DESKTOP_PREFS}"
  remove_path "${DESKTOP_SAVED_STATE}"

  remove_root_path "${ROOT_PLIST}"
  remove_root_path "${ROOTCTL}"
  remove_root_path "${ROOTCTL_SUDOERS}"

  remove_path "${APP_DIR}"
  printf 'Proxy Gateway uninstall: project-owned app, config, runtime files, startup items, and preferences removed.\n'
}

command="${1:-status}"
shift || true

case "${command}" in
  status) status "$@" ;;
  profile-status) profile_status "$@" ;;
  import-upstream) import_upstream "$@" ;;
  import-encrypted-profile) import_encrypted_profile "$@" ;;
  render-config) render_config "$@" ;;
  validate) validate "$@" ;;
  install-binary) install_binary "$@" ;;
  install-launchd) install_launchd "$@" ;;
  install-daemon) install_daemon "$@" ;;
  start) start_service "$@" ;;
  start-root) start_root_service "$@" ;;
  stop) stop_service "$@" ;;
  stop-root) stop_root_service "$@" ;;
  test) test_config "$@" ;;
  snapshot) snapshot "$@" ;;
  update-check) run_update --check "$@" ;;
  update-download) run_update --download "$@" ;;
  update-install) run_update --install "$@" ;;
  prepare-independent-underlay) prepare_independent_underlay "$@" ;;
  restore-lan-gateway) restore_lan_gateway "$@" ;;
  uninstall) uninstall "$@" ;;
  -h|--help|help) usage ;;
  *)
    echo "unknown command: ${command}" >&2
    usage >&2
    exit 2
    ;;
esac
