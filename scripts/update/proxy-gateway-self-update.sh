#!/usr/bin/env bash
set -euo pipefail

MODE="--check"
ASSUME_YES=0
KEEP_WORK_DIR=0
REPO="${PROXY_GATEWAY_UPDATE_REPO:-gaoyi1020-web/proxy-gateway-console-public}"
API_URL="${PROXY_GATEWAY_UPDATE_API_URL:-https://api.github.com/repos/${REPO}/releases/latest}"
WORK_DIR="${PROXY_GATEWAY_UPDATE_WORK_DIR:-}"
MANIFEST_NAME="proxy-gateway-update-manifest.json"

usage() {
  cat <<'EOF'
usage: scripts/update/proxy-gateway-self-update.sh [--check|--download|--install] [--yes] [--keep]

Checks the public GitHub Release update manifest, downloads the matching
platform package, verifies SHA256, and optionally runs the installer.

Environment:
  PROXY_GATEWAY_UPDATE_REPO       GitHub repo, default gaoyi1020-web/proxy-gateway-console-public
  PROXY_GATEWAY_UPDATE_API_URL    Override latest-release API URL for tests
  PROXY_GATEWAY_UPDATE_WORK_DIR   Directory for downloaded files
  PROXY_GATEWAY_CURRENT_VERSION   Override detected local version
EOF
}

fail() {
  printf 'self-update failed: %s\n' "$*" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check|--download|--install)
      MODE="$1"
      shift
      ;;
    --yes|-y)
      ASSUME_YES=1
      shift
      ;;
    --keep)
      KEEP_WORK_DIR=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

need_command curl
need_command python3

if [[ -z "${WORK_DIR}" ]]; then
  WORK_DIR="$(mktemp -d)"
  if [[ "${KEEP_WORK_DIR}" != "1" ]]; then
    trap 'rm -rf "${WORK_DIR}"' EXIT
  fi
else
  mkdir -p "${WORK_DIR}"
fi

download() {
  local url="$1"
  local out="$2"
  curl -fsSL --retry 2 --connect-timeout 12 --max-time 120 "${url}" -o "${out}"
}

host_platform() {
  case "$(uname -s)" in
    Darwin) printf 'darwin\n' ;;
    Linux) printf 'linux\n' ;;
    *) fail "unsupported platform: $(uname -s)" ;;
  esac
}

host_arch() {
  case "$(uname -m)" in
    x86_64|amd64) printf 'x86_64\n' ;;
    arm64|aarch64) printf 'arm64\n' ;;
    *) uname -m ;;
  esac
}

current_version() {
  if [[ -n "${PROXY_GATEWAY_CURRENT_VERSION:-}" ]]; then
    printf '%s\n' "${PROXY_GATEWAY_CURRENT_VERSION}"
    return
  fi

  if [[ -f "${HOME}/ProxyGatewayMacVPN/VERSION" ]]; then
    sed -n '1p' "${HOME}/ProxyGatewayMacVPN/VERSION"
    return
  fi

  if [[ -f "${HOME}/Applications/Proxy Gateway Desktop.app/Contents/Info.plist" ]] && command -v plutil >/dev/null 2>&1; then
    plutil -extract CFBundleShortVersionString raw "${HOME}/Applications/Proxy Gateway Desktop.app/Contents/Info.plist" 2>/dev/null && return
  fi

  if [[ -f "${HOME}/.local/share/proxy-gateway-desktop/self-use/VERSION" ]]; then
    sed -n '1p' "${HOME}/.local/share/proxy-gateway-desktop/self-use/VERSION"
    return
  fi

  printf 'unknown\n'
}

json_field() {
  local json_path="$1"
  local expr="$2"
  python3 - "$json_path" "$expr" <<'PY'
import json
import sys

path, expr = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    data = json.load(fh)

value = data
for part in expr.split("."):
    value = value[part]
print(value)
PY
}

release_manifest_url() {
  local release_json="$1"
  python3 - "$release_json" "${MANIFEST_NAME}" <<'PY'
import json
import sys

path, manifest_name = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    release = json.load(fh)

for asset in release.get("assets", []):
    if asset.get("name") == manifest_name:
        print(asset.get("browser_download_url") or asset.get("url"))
        raise SystemExit(0)

raise SystemExit(f"missing {manifest_name} asset in latest release")
PY
}

