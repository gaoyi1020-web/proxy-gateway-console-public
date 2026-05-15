#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_OUT="${ROOT_DIR}/dist/open-source/proxy-gateway-console-public-${STAMP}"
OUT_DIR="${1:-${DEFAULT_OUT}}"

usage() {
  printf 'Usage: %s [output-dir]\n' "$0"
  printf 'Creates a no-history public source snapshot from the current Git index.\n'
}

fail() {
  printf 'public export failed: %s\n' "$*" >&2
  exit 1
}

should_exclude() {
  case "$1" in
    dist/*) return 0 ;;
    src-tauri/target/*) return 0 ;;
    src-tauri/binaries/*) return 0 ;;
    docs/verification/*) return 0 ;;
    docs/superpowers/*) return 0 ;;
    docs/cgc/*) return 0 ;;
    docs/phone-compat/*) return 0 ;;
    docs/private/*) return 0 ;;
    docs/ARCHIVE_*.md) return 0 ;;
    docs/PROJECT_DOSSIER.md) return 0 ;;
    docs/PROJECT_INDEX.md) return 0 ;;
    docs/PROJECT_STRUCTURE_FLOW.md) return 0 ;;
    docs/V2_*.md) return 0 ;;
    *.tar.gz) return 0 ;;
    *.tar.gz.sha256) return 0 ;;
    *.zip) return 0 ;;
    *.log) return 0 ;;
    *.tmp) return 0 ;;
    .env) return 0 ;;
    *.pem) return 0 ;;
    *.key) return 0 ;;
    profile.json.enc) return 0 ;;
    upstream.json) return 0 ;;
    sing-box.json) return 0 ;;
    publickey) return 0 ;;
    privatekey) return 0 ;;
  esac

  return 1
}

scan_private_traces() {
  local path="$1"
  local pattern='(/[h]ome/g|/[U]sers/g|192[.]168[.]10[.]|[Aa]liyun|n[1]n|BEGIN (OPENSSH|RSA|DSA|EC)[[:space:]]+PRIVATE[[:space:]]+KEY|PRIVATE[[:space:]]+KEY)'
  local matches

  if command -v rg >/dev/null 2>&1; then
    matches="$(rg -n --hidden -e "${pattern}" "${path}" || true)"
  else
    matches="$(grep -RInE "${pattern}" "${path}" || true)"
  fi

  if [[ -n "${matches}" ]]; then
    printf '%s\n' "${matches}" >&2
    fail "private trace scan found blocked patterns"
  fi
}

if [[ "${OUT_DIR}" == "--help" || "${OUT_DIR}" == "-h" ]]; then
  usage
  exit 0
fi

case "${OUT_DIR}" in
  /*) ;;
  *) OUT_DIR="${ROOT_DIR}/${OUT_DIR}" ;;
esac

cd "${ROOT_DIR}"

[[ -d .git ]] || fail "must run inside the repository checkout"
[[ -z "$(git ls-files -u)" ]] || fail "unmerged paths are present"
git diff --quiet || fail "unstaged changes are present; stage or discard them before exporting"

required_files=(
  README.md
  FEATURES.md
  SECURITY.md
  LICENSE
  package.json
  docs/THIRD_PARTY_NOTICES.md
)

for file in "${required_files[@]}"; do
  git ls-files --error-unmatch "${file}" >/dev/null 2>&1 || fail "required public file is not tracked: ${file}"
done

[[ ! -e "${OUT_DIR}" ]] || fail "output path already exists: ${OUT_DIR}"
mkdir -p "$(dirname "${OUT_DIR}")"

TMP_DIR="${OUT_DIR}.tmp"
rm -rf "${TMP_DIR}"
mkdir -p "${TMP_DIR}"
trap 'rm -rf "${TMP_DIR}"' EXIT

while IFS= read -r -d '' file; do
  if should_exclude "${file}"; then
    continue
  fi

  mkdir -p "${TMP_DIR}/$(dirname "${file}")"
  cp -Pp "${file}" "${TMP_DIR}/${file}"
done < <(git ls-files -z --cached)

for file in "${required_files[@]}"; do
  [[ -f "${TMP_DIR}/${file}" ]] || fail "required public file missing from export: ${file}"
done

{
  printf 'project=proxy-gateway-console\n'
  printf 'generatedAt=%s\n' "${STAMP}"
  printf 'sourceHead=%s\n' "$(git rev-parse --short HEAD)"
  printf 'sourceBranch=%s\n' "$(git branch --show-current)"
  printf 'stagedChanges=%s\n' "$(git diff --cached --name-only | wc -l | tr -d ' ')"
  printf 'history=included=false\n'
  printf 'license=MIT\n'
  printf 'thirdPartyNotices=docs/THIRD_PARTY_NOTICES.md\n'
} > "${TMP_DIR}/SOURCE_MANIFEST.txt"

scan_private_traces "${TMP_DIR}"

mv "${TMP_DIR}" "${OUT_DIR}"
trap - EXIT
printf 'public export created: %s\n' "${OUT_DIR}"
