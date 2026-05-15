#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-/tmp/proxy-gateway-v2-aws-package.tar.gz}"

case "${OUT}" in
  /|/home|"${HOME}"|"${ROOT_DIR}")
    echo "refusing unsafe package path: ${OUT}" >&2
    exit 2
    ;;
esac

mkdir -p "$(dirname "${OUT}")"
tar \
  --exclude='./.git' \
  --exclude='./node_modules' \
  --exclude='./dist' \
  --exclude='./.env' \
  --exclude='./.env.*' \
  --exclude='./coverage' \
  --exclude='./*.log' \
  --exclude='./*.tmp' \
  --exclude='./*.tsbuildinfo' \
  --exclude='./__pycache__' \
  --exclude='./agent/__pycache__' \
  --exclude='./agent/tests/__pycache__' \
  --exclude='./server/__pycache__' \
  -C "${ROOT_DIR}" \
  -czf "${OUT}" \
  .

tar -tzf "${OUT}" ./LICENSE ./docs/THIRD_PARTY_NOTICES.md >/dev/null

printf '%s\n' "${OUT}"
