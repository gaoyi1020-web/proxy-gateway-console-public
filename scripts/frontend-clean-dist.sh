#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"

if [[ ! -d "${DIST_DIR}" ]]; then
  exit 0
fi

find "${DIST_DIR}" -mindepth 1 -maxdepth 1 \
  ! -name archive \
  ! -name self-use \
  ! -name linux-self-use \
  -exec rm -rf {} +
