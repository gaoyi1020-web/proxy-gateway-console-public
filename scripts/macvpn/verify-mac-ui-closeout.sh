#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MAC_HOST="${MAC_HOST:-example-mac.local}"
MAC_USER="${MAC_USER:-${USER:-user}}"
MAC_SSH_KEY="${MAC_SSH_KEY:-${HOME}/.ssh/proxy_gateway_mac_ed25519}"
SSH_OPTS=(-i "${MAC_SSH_KEY}" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
REMOTE="${MAC_USER}@${MAC_HOST}"

APP_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/App/ProxyGatewayDesktopApp.swift"
MAIN_WINDOW_CONTROLLER_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/App/MainWindowController.swift"
MENU_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/StatusBarMenuView.swift"
CONTENT_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/ContentView.swift"
CONTROL_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/ControlPanelView.swift"
LIFECYCLE_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/LifecycleSettingsView.swift"
OUTPUT_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/CommandOutputView.swift"
STORE_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Stores/MacVpnStore.swift"
CONTROLLER_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Services/MacVpnController.swift"
IMPORT_KIND_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Models/MacVpnImportKind.swift"
V3_STATE_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Models/MacVpnViewState.swift"
CONNECTION_BANNER_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/ConnectionStateBanner.swift"
PRIMARY_ACTION_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/PrimaryActionPanel.swift"
CONFIG_CARD_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/ConfigurationCard.swift"
SYSTEM_OPTIONS_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/SystemOptionsRow.swift"
ADVANCED_DETAILS_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/AdvancedDetailsDisclosure.swift"
UNINSTALL_AREA_FILE="${ROOT_DIR}/macos/ProxyGatewayDesktop/Sources/ProxyGatewayDesktop/Views/UninstallArea.swift"

failures=()
warnings=()

note() {
  printf '%s\n' "$*"
}

record_failure() {
  failures+=("$*")
  printf 'FAIL: %s\n' "$*" >&2
}

record_warning() {
  warnings+=("$*")
  printf 'WARN: %s\n' "$*" >&2
}

require_contains() {
  local label="$1"
  local file="$2"
  local pattern="$3"

  if grep -Fq "${pattern}" "${file}"; then
    note "PASS: ${label}"
  else
    record_failure "${label}: missing '${pattern}' in ${file#${ROOT_DIR}/}"
  fi
}

remote() {
  ssh "${SSH_OPTS[@]}" "${REMOTE}" "$@"
}

note "Mac UI closeout verification target: ${REMOTE}"

require_contains "startup-visible WindowGroup source" "${APP_FILE}" "WindowGroup(\"Proxy Gateway\")"
require_contains "appkit fallback main window source" "${MAIN_WINDOW_CONTROLLER_FILE}" "final class MainWindowController"
require_contains "launch opens fallback when needed" "${APP_FILE}" "showFallbackWindowIfNeeded()"
require_contains "status bar fallback singleton Window source" "${APP_FILE}" "Window(\"Proxy Gateway\", id: \"main\")"
require_contains "status bar focuses existing window first" "${MENU_FILE}" "if focusExistingMainWindow()"
require_contains "status bar fallback opens singleton window" "${MENU_FILE}" "openWindow(id: \"main\")"
require_contains "v3 content uses connection banner" "${CONTENT_FILE}" "ConnectionStateBanner"
require_contains "v3 content exposes status grid" "${CONTENT_FILE}" "StatusGridView(status: store.status)"
require_contains "v3 content uses primary actions" "${CONTENT_FILE}" "PrimaryActionPanel"
require_contains "v3 content uses configuration card" "${CONTENT_FILE}" "ConfigurationCard"
require_contains "v3 content uses system options row" "${CONTENT_FILE}" "SystemOptionsRow"
require_contains "v3 content uses advanced disclosure" "${CONTENT_FILE}" "AdvancedDetailsDisclosure"
require_contains "v3 content uses uninstall area" "${CONTENT_FILE}" "UninstallArea"
require_contains "v3 view state exists" "${V3_STATE_FILE}" "struct MacVpnViewState"
require_contains "v3 state handles needs config" "${V3_STATE_FILE}" "需要配置"
require_contains "v3 state exposes gateway switch title" "${V3_STATE_FILE}" "gatewaySwitchTitle"
require_contains "v3 connection banner exists" "${CONNECTION_BANNER_FILE}" "struct ConnectionStateBanner"
require_contains "v3 primary action panel exists" "${PRIMARY_ACTION_FILE}" "struct PrimaryActionPanel"
require_contains "v3 configuration card exists" "${CONFIG_CARD_FILE}" "struct ConfigurationCard"
require_contains "v3 system options row exists" "${SYSTEM_OPTIONS_FILE}" "struct SystemOptionsRow"
require_contains "v3 advanced disclosure exists" "${ADVANCED_DETAILS_FILE}" "struct AdvancedDetailsDisclosure"
require_contains "v3 advanced details keeps command output" "${ADVANCED_DETAILS_FILE}" "CommandOutputView(result: store.lastResult)"
require_contains "v3 uninstall area exists" "${UNINSTALL_AREA_FILE}" "struct UninstallArea"
require_contains "primary actions expose gateway toggle" "${PRIMARY_ACTION_FILE}" "Toggle("
require_contains "primary actions expose start gateway" "${PRIMARY_ACTION_FILE}" "store.perform(shouldRun ? .startRoot : .stopRoot)"
require_contains "primary actions expose test" "${PRIMARY_ACTION_FILE}" "store.perform(.test)"
require_contains "primary actions expose status refresh" "${PRIMARY_ACTION_FILE}" "store.refresh()"
require_contains "configuration card exposes config import" "${CONFIG_CARD_FILE}" "导入配置"
require_contains "configuration card uses native import panel" "${CONFIG_CARD_FILE}" "NSOpenPanel"
require_contains "uninstall area exposes uninstall" "${UNINSTALL_AREA_FILE}" "卸载"
require_contains "uninstall requires password confirmation" "${UNINSTALL_AREA_FILE}" "SecureField"
require_contains "uninstall warns local config deletion" "${UNINSTALL_AREA_FILE}" "本地 App、配置"
require_contains "import allows upstream adapter" "${IMPORT_KIND_FILE}" "upstream.json"
require_contains "import allows encrypted profile" "${IMPORT_KIND_FILE}" "profile.json.enc"
require_contains "store exposes config import" "${STORE_FILE}" "func importConfig"
require_contains "store exposes uninstall" "${STORE_FILE}" "func uninstall"
require_contains "controller runs selected import command" "${CONTROLLER_FILE}" "kind.importCommand"
require_contains "controller supports password-gated uninstall" "${CONTROLLER_FILE}" "func uninstall(password:"
require_contains "controller stops root service during uninstall" "${CONTROLLER_FILE}" "rootControllerPath, \"stop\""
require_contains "controller runs macvpn uninstall during uninstall" "${CONTROLLER_FILE}" "\"uninstall\""
require_contains "controller removes root artifacts during uninstall" "${CONTROLLER_FILE}" "uninstall:remove-root-artifacts"
require_contains "import model maps import-upstream" "${IMPORT_KIND_FILE}" "import-upstream"
require_contains "import model maps import-encrypted-profile" "${IMPORT_KIND_FILE}" "import-encrypted-profile"
require_contains "controller renders imported upstream" "${CONTROLLER_FILE}" "render-config"
require_contains "controller validates imported upstream" "${CONTROLLER_FILE}" "validate"
require_contains "background toggle visible" "${SYSTEM_OPTIONS_FILE}" "后台运行"
require_contains "login start toggle visible" "${SYSTEM_OPTIONS_FILE}" "开机启动"
require_contains "last command result visible" "${OUTPUT_FILE}" "最近结果"

note "PASS: status bar Open Window has existing-window guard"

if remote "pkill -x ProxyGatewayDesktop >/dev/null 2>&1 || true; open -a \"\${HOME}/Applications/Proxy Gateway Desktop.app\" && sleep 2 && pgrep -fl ProxyGatewayDesktop" >/tmp/proxygateway-ui-pgrep.out 2>&1; then
  note "PASS: installed app launch process"
else
  record_failure "installed app did not launch: $(tr '\n' ' ' </tmp/proxygateway-ui-pgrep.out)"
fi

if remote "grep -a -Fq 'Proxy Gateway' \"\${HOME}/Applications/Proxy Gateway Desktop.app/Contents/MacOS/ProxyGatewayDesktop\""; then
  note "PASS: installed binary includes app UI strings"
else
  record_failure "installed binary does not include expected app UI strings"
fi

if remote "grep -a -Fq '导入配置' \"\${HOME}/Applications/Proxy Gateway Desktop.app/Contents/MacOS/ProxyGatewayDesktop\""; then
  note "PASS: installed binary includes import UI string"
else
  record_failure "installed binary does not include 导入配置"
fi

if remote "grep -a -Fq '卸载' \"\${HOME}/Applications/Proxy Gateway Desktop.app/Contents/MacOS/ProxyGatewayDesktop\""; then
  note "PASS: installed binary includes uninstall UI string"
else
  record_failure "installed binary does not include 卸载"
fi

if remote "grep -a -Fq '需要配置' \"\${HOME}/Applications/Proxy Gateway Desktop.app/Contents/MacOS/ProxyGatewayDesktop\""; then
  note "PASS: installed binary includes v3 needs-config string"
else
  record_failure "installed binary does not include 需要配置"
fi

if remote "grep -a -Fq '诊断详情' \"\${HOME}/Applications/Proxy Gateway Desktop.app/Contents/MacOS/ProxyGatewayDesktop\""; then
  note "PASS: installed binary includes v3 details disclosure string"
else
  record_failure "installed binary does not include 诊断详情"
fi

if remote "osascript -e 'tell application \"System Events\" to tell process \"ProxyGatewayDesktop\" to return count of windows'" >/tmp/proxygateway-ui-accessibility.out 2>&1; then
  window_count="$(tr -d '[:space:]' </tmp/proxygateway-ui-accessibility.out)"
  if [[ "${window_count}" =~ ^[0-9]+$ ]] && ((window_count > 0)); then
    note "PASS: accessibility window query (${window_count})"
  else
    record_failure "accessibility window query returned ${window_count:-empty}"
  fi
else
  record_failure "accessibility window query failed: $(tr '\n' ' ' </tmp/proxygateway-ui-accessibility.out)"
fi

if remote "osascript -e 'tell application \"System Events\" to tell process \"ProxyGatewayDesktop\" to tell window \"Proxy Gateway\" to return {value of attribute \"AXTitle\", value of attribute \"AXMinimized\", value of attribute \"AXPosition\", value of attribute \"AXSize\"}'" >/tmp/proxygateway-ui-window.out 2>&1; then
  window_state="$(tr '\n' ' ' </tmp/proxygateway-ui-window.out)"
  if grep -Fq "Proxy Gateway" <<<"${window_state}" && grep -Fq "false" <<<"${window_state}"; then
    note "PASS: accessibility main window state (${window_state})"
  else
    record_failure "unexpected accessibility main window state: ${window_state}"
  fi
else
  record_failure "accessibility main window state failed: $(tr '\n' ' ' </tmp/proxygateway-ui-window.out)"
fi

if remote "osascript -e 'tell application \"System Events\" to tell process \"ProxyGatewayDesktop\" to tell scroll area 1 of group 1 of window \"Proxy Gateway\" to return {name of static texts, name of buttons, name of checkboxes}'" >/tmp/proxygateway-ui-text.out 2>&1; then
  ui_text="$(tr '\n' ' ' </tmp/proxygateway-ui-text.out)"
  if grep -Fq "Proxy Gateway" <<<"${ui_text}" \
    && grep -Fq "功能开关" <<<"${ui_text}" \
    && grep -Fq "网络网关" <<<"${ui_text}" \
    && grep -Fq "配置" <<<"${ui_text}" \
    && grep -Fq "运行方式" <<<"${ui_text}"; then
    note "PASS: accessibility main window text"
  else
    record_failure "main window text did not expose simplified control UI: ${ui_text}"
  fi
else
  record_failure "accessibility main window text failed: $(tr '\n' ' ' </tmp/proxygateway-ui-text.out)"
fi

if remote "screencapture -x /tmp/proxygateway-ui-closeout-current.png >/tmp/proxygateway-ui-screencapture.err 2>&1; test -s /tmp/proxygateway-ui-closeout-current.png"; then
  note "PASS: screenshot capture capability"
else
  record_warning "screenshot capture unavailable in current Mac session"
fi

if ((${#failures[@]})); then
  printf '\nMac UI closeout verification: fail\n' >&2
  printf ' - %s\n' "${failures[@]}" >&2
  exit 1
fi

if ((${#warnings[@]})); then
  printf '\nMac UI closeout verification: pass with warnings\n'
  printf ' - %s\n' "${warnings[@]}"
  exit 0
fi

printf '\nMac UI closeout verification: pass\n'
