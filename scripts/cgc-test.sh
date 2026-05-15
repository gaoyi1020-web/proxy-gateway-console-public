#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CGC="${ROOT_DIR}/scripts/cgc"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

contains() {
  local haystack="$1"
  local needle="$2"
  grep -Fq -- "${needle}" <<<"${haystack}" || fail "expected output to contain: ${needle}"
}

[[ -x "${CGC}" ]] || fail "scripts/cgc is missing or not executable"
cgc_source="$(cat "${CGC}")"
contains "${cgc_source}" "gatewayProfileSource"
contains "${cgc_source}" "optimizationPhase"
contains "${cgc_source}" "optimizationBlockers"

help_output="$("${CGC}" --help)"
contains "${help_output}" "Proxy Gateway CGC"
contains "${help_output}" "closeout"
contains "${help_output}" "evidence-pack"
contains "${help_output}" "claude-brief"
contains "${help_output}" "Gemini findings require Codex path:line verification before action"

status_output="$("${CGC}" status --local-only)"
contains "${status_output}" "macvpn kit verification: pass"
contains "${status_output}" "Mac desktop state: skipped (--local-only)"

linux_status_dry_run="$("${CGC}" status --lane linux-workbench --require-app-running --dry-run)"
contains "${linux_status_dry_run}" "CGC Linux workbench status dry run"
contains "${linux_status_dry_run}" "would run: scripts/cgc-test.sh"
contains "${linux_status_dry_run}" "local HTTP endpoint probe"

closeout_dry_run="$("${CGC}" closeout --task "Mac project closeout" --local-only --dry-run)"
contains "${closeout_dry_run}" "CGC closeout dry run"
contains "${closeout_dry_run}" "service changes: disallowed"
contains "${closeout_dry_run}" "scripts/macvpn/verify-macvpn-kit.sh"

linux_closeout_dry_run="$("${CGC}" closeout --lane linux-workbench --task "Linux workbench closeout" --require-app-running --dry-run)"
contains "${linux_closeout_dry_run}" "CGC Linux workbench closeout dry run"
contains "${linux_closeout_dry_run}" "would run: npm test"
contains "${linux_closeout_dry_run}" "would run: npm run desktop:smoke:self-use"
contains "${linux_closeout_dry_run}" "local HTTP endpoint probe"

network_scan_dry_run="$("${CGC}" network-scan --dry-run)"
contains "${network_scan_dry_run}" "CGC network scan dry run"
contains "${network_scan_dry_run}" "would run: scripts/network/network-smoke.sh"
contains "${network_scan_dry_run}" 'would run: ${HOME}/.local/bin/proxy-stack self-check --deep'

gemini_dry_run="$("${CGC}" gemini --task "Review Mac closeout evidence" --dry-run)"
contains "${gemini_dry_run}" "Gemini read-only review prompt"
contains "${gemini_dry_run}" "Requested Gemini model: gemini-cli-default"
contains "${gemini_dry_run}" "Do not modify files"
contains "${gemini_dry_run}" "Review Mac closeout evidence"

linux_gemini_dry_run="$(CGC_GEMINI_MODEL=local-pro-review "${CGC}" gemini --lane linux-workbench --task "Review Linux status workbench UI" --dry-run)"
contains "${linux_gemini_dry_run}" "Linux status workbench lane"
contains "${linux_gemini_dry_run}" "Requested Gemini model: local-pro-review"
contains "${linux_gemini_dry_run}" "docs/verification/LINUX_STATUS_WORKBENCH_UI_2026-05-08.md"
contains "${linux_gemini_dry_run}" "server/workbench-styles.test.mjs"
contains "${linux_gemini_dry_run}" "Do not report P0/P1/P2 labels for confirmations"
contains "${linux_gemini_dry_run}" "Codex verification checklist"
contains "${linux_gemini_dry_run}" "Review Linux status workbench UI"

evidence_pack_dry_run="$("${CGC}" evidence-pack --lane project --task "Project closeout review" --dry-run)"
contains "${evidence_pack_dry_run}" "CGC Evidence Pack"
contains "${evidence_pack_dry_run}" "Gemini is a rough scanner and candidate reviewer only"
contains "${evidence_pack_dry_run}" "Codex Secondary Processing Table"
contains "${evidence_pack_dry_run}" "accepted / rejected / needs-command / manual-gate"
contains "${evidence_pack_dry_run}" "Project-wide evidence must be split by area"

if "${CGC}" gemini --lane unknown --task "Bad lane" --dry-run >/tmp/cgc-bad-lane.out 2>&1; then
  fail "expected unknown Gemini lane to fail"
fi
contains "$(cat /tmp/cgc-bad-lane.out)" "unknown gemini lane: unknown"

if "${CGC}" evidence-pack --lane unknown --task "Bad lane" --dry-run >/tmp/cgc-bad-evidence-lane.out 2>&1; then
  fail "expected unknown evidence-pack lane to fail"
fi
contains "$(cat /tmp/cgc-bad-evidence-lane.out)" "unknown evidence-pack lane: unknown"

brief_dry_run="$("${CGC}" claude-brief --task "Plan Sparkle updater" --scope "Mac updater" --files "macos/ProxyGatewayDesktop" --tests "bash -n scripts/cgc" --dry-run)"
contains "${brief_dry_run}" "Claude execution brief"
contains "${brief_dry_run}" "Codex verification is required"
contains "${brief_dry_run}" "Plan Sparkle updater"
contains "${brief_dry_run}" "bash -n scripts/cgc"

plan_dry_run="$("${CGC}" claude-plan --task "Plan signing" --scope "Mac packaging" --files "read-only" --tests "propose commands only" --dry-run)"
contains "${plan_dry_run}" "Claude planning brief"
contains "${plan_dry_run}" "read-only"
contains "${plan_dry_run}" "propose commands only"

[[ -f "${ROOT_DIR}/runtime/proxy-stack/proxy_stack.py" ]] || fail "runtime proxy-stack source is missing"
[[ -f "${ROOT_DIR}/runtime/proxy-stack/tests/test_proxy_stack.py" ]] || fail "runtime proxy-stack tests are missing"
python3 -m py_compile "${ROOT_DIR}/runtime/proxy-stack/proxy_stack.py"
(cd "${ROOT_DIR}/runtime/proxy-stack" && python3 -m unittest discover -s tests)

printf 'cgc tests: pass\n'
