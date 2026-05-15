#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${HOME}/.local/bin"
SERVICE_DIR="${HOME}/.config/systemd/user"
WRAPPER="${BIN_DIR}/gateway-agent"
SERVICE="${SERVICE_DIR}/gateway-agent.service"
MODE="${1:---dry-run}"

if [[ "${MODE}" != "--dry-run" && "${MODE}" != "--apply" ]]; then
  echo "usage: $0 [--dry-run|--apply]" >&2
  exit 2
fi

echo "gateway-agent wrapper: ${WRAPPER}"
echo "gateway-agent service: ${SERVICE}"

if [[ "${MODE}" == "--dry-run" ]]; then
  echo "dry-run only; no files changed"
  exit 0
fi

systemctl --user stop gateway-agent 2>/dev/null || true
systemctl --user disable gateway-agent 2>/dev/null || true
rm -f "${WRAPPER}" "${SERVICE}"
if ! systemctl --user daemon-reload; then
  echo "warning: systemctl --user daemon-reload failed; run it manually from a user session after uninstall" >&2
fi
echo "removed v2 wrapper/service; v1 proxy services were not changed"
