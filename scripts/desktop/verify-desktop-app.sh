#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

bash -n scripts/desktop/build-agent-sidecar.sh
npm run test
npm run build
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY npm run desktop:check
scripts/desktop/build-agent-sidecar.sh --dry-run

credential_terms='api[_-]?key|password|passwd|auth|credential|private[_-]?endpoint'
scan_expr="(${credential_terms})[[:space:]]*[:=]"
for scheme in ss vmess trojan; do
  scan_expr="${scheme}://|${scan_expr}"
done
if [[ -n "${KNOWN_SUDO_TOKEN_PATTERN:-}" ]]; then
  scan_expr="${KNOWN_SUDO_TOKEN_PATTERN}|${scan_expr}"
fi

if rg -n "${scan_expr}" --glob '!node_modules/**' --glob '!dist/**' --glob '!package-lock.json' .; then
  echo "secret scan found matches" >&2
  exit 1
fi
