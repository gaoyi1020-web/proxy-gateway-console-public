#!/usr/bin/env bash
set -euo pipefail

MAC_HOST="${MAC_HOST:-example-mac.local}"
MAC_USER="${MAC_USER:-${USER:-user}}"
MAC_SSH_KEY="${MAC_SSH_KEY:-${HOME}/.ssh/proxy_gateway_mac_ed25519}"
REQUIRE_APP_RUNNING="${REQUIRE_APP_RUNNING:-0}"
SSH_OPTS=(-i "${MAC_SSH_KEY}" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
REMOTE="${MAC_USER}@${MAC_HOST}"

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

remote() {
  ssh "${SSH_OPTS[@]}" "${REMOTE}" "$@"
}

require_remote_contains() {
  local label="$1"
  local pattern="$2"
  local command="$3"
  local output
  if ! output="$(remote "${command}" 2>&1)"; then
    record_failure "${label}: command failed: ${output}"
    return
  fi
  if ! grep -Fq "${pattern}" <<<"${output}"; then
    record_failure "${label}: expected '${pattern}', got: ${output}"
    return
  fi
  note "PASS: ${label}"
}

note "Mac desktop state verification target: ${REMOTE}"

if remote "pgrep -fl ProxyGatewayDesktop" >/dev/null 2>&1; then
  note "PASS: app process"
elif [[ "${REQUIRE_APP_RUNNING}" == "1" ]]; then
  record_failure "app process is not running"
else
  record_warning "app process is not running; root VPN may still be healthy as a background service"
fi
require_remote_contains "bundle version" "\"CFBundleVersion\" => \"2\"" "plutil -p \"\${HOME}/Applications/Proxy Gateway Desktop.app/Contents/Info.plist\""
require_remote_contains "bundle short version" "\"CFBundleShortVersionString\" => \"0.2.0\"" "plutil -p \"\${HOME}/Applications/Proxy Gateway Desktop.app/Contents/Info.plist\""
require_remote_contains "bundle icon" "\"CFBundleIconFile\" => \"AppIcon\"" "plutil -p \"\${HOME}/Applications/Proxy Gateway Desktop.app/Contents/Info.plist\""
require_remote_contains "desktop icon asset" "AppIcon.icns" "ls \"\${HOME}/Desktop/Proxy Gateway Desktop.app/Contents/Resources/AppIcon.icns\""
require_remote_contains "login launch agent" "local.proxygateway.desktop.login.plist" "ls \"\${HOME}/Library/LaunchAgents/local.proxygateway.desktop.login.plist\""
require_remote_contains "background preference" "1" "defaults read local.proxygateway.desktop runInBackground"
require_remote_contains "rootctl loaded" "rootctl: loaded" "sudo -n /usr/local/sbin/proxygateway-macvpn-rootctl status"
require_remote_contains "rootctl process" "rootctl: process running" "sudo -n /usr/local/sbin/proxygateway-macvpn-rootctl status"
require_remote_contains "vpn root mode" "mode: root-running" "\"\${HOME}/ProxyGatewayMacVPN/macvpnctl.sh\" status | sed -n '1,12p'"
require_remote_contains "vpn root launchd" "launchd: user=not loaded, root=loaded" "\"\${HOME}/ProxyGatewayMacVPN/macvpnctl.sh\" status | sed -n '1,12p'"
require_remote_contains "wifi ipv6 off" "IPv6: Off" "networksetup -getinfo Wi-Fi"
require_remote_contains "chatgpt egress" "loc=US" "curl -sS --connect-timeout 12 --max-time 25 https://chatgpt.com/cdn-cgi/trace"

if remote "ifconfig en0 | grep -q 'inet6 2409:'"; then
  record_failure "native Wi-Fi IPv6 address still present on en0"
else
  note "PASS: no native Wi-Fi IPv6 address on en0"
fi

if remote "curl -sS -o /tmp/proxygateway-google-204.out -w '%{http_code}' --connect-timeout 12 --max-time 25 https://www.gstatic.com/generate_204 | grep -q '^204$'"; then
  note "PASS: google generate_204"
else
  record_failure "google generate_204 did not return 204"
fi

if ((${#failures[@]})); then
  printf '\nMac desktop state verification: fail\n' >&2
  printf ' - %s\n' "${failures[@]}" >&2
  exit 1
fi

if ((${#warnings[@]})); then
  printf '\nMac desktop state verification: pass with warnings\n'
  printf ' - %s\n' "${warnings[@]}"
  exit 0
fi

printf '\nMac desktop state verification: pass\n'