selected_asset_json() {
  local manifest="$1"
  local platform="$2"
  local arch="$3"
  python3 - "$manifest" "$platform" "$arch" <<'PY'
import json
import sys

path, platform, arch = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, encoding="utf-8") as fh:
    manifest = json.load(fh)

if manifest.get("schemaVersion") != 1:
    raise SystemExit("unsupported update manifest schema")

for asset in manifest.get("assets", []):
    if not asset.get("installable"):
        continue
    if asset.get("platform") != platform:
        continue
    asset_arch = asset.get("arch")
    if asset_arch not in (arch, "universal", "any"):
        continue
    print(json.dumps(asset, separators=(",", ":")))
    raise SystemExit(0)

raise SystemExit(f"no compatible installable update asset for {platform}/{arch}")
PY
}

asset_field() {
  local asset_json="$1"
  local field="$2"
  python3 - "$asset_json" "$field" <<'PY'
import json
import sys

asset = json.loads(sys.argv[1])
print(asset[sys.argv[2]])
PY
}

verify_asset_checksum() {
  local file="$1"
  local expected="$2"
  local actual

  if command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "${file}" | awk '{print $1}')"
  elif command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "${file}" | awk '{print $1}')"
  else
    fail "missing required command: shasum or sha256sum"
  fi

  if [[ "${actual}" != "${expected}" ]]; then
    fail "expected checksum ${expected}, got ${actual}"
  fi
}

install_asset() {
  local file="$1"
  local kind="$2"
  local extract_dir

  [[ "${ASSUME_YES}" == "1" ]] || fail "--install requires --yes so updates are explicit"

  extract_dir="${WORK_DIR}/extract"
  rm -rf "${extract_dir}"
  mkdir -p "${extract_dir}"

  case "${kind}" in
    self-use-zip)
      need_command unzip
      unzip -q "${file}" -d "${extract_dir}"
      installer="$(find "${extract_dir}" -maxdepth 3 -type f -name 'Install Proxy Gateway.command' -print -quit)"
      [[ -n "${installer}" ]] || fail "Install Proxy Gateway.command not found in update package"
      bash "${installer}"
      ;;
    self-use-tar)
      tar -xzf "${file}" -C "${extract_dir}"
      installer="$(find "${extract_dir}" -maxdepth 3 -type f -name 'Install Proxy Gateway.sh' -print -quit)"
      [[ -n "${installer}" ]] || fail "Install Proxy Gateway.sh not found in update package"
      bash "${installer}"
      ;;
    *)
      fail "asset kind is not installable by this updater: ${kind}"
      ;;
  esac
}

release_json="${WORK_DIR}/latest-release.json"
manifest_json="${WORK_DIR}/${MANIFEST_NAME}"
download "${API_URL}" "${release_json}"
download "$(release_manifest_url "${release_json}")" "${manifest_json}"

platform="$(host_platform)"
arch="$(host_arch)"
asset_json="$(selected_asset_json "${manifest_json}" "${platform}" "${arch}")"

latest_version="$(json_field "${manifest_json}" version)"
local_version="$(current_version)"
asset_name="$(asset_field "${asset_json}" name)"
asset_url="$(asset_field "${asset_json}" url)"
asset_sha256="$(asset_field "${asset_json}" sha256)"
asset_kind="$(asset_field "${asset_json}" kind)"
asset_path="${WORK_DIR}/${asset_name}"

printf 'current-version: %s\n' "${local_version}"
printf 'latest-version: %s\n' "${latest_version}"
printf 'asset: %s\n' "${asset_name}"

if [[ "${local_version}" == "${latest_version}" ]]; then
  printf 'update: not needed\n'
  exit 0
fi

printf 'update: available\n'

if [[ "${MODE}" == "--check" ]]; then
  exit 0
fi

download "${asset_url}" "${asset_path}"
verify_asset_checksum "${asset_path}" "${asset_sha256}"
printf 'downloaded: %s\n' "${asset_path}"
printf 'verified-sha256: %s\n' "${asset_sha256}"

if [[ "${MODE}" == "--install" ]]; then
  install_asset "${asset_path}" "${asset_kind}"
fi
