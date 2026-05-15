#!/usr/bin/env bash
set -euo pipefail

ROOTCTL="/usr/local/sbin/proxygateway-macvpn-rootctl"
SUDOERS="/etc/sudoers.d/proxygateway-macvpn-rootctl"
USER_NAME="${PROXY_GATEWAY_MAC_USER:-}"

usage() {
  cat <<EOF
usage: $0 [--user <mac_user>]

Installs a root-owned, least-scope controller for passwordless Mac VPN
start/stop/status from the desktop app after one administrator approval.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      [[ $# -ge 2 && -n "${2:-}" ]] || { echo "--user requires a value" >&2; exit 2; }
      USER_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$(id -u)" != "0" ]]; then
  echo "run as root through sudo or macOS administrator approval" >&2
  exit 2
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS only" >&2
  exit 2
fi

if [[ -z "${USER_NAME}" ]]; then
  USER_NAME="$(stat -f '%Su' /dev/console)"
fi

if ! id "${USER_NAME}" >/dev/null 2>&1; then
  echo "user not found: ${USER_NAME}" >&2
  exit 2
fi

install -d -m 0755 -o root -g wheel "$(dirname "${ROOTCTL}")"

tmp_rootctl="$(mktemp "${TMPDIR:-/tmp}/proxygateway-rootctl.XXXXXX")"
cat >"${tmp_rootctl}" <<'SCRIPT'
#!/bin/sh
set -eu

LABEL="com.proxygateway.macvpn"
ROOT_PLIST="/Library/LaunchDaemons/com.proxygateway.macvpn.plist"

usage() {
  echo "usage: $0 {start|stop|status}" >&2
}

require_plist() {
  if [ ! -f "${ROOT_PLIST}" ]; then
    echo "root plist missing: ${ROOT_PLIST}" >&2
    exit 2
  fi
}

case "${1:-}" in
  start)
    require_plist
    if /bin/launchctl print "system/${LABEL}" >/dev/null 2>&1; then
      /bin/launchctl kickstart -k "system/${LABEL}"
    else
      /bin/launchctl bootstrap system "${ROOT_PLIST}" >/dev/null 2>&1 || true
      /bin/launchctl kickstart -k "system/${LABEL}"
    fi
    echo "rootctl: started"
    ;;
  stop)
    require_plist
    /bin/launchctl bootout system "${ROOT_PLIST}" >/dev/null 2>&1 || true
    echo "rootctl: stopped"
    ;;
  status)
    if /bin/launchctl print "system/${LABEL}" >/dev/null 2>&1; then
      echo "rootctl: loaded"
    else
      echo "rootctl: not loaded"
    fi
    if /bin/ps ax -o command= | /usr/bin/grep -F "sing-box run -c" | /usr/bin/grep -F "ProxyGatewayMacVPN" | /usr/bin/grep -v grep >/dev/null 2>&1; then
      echo "rootctl: process running"
    else
      echo "rootctl: process not running"
    fi
    ;;
  *)
    usage
    exit 2
    ;;
esac
SCRIPT

install -m 0755 -o root -g wheel "${tmp_rootctl}" "${ROOTCTL}"
rm -f "${tmp_rootctl}"

tmp_sudoers="$(mktemp "${TMPDIR:-/tmp}/proxygateway-sudoers.XXXXXX")"
cat >"${tmp_sudoers}" <<EOF
${USER_NAME} ALL=(root) NOPASSWD: ${ROOTCTL} start, ${ROOTCTL} stop, ${ROOTCTL} status
EOF

/usr/sbin/visudo -cf "${tmp_sudoers}" >/dev/null
install -m 0440 -o root -g wheel "${tmp_sudoers}" "${SUDOERS}"
rm -f "${tmp_sudoers}"
/usr/sbin/visudo -cf "${SUDOERS}" >/dev/null

echo "installed root controller: ${ROOTCTL}"
echo "installed sudoers rule: ${SUDOERS}"
echo "allowed user: ${USER_NAME}"
