#!/usr/bin/env bash
set -euo pipefail

INSTALLER="${HOME}/ProxyGatewayDesktopApp/scripts/macvpn/install-macvpn-rootctl.sh"
USER_NAME="$(id -un)"

echo "Proxy Gateway root controller installer"
echo "User: ${USER_NAME}"
echo
echo "This one-time step installs a root-owned controller for passwordless"
echo "Start VPN / Stop VPN from the desktop app."
echo

if [[ ! -x "${INSTALLER}" ]]; then
  echo "Installer not found or not executable:"
  echo "  ${INSTALLER}"
  echo
  read -r -p "Press Enter to close."
  exit 2
fi

sudo "${INSTALLER}" --user "${USER_NAME}"
echo
echo "Verification:"
sudo -n /usr/local/sbin/proxygateway-macvpn-rootctl status
echo
echo "Done. The desktop app can now Start/Stop VPN without asking again."
read -r -p "Press Enter to close."
