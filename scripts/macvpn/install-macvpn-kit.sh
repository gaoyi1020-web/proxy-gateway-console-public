#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/ProxyGatewayMacVPN"

usage() {
  cat <<EOF
usage: $0 [--target <dir>]

Stages the Mac VPN kit into the target directory. This script only copies
files and creates runtime directories; it does not start or stop services.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "--target requires a directory" >&2
        exit 2
      fi
      TARGET="$2"
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

install -d "${TARGET}" "${TARGET}/config" "${TARGET}/logs" "${TARGET}/state" "${TARGET}/bin"
install -m 0755 "${SCRIPT_DIR}/macvpnctl.sh" "${TARGET}/macvpnctl.sh"
install -m 0644 "${SCRIPT_DIR}/sing-box.tun.template.json" "${TARGET}/sing-box.tun.template.json"
if [[ -x "${SCRIPT_DIR}/bin/sing-box" ]]; then
  install -m 0755 "${SCRIPT_DIR}/bin/sing-box" "${TARGET}/bin/sing-box"
fi

cat <<EOF
installed Mac VPN kit:
  target: ${TARGET}
next:
  ${TARGET}/macvpnctl.sh status
EOF
