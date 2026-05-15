#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
echo "source project: ${ROOT_DIR}"

if [[ "${MODE}" == "--dry-run" ]]; then
  echo "dry-run only; no files changed"
  exit 0
fi

mkdir -p "${BIN_DIR}" "${SERVICE_DIR}"
cat > "${WRAPPER}" <<EOF
#!/usr/bin/env bash
exec python3 "${ROOT_DIR}/agent/gateway_agent.py" "\$@"
EOF
chmod 0755 "${WRAPPER}"
sed \
  -e "s|@PROJECT_ROOT@|${ROOT_DIR}|g" \
  -e "s|@GATEWAY_AGENT_WRAPPER@|${WRAPPER}|g" \
  "${ROOT_DIR}/packaging/systemd/gateway-agent.service" > "${SERVICE}"
if ! systemctl --user daemon-reload; then
  echo "warning: systemctl --user daemon-reload failed; run it manually from a user session before starting the service" >&2
fi
echo "installed but not enabled; run: systemctl --user start gateway-agent"
