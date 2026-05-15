#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

fail() {
  printf 'public core check failed: %s\n' "$*" >&2
  exit 1
}

cd "${ROOT_DIR}"

[[ -d .git ]] || fail "must run inside the repository checkout"
[[ -z "$(git ls-files -u)" ]] || fail "unmerged paths are present"

required_files=(
  README.md
  FEATURES.md
  SECURITY.md
  LICENSE
  package.json
  docs/ACTIONS_BUDGET.md
  docs/OPEN_SOURCE_BOUNDARY.md
  docs/THIRD_PARTY_NOTICES.md
)

for file in "${required_files[@]}"; do
  git ls-files --error-unmatch "${file}" >/dev/null 2>&1 || fail "required public file is not tracked: ${file}"
done

blocked_path_pattern='(^dist/|^src-tauri/binaries/|^docs/(verification|superpowers|cgc|phone-compat|private)/|^docs/(ARCHIVE_|PROJECT_DOSSIER[.]md|PROJECT_INDEX[.]md|PROJECT_STRUCTURE_FLOW[.]md|V2_)|(^|/)(privatekey|publickey|profile[.]json[.]enc|upstream[.]json|sing-box[.]json)$|[.](tar[.]gz|zip|log|tmp|pem|key)$)'
blocked_paths="$(git ls-files | grep -En "${blocked_path_pattern}" || true)"

if [[ -n "${blocked_paths}" ]]; then
  printf '%s\n' "${blocked_paths}" >&2
  fail "blocked private or generated paths are tracked"
fi

private_trace_pattern='(/[h]ome/g|/[U]sers/g|192[.]168[.]10[.]|[Aa]liyun|n[1]n|BEGIN (OPENSSH|RSA|DSA|EC)[[:space:]]+PRIVATE[[:space:]]+KEY|PRIVATE[[:space:]]+KEY|OPENAI_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY|MINIMAX_API_KEY)'
matches="$(git ls-files -z \
  | xargs -0 grep -InE "${private_trace_pattern}" 2>/dev/null \
  | grep -Ev '(^scripts/open-source/check-public-core[.]sh:|^scripts/open-source/export-public-snapshot[.]sh:|^server/open-source-export[.]test[.]mjs:)' \
  || true)"

if [[ -n "${matches}" ]]; then
  printf '%s\n' "${matches}" >&2
  fail "private trace scan found blocked patterns"
fi

printf 'public core check passed\n'
