#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  printf 'local ci failed: %s\n' "$*" >&2
  exit 1
}

run() {
  printf '\n==> %s\n' "$*"
  "$@"
}

run_shell_syntax_check() {
  local scripts=()

  shopt -s nullglob
  scripts+=(
    scripts/cgc
    scripts/*.sh
    scripts/cloud/*.sh
    scripts/desktop/*.sh
    scripts/macvpn/*.sh
    scripts/network/*.sh
    scripts/open-source/*.sh
    scripts/phone-compat/*.sh
    scripts/profile/*.sh
  )
  shopt -u nullglob

  ((${#scripts[@]} > 0)) || fail "no shell scripts found"
  run bash -n "${scripts[@]}"
}

check_package_boundary() {
  local archives=()

  shopt -s nullglob
  archives=(dist/self-use/ProxyGateway-Mac-SelfUse-*.zip)
  shopt -u nullglob

  if ((${#archives[@]} == 0)); then
    printf '\n==> package boundary\n'
    printf 'no Mac self-use archives found; package boundary archive scan skipped\n'
    return
  fi

  for archive in "${archives[@]}"; do
    printf '\n==> package boundary: %s\n' "${archive}"
    if unzip -l "${archive}" | grep -E 'upstream[.]json|sing-box[.]json|profile[.]json[.]enc|[.]log|verify-mac-desktop-state[.]sh|verify-mac-ui-closeout[.]sh|package-self-use-installer[.]sh'; then
      fail "blocked private or developer-only file found in ${archive}"
    fi
  done
}

run_desktop_check() {
  local mode="${CI_LOCAL_DESKTOP_CHECK:-auto}"
  local sidecars=()

  shopt -s nullglob
  sidecars=(src-tauri/binaries/gateway-agent-*)
  shopt -u nullglob

  case "${mode}" in
    0|false|skip)
      printf '\n==> desktop check skipped by CI_LOCAL_DESKTOP_CHECK=%s\n' "${mode}"
      return
      ;;
    1|true|require)
      ((${#sidecars[@]} > 0)) || fail "desktop sidecar binary is missing; run scripts/desktop/build-agent-sidecar.sh or set CI_LOCAL_DESKTOP_CHECK=auto"
      ;;
    auto)
      if ((${#sidecars[@]} == 0)); then
        printf '\n==> desktop check\n'
        printf 'desktop sidecar binary missing; npm run desktop:check skipped in auto mode\n'
        return
      fi
      ;;
    *)
      fail "unknown CI_LOCAL_DESKTOP_CHECK mode: ${mode}"
      ;;
  esac

  command -v cargo >/dev/null 2>&1 || fail "cargo not found; set CI_LOCAL_DESKTOP_CHECK=0 to skip desktop check"
  run npm run desktop:check
}

cd "${ROOT_DIR}"

[[ -f package.json ]] || fail "package.json not found"
[[ -f .github/workflows/ci.yml ]] || fail ".github/workflows/ci.yml not found"

if [[ "${CI_LOCAL_INSTALL:-0}" == "1" ]]; then
  run npm ci
  if [[ -s requirements.txt ]]; then
    run python3 -m pip install -r requirements.txt
  fi
else
  printf '==> dependency install skipped; set CI_LOCAL_INSTALL=1 to run npm ci and pip install\n'
fi

run npm run open-source:check
run npm run license:audit
run npm run build
run npm test
run_shell_syntax_check
run scripts/macvpn/verify-macvpn-kit.sh
check_package_boundary
run_desktop_check

printf '\nlocal ci passed\n'
