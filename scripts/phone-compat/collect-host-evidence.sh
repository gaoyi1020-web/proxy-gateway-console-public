#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${ROOT_DIR}/docs/phone-compat/evidence/generated"
STAMP="$(date '+%Y%m%d-%H%M%S')"
OUT_FILE="${OUT_DIR}/${STAMP}-host-evidence.md"

redact() {
  sed -E \
    -e 's/(token|password|authorization|cookie|secret)=([^[:space:]]+)/\1=[redacted]/gi' \
    -e 's/lladdr ([0-9a-f]{2}:){5}[0-9a-f]{2}/lladdr [mac-redacted]/gi'
}

mkdir -p "${OUT_DIR}"

{
  printf '# Phone Host Evidence - %s\n\n' "$(date '+%Y-%m-%d %H:%M:%S %z')"

  printf '## Listening Ports\n\n```text\n'
  ss -ltnp | rg '(:4077|:18181|:18180|:18122|:11880|:8118)\b' || true
  printf '```\n\n'

  printf '## LAN Neighbors\n\n```text\n'
  ip neigh show dev wlp0s20f3 | redact || true
  printf '```\n\n'

  printf '## CGC Network Scan Summary\n\n```text\n'
  (cd "${ROOT_DIR}" && scripts/cgc network-scan) 2>&1 |
    redact |
    rg '"id": "naked-domestic-baidu"|"id": "naked-foreign-google"|"id": "unified-http-google"|"id": "unified-http-chatgpt-trace"|"id": "lan-proxy-google"|"ok": |"status": |"httpCode": |"elapsedSeconds": |"summary": |"phase": |"dispatcherActive": |"blockers": ' |
    head -n 120 || true
  printf '```\n\n'

  printf '## Recent Phone Google/Apple Proxy Decisions\n\n```text\n'
  rg 'google|gstatic|googleusercontent|apple' "${HOME}/.local/share/proxy-stack/iphone-lan-proxy.log" 2>/dev/null |
    tail -n 40 |
    redact || true
  printf '```\n'
} | sed -E 's/[[:space:]]+$//' >"${OUT_FILE}"

printf 'wrote: %s\n' "${OUT_FILE#${ROOT_DIR}/}"
