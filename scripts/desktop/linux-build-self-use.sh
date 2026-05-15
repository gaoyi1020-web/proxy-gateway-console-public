#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${ROOT_DIR}/dist/linux-self-use"
MANIFEST="${OUT_DIR}/manifest.txt"
MODE="${1:---build}"

usage() {
  cat <<'EOF'
usage: scripts/desktop/linux-build-self-use.sh [--dry-run|--build]

Builds the Linux self-use desktop release artifact.

--dry-run  print required commands and paths without building
--build    run frontend build, sidecar build, and Tauri release build
EOF
}

if [[ "${MODE}" == "-h" || "${MODE}" == "--help" || "${MODE}" == "help" ]]; then
  usage
  exit 0
fi

if [[ "${MODE}" != "--dry-run" && "${MODE}" != "--build" ]]; then
  usage >&2
  exit 2
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "linux self-use package can only be built on Linux" >&2
  exit 2
fi

cd "${ROOT_DIR}"
TARGET_TRIPLE="$(rustc --print host-tuple 2>/dev/null || rustc -Vv | awk '/host:/ {print $2}')"
SIDECAR="${ROOT_DIR}/src-tauri/binaries/gateway-agent-${TARGET_TRIPLE}"
RELEASE_BIN="${ROOT_DIR}/src-tauri/target/release/proxy-gateway-test"
RELEASE_SIDECAR="${ROOT_DIR}/src-tauri/target/release/gateway-agent"
SIDECAR_BACKUP=""
DIST_BACKUP_DIR=""
BUILD_MODE="tauri-cli-no-bundle"

restore_source_sidecar() {
  if [[ -n "${SIDECAR_BACKUP}" && -f "${SIDECAR_BACKUP}" ]]; then
    cp -p "${SIDECAR_BACKUP}" "${SIDECAR}"
    rm -f "${SIDECAR_BACKUP}"
  fi
}

preserve_dist_artifacts() {
  DIST_BACKUP_DIR="$(mktemp -d)"
  for artifact_dir in archive self-use; do
    if [[ -e "${ROOT_DIR}/dist/${artifact_dir}" ]]; then
      mv "${ROOT_DIR}/dist/${artifact_dir}" "${DIST_BACKUP_DIR}/${artifact_dir}"
    fi
  done
}

restore_dist_artifacts() {
  if [[ -z "${DIST_BACKUP_DIR}" || ! -d "${DIST_BACKUP_DIR}" ]]; then
    return 0
  fi
  mkdir -p "${ROOT_DIR}/dist"
  for artifact_dir in archive self-use; do
    if [[ -e "${DIST_BACKUP_DIR}/${artifact_dir}" ]]; then
      rm -rf "${ROOT_DIR}/dist/${artifact_dir}"
      mv "${DIST_BACKUP_DIR}/${artifact_dir}" "${ROOT_DIR}/dist/${artifact_dir}"
    fi
  done
  rmdir "${DIST_BACKUP_DIR}" 2>/dev/null || rm -rf "${DIST_BACKUP_DIR}"
}

cleanup() {
  restore_source_sidecar
  restore_dist_artifacts
}

verify_embedded_frontend() {
  local assets=()
  local asset
  local embedded_path
  local missing=0

  while IFS= read -r -d '' asset; do
    assets+=("${asset}")
  done < <(find "${ROOT_DIR}/dist/assets" -maxdepth 1 -type f \( -name 'index-*.js' -o -name 'index-*.css' \) -print0 | sort -z)

  if [[ "${#assets[@]}" -eq 0 ]]; then
    echo "frontend dist assets are missing; refusing to package desktop release" >&2
    return 1
  fi

  for asset in "${assets[@]}"; do
    embedded_path="/assets/$(basename "${asset}")"
    if ! grep -aFq "${embedded_path}" "${RELEASE_BIN}"; then
      echo "release binary does not contain current embedded asset ${embedded_path}" >&2
      missing=1
    fi
  done

  if [[ "${missing}" -ne 0 ]]; then
    echo "refusing to package stale or dev-url desktop build" >&2
    return 1
  fi
}

run_tauri_release_build() {
  local build_log
  build_log="$(mktemp)"
  if npm run desktop:build -- --no-bundle 2>&1 | tee "${build_log}"; then
    rm -f "${build_log}"
    return 0
  fi

  if grep -Eq 'OS file watch limit reached|failed to watch' "${build_log}"; then
    echo "Tauri CLI watcher limit reached before a valid no-bundle release binary was produced" >&2
    if [[ -x "${RELEASE_BIN}" ]] && verify_embedded_frontend; then
      echo "Reusing existing embedded release binary after watcher-limit failure" >&2
      BUILD_MODE="existing-embedded-after-watch-limit"
      rm -f "${build_log}"
      return 0
    fi
  fi
  rm -f "${build_log}"
  return 1
}

if [[ "${MODE}" == "--dry-run" ]]; then
  cat <<EOF
root: ${ROOT_DIR}
target: ${TARGET_TRIPLE}
sidecar: ${SIDECAR}
release-binary: ${RELEASE_BIN}
release-sidecar: ${RELEASE_SIDECAR}
out-dir: ${OUT_DIR}
commands:
  npm run build
  scripts/desktop/build-agent-sidecar.sh --apply
  npm run desktop:build -- --no-bundle
  verify embedded frontend assets in release binary
  sha256sum release artifacts > ${MANIFEST}
EOF
  exit 0
fi

trap cleanup EXIT
preserve_dist_artifacts
npm run build
if [[ -f "${SIDECAR}" ]]; then
  SIDECAR_BACKUP="$(mktemp)"
  cp -p "${SIDECAR}" "${SIDECAR_BACKUP}"
fi
scripts/desktop/build-agent-sidecar.sh --apply
run_tauri_release_build
mkdir -p "$(dirname "${RELEASE_SIDECAR}")"
install -m 0755 "${SIDECAR}" "${RELEASE_SIDECAR}"

if [[ ! -x "${RELEASE_SIDECAR}" ]]; then
  echo "missing release sidecar: ${RELEASE_SIDECAR}" >&2
  exit 1
fi

if [[ ! -x "${RELEASE_BIN}" ]]; then
  echo "missing release binary: ${RELEASE_BIN}" >&2
  exit 1
fi

verify_embedded_frontend

mkdir -p "${OUT_DIR}"
{
  printf 'generatedAt=%s\n' "$(date -Is)"
  printf 'root=%s\n' "${ROOT_DIR}"
  printf 'target=%s\n' "${TARGET_TRIPLE}"
  printf 'buildMode=%s\n' "${BUILD_MODE}"
  printf 'releaseBinary=%s\n' "${RELEASE_BIN}"
  printf 'releaseSidecar=%s\n' "${RELEASE_SIDECAR}"
  printf 'license=%s\n' "${ROOT_DIR}/LICENSE"
  printf 'thirdPartyNotices=%s\n' "${ROOT_DIR}/docs/THIRD_PARTY_NOTICES.md"
  sha256sum "${RELEASE_BIN}" "${RELEASE_SIDECAR}"
  sha256sum "${ROOT_DIR}/LICENSE" "${ROOT_DIR}/docs/THIRD_PARTY_NOTICES.md"
} >"${MANIFEST}"

printf 'Linux self-use desktop build complete: %s\n' "${MANIFEST}"
