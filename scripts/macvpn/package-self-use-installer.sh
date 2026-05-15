#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/dist/self-use}"
VERSION="${VERSION:-0.2.0}"
APP_BUNDLE="${APP_BUNDLE:-}"
SING_BOX="${SING_BOX:-}"
PACKAGE_DIR="${OUT_DIR}/ProxyGateway-Mac-SelfUse-${VERSION}"
ZIP_PATH="${OUT_DIR}/ProxyGateway-Mac-SelfUse-${VERSION}.zip"
APP_NAME="Proxy Gateway Desktop.app"

usage() {
  cat <<EOF
usage: $0 [--app <path-to-app>] [--sing-box <path>] [--out-dir <dir>] [--version <version>]

Builds an unsigned self-use Mac installer package. The package contains code,
templates, and optional app bundle only; it refuses private runtime configs.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app)
      [[ $# -ge 2 && -n "${2:-}" ]] || { echo "--app requires a path" >&2; exit 2; }
      APP_BUNDLE="$2"
      shift 2
      ;;
    --out-dir)
      [[ $# -ge 2 && -n "${2:-}" ]] || { echo "--out-dir requires a path" >&2; exit 2; }
      OUT_DIR="$2"
      PACKAGE_DIR="${OUT_DIR}/ProxyGateway-Mac-SelfUse-${VERSION}"
      ZIP_PATH="${OUT_DIR}/ProxyGateway-Mac-SelfUse-${VERSION}.zip"
      shift 2
      ;;
    --sing-box)
      [[ $# -ge 2 && -n "${2:-}" ]] || { echo "--sing-box requires a path" >&2; exit 2; }
      SING_BOX="$2"
      shift 2
      ;;
    --version)
      [[ $# -ge 2 && -n "${2:-}" ]] || { echo "--version requires a value" >&2; exit 2; }
      VERSION="$2"
      PACKAGE_DIR="${OUT_DIR}/ProxyGateway-Mac-SelfUse-${VERSION}"
      ZIP_PATH="${OUT_DIR}/ProxyGateway-Mac-SelfUse-${VERSION}.zip"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "${OUT_DIR}" in
  /*) ;;
  *) OUT_DIR="${ROOT_DIR}/${OUT_DIR}" ;;
esac
PACKAGE_DIR="${OUT_DIR}/ProxyGateway-Mac-SelfUse-${VERSION}"
ZIP_PATH="${OUT_DIR}/ProxyGateway-Mac-SelfUse-${VERSION}.zip"

rm -rf "${PACKAGE_DIR}"
rm -f "${ZIP_PATH}"
mkdir -p "${PACKAGE_DIR}/payload/macvpn" "${PACKAGE_DIR}/payload/profile" "${PACKAGE_DIR}/payload/app" "${PACKAGE_DIR}/notices"

install -m 0755 "${ROOT_DIR}/scripts/macvpn/install-macvpn-kit.sh" "${PACKAGE_DIR}/payload/macvpn/install-macvpn-kit.sh"
install -m 0755 "${ROOT_DIR}/scripts/macvpn/install-macvpn-rootctl.sh" "${PACKAGE_DIR}/payload/macvpn/install-macvpn-rootctl.sh"
install -m 0755 "${ROOT_DIR}/scripts/macvpn/macvpnctl.sh" "${PACKAGE_DIR}/payload/macvpn/macvpnctl.sh"
install -m 0644 "${ROOT_DIR}/scripts/macvpn/sing-box.tun.template.json" "${PACKAGE_DIR}/payload/macvpn/sing-box.tun.template.json"
printf '%s\n' "${VERSION}" > "${PACKAGE_DIR}/payload/VERSION"
cp "${ROOT_DIR}/config/profile.template.json" "${PACKAGE_DIR}/payload/profile/profile.template.json"
install -m 0644 "${ROOT_DIR}/LICENSE" "${PACKAGE_DIR}/notices/LICENSE"
install -m 0644 "${ROOT_DIR}/docs/THIRD_PARTY_NOTICES.md" "${PACKAGE_DIR}/notices/THIRD_PARTY_NOTICES.md"

if [[ -n "${SING_BOX}" ]]; then
  [[ -x "${SING_BOX}" ]] || { echo "sing-box binary missing or not executable: ${SING_BOX}" >&2; exit 2; }
  mkdir -p "${PACKAGE_DIR}/payload/macvpn/bin"
  install -m 0755 "${SING_BOX}" "${PACKAGE_DIR}/payload/macvpn/bin/sing-box"
fi

if [[ -n "${APP_BUNDLE}" ]]; then
  [[ -d "${APP_BUNDLE}" ]] || { echo "app bundle missing: ${APP_BUNDLE}" >&2; exit 2; }
  cp -R "${APP_BUNDLE}" "${PACKAGE_DIR}/payload/app/${APP_NAME}"
fi

cat >"${PACKAGE_DIR}/Install Proxy Gateway.command" <<'INSTALL'
#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/ProxyGatewayMacVPN"
APP_SOURCE="${BASE_DIR}/payload/app/Proxy Gateway Desktop.app"
APP_TARGET="${HOME}/Applications/Proxy Gateway Desktop.app"
DESKTOP_APP_TARGET="${HOME}/Desktop/Proxy Gateway Desktop.app"
LOGIN_AGENT="${HOME}/Library/LaunchAgents/local.proxygateway.desktop.login.plist"

mkdir -p "${HOME}/Applications" "${HOME}/Desktop" "${HOME}/Library/LaunchAgents"
if [[ -d "${APP_SOURCE}" ]]; then
  rm -rf "${APP_TARGET}"
  if command -v ditto >/dev/null 2>&1; then
    ditto "${APP_SOURCE}" "${APP_TARGET}"
  else
    cp -R "${APP_SOURCE}" "${APP_TARGET}"
  fi
  echo "installed app: ${APP_TARGET}"
  rm -rf "${DESKTOP_APP_TARGET}"
  if command -v ditto >/dev/null 2>&1; then
    ditto "${APP_TARGET}" "${DESKTOP_APP_TARGET}"
  else
    cp -R "${APP_TARGET}" "${DESKTOP_APP_TARGET}"
  fi
  echo "installed desktop app copy: ${DESKTOP_APP_TARGET}"
  defaults write local.proxygateway.desktop runInBackground -bool true
  cat >"${LOGIN_AGENT}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>local.proxygateway.desktop.login</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>${APP_TARGET}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>LimitLoadToSessionType</key>
  <string>Aqua</string>
</dict>
</plist>
PLIST
  echo "installed login launch agent: ${LOGIN_AGENT}"
else
  echo "app bundle not included; installing VPN kit only"
fi

"${BASE_DIR}/payload/macvpn/install-macvpn-kit.sh" --target "${TARGET}"
install -m 0644 "${BASE_DIR}/payload/VERSION" "${TARGET}/VERSION"

if [[ "$(uname -s)" == "Darwin" ]]; then
  if [[ -n "${PROXY_GATEWAY_SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "${PROXY_GATEWAY_SUDO_PASSWORD}" \
      | sudo -S -p '' "${BASE_DIR}/payload/macvpn/install-macvpn-rootctl.sh" --user "$(id -un)"
  else
    sudo "${BASE_DIR}/payload/macvpn/install-macvpn-rootctl.sh" --user "$(id -un)"
  fi
fi

cat <<EOF
Proxy Gateway installed.

Next:
  1. Import your private profile into:
     ${TARGET}/config/
  2. Run:
     ${TARGET}/macvpnctl.sh profile-status
     ${TARGET}/macvpnctl.sh render-config
     ${TARGET}/macvpnctl.sh validate
EOF
INSTALL

cat >"${PACKAGE_DIR}/Uninstall Proxy Gateway.command" <<'UNINSTALL'
#!/usr/bin/env bash
set -euo pipefail

LOGIN_AGENT="${HOME}/Library/LaunchAgents/local.proxygateway.desktop.login.plist"

if [[ -x "${HOME}/ProxyGatewayMacVPN/macvpnctl.sh" ]]; then
  if [[ -z "${PROXY_GATEWAY_SUDO_PASSWORD:-}" && "$(uname -s)" == "Darwin" ]]; then
    sudo -v || true
  fi
  "${HOME}/ProxyGatewayMacVPN/macvpnctl.sh" uninstall || true
fi

launchctl bootout "gui/$(id -u)" "${LOGIN_AGENT}" >/dev/null 2>&1 || true
rm -f "${LOGIN_AGENT}"
defaults delete local.proxygateway.desktop >/dev/null 2>&1 || true

echo "Proxy Gateway removed. Local app, configuration, generated runtime files, startup items, and project preferences were deleted where permissions allowed."
UNINSTALL

chmod +x "${PACKAGE_DIR}/Install Proxy Gateway.command" "${PACKAGE_DIR}/Uninstall Proxy Gateway.command"

cat >"${PACKAGE_DIR}/README_SELF_USE.md" <<'README'
# Proxy Gateway Mac Self-Use Package

This package installs code, templates, and scripts only.

It does not include real upstream servers, passwords, auth strings, profile secrets, generated runtime config, logs, or state.

Import a private profile after installation.
README

if find "${PACKAGE_DIR}" -type f \( -name 'upstream.json' -o -name 'sing-box.json' -o -name 'profile.json.enc' -o -name '*.log' -o -name 'verify-mac-desktop-state.sh' -o -name 'verify-mac-ui-closeout.sh' -o -name 'package-self-use-installer.sh' \) | grep -q .; then
  echo "package contains private or runtime config artifacts" >&2
  exit 1
fi

test -f "${PACKAGE_DIR}/notices/LICENSE"
test -f "${PACKAGE_DIR}/notices/THIRD_PARTY_NOTICES.md"

(cd "${OUT_DIR}" && zip -qry "${ZIP_PATH}" "$(basename "${PACKAGE_DIR}")")
printf 'wrote: %s\n' "${ZIP_PATH}"
