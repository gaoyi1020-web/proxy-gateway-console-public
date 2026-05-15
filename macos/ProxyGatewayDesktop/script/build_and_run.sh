#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="ProxyGatewayDesktop"
DISPLAY_NAME="Proxy Gateway Desktop"
BUNDLE_ID="local.proxygateway.desktop"
SHORT_VERSION="0.2.0"
BUNDLE_VERSION="2"
MIN_SYSTEM_VERSION="13.0"
SWIFTC_TARGET="${SWIFTC_TARGET:-$(uname -m)-apple-macos${MIN_SYSTEM_VERSION}}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS_DIR="${ROOT_DIR}/Assets"
DIST_DIR="${ROOT_DIR}/dist"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
APP_CONTENTS="${APP_BUNDLE}/Contents"
APP_MACOS="${APP_CONTENTS}/MacOS"
APP_RESOURCES="${APP_CONTENTS}/Resources"
APP_BINARY="${APP_MACOS}/${APP_NAME}"
INFO_PLIST="${APP_CONTENTS}/Info.plist"
APP_ICON="${ASSETS_DIR}/AppIcon.icns"
SDK_PATH="${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk}"
DIRECT_BUILD_DIR="${ROOT_DIR}/.build/direct/debug"
USER_APPLICATIONS="${HOME}/Applications"
INSTALLED_APP="${USER_APPLICATIONS}/${DISPLAY_NAME}.app"
DESKTOP_APP="${HOME}/Desktop/${DISPLAY_NAME}.app"

pkill -x "${APP_NAME}" >/dev/null 2>&1 || true

build_with_swiftpm() {
  local build_dir
  if ! swift build --package-path "${ROOT_DIR}"; then
    return 1
  fi
  build_dir="$(swift build --package-path "${ROOT_DIR}" --show-bin-path)"
  BUILD_BINARY="${build_dir}/${APP_NAME}"
}

build_with_swiftc() {
  local sources=()
  local source
  while IFS= read -r source; do
    sources+=("${source}")
  done < <(find "${ROOT_DIR}/Sources/ProxyGatewayDesktop" -name '*.swift' | sort)

  mkdir -p "${DIRECT_BUILD_DIR}"
  swiftc \
    -sdk "${SDK_PATH}" \
    -target "${SWIFTC_TARGET}" \
    "${sources[@]}" \
    -o "${DIRECT_BUILD_DIR}/${APP_NAME}"
  BUILD_BINARY="${DIRECT_BUILD_DIR}/${APP_NAME}"
}

if ! build_with_swiftpm; then
  build_with_swiftc
fi

rm -rf "${APP_BUNDLE}"
mkdir -p "${APP_MACOS}" "${APP_RESOURCES}"
cp "${BUILD_BINARY}" "${APP_BINARY}"
chmod +x "${APP_BINARY}"
if [[ -f "${APP_ICON}" ]]; then
  cp "${APP_ICON}" "${APP_RESOURCES}/AppIcon.icns"
fi

cat >"${INFO_PLIST}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleDisplayName</key>
  <string>${DISPLAY_NAME}</string>
  <key>CFBundleName</key>
  <string>${DISPLAY_NAME}</string>
  <key>CFBundleShortVersionString</key>
  <string>${SHORT_VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${BUNDLE_VERSION}</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIconName</key>
  <string>AppIcon</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSApplicationCategoryType</key>
  <string>public.app-category.utilities</string>
  <key>LSMinimumSystemVersion</key>
  <string>${MIN_SYSTEM_VERSION}</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

open_app() {
  /usr/bin/open -n "${APP_BUNDLE}"
}

install_app() {
  mkdir -p "${USER_APPLICATIONS}"
  ditto "${APP_BUNDLE}" "${INSTALLED_APP}"
  ditto "${APP_BUNDLE}" "${DESKTOP_APP}"
  if [[ -x /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister ]]; then
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "${INSTALLED_APP}" >/dev/null 2>&1 || true
  fi
  printf 'installed: %s\n' "${INSTALLED_APP}"
  printf 'desktop: %s\n' "${DESKTOP_APP}"
}

case "${MODE}" in
  run)
    open_app
    ;;
  --install|install)
    install_app
    ;;
  --debug|debug)
    lldb -- "${APP_BINARY}"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"${APP_NAME}\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"${BUNDLE_ID}\""
    ;;
  --verify|verify)
    open_app
    sleep 2
    pgrep -x "${APP_NAME}" >/dev/null
    ;;
  *)
    echo "usage: $0 [run|--install|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
