#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${PROXY_GATEWAY_DESKTOP_INSTALL_ROOT:-${HOME}/.local/share/proxy-gateway-desktop/self-use}"
AGENT="${INSTALL_ROOT}/bin/gateway-agent"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "linux self-use smoke test can only run on Linux" >&2
  exit 2
fi

if [[ ! -x "${AGENT}" ]]; then
  echo "missing installed sidecar: ${AGENT}" >&2
  exit 1
fi

export GATEWAY_AGENT_V2=1
export XDG_CONFIG_HOME="${TMP_DIR}/config"
export GATEWAY_AGENT_RUNTIME_DIR="${TMP_DIR}/runtime"

mkdir -p "${TMP_DIR}/profile"

"${AGENT}" profile-template >"${TMP_DIR}/profile/profile.template.json"
"${AGENT}" profile-encrypt \
  --profile-input "${TMP_DIR}/profile/profile.template.json" \
  --profile-output "${TMP_DIR}/profile/profile.json.enc" \
  --passphrase passphrase \
  >"${TMP_DIR}/encrypt.json"
"${AGENT}" profile-import --from "${TMP_DIR}/profile/profile.json.enc" >"${TMP_DIR}/import.json"
"${AGENT}" start --lan-host 127.0.0.1 >"${TMP_DIR}/start.json"
"${AGENT}" status >"${TMP_DIR}/status.json"
"${AGENT}" self-check >"${TMP_DIR}/self-check.json"
"${AGENT}" uninstall --dry-run >"${TMP_DIR}/uninstall-plan.json"
"${AGENT}" stop >"${TMP_DIR}/stop.json"

node - <<'NODE' "${TMP_DIR}"
const fs = require("fs");
const dir = process.argv[2];

function read(name) {
  return JSON.parse(fs.readFileSync(`${dir}/${name}.json`, "utf8"));
}

const checks = [
  ["encrypt", read("encrypt").ok === true],
  ["import", read("import").ok === true && read("import").state === "imported"],
  ["start", read("start").ok === true && read("start").state === "manifest_ready"],
  ["status", read("status").ok === true && read("status").profileSource?.present === true],
  ["self-check", read("self-check").ok === true],
  ["uninstall-plan", read("uninstall-plan").ok === true && read("uninstall-plan").state === "dry_run"],
  ["stop", read("stop").ok === true],
];

const failed = checks.filter(([, ok]) => !ok).map(([name]) => name);
const summary = Object.fromEntries(checks.map(([name, ok]) => [name, ok ? "pass" : "fail"]));
console.log(JSON.stringify({ ok: failed.length === 0, summary }, null, 2));
if (failed.length) {
  process.exit(1);
}
NODE

echo "Linux self-use desktop smoke: pass"
