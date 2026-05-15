import AppKit
import SwiftUI

struct StatusBarMenuView: View {
    @ObservedObject var store: MacVpnStore
    @ObservedObject var preferences: AppPreferences

    var body: some View {
        let panelState = MenuBarPanelState(status: store.status, isBusy: store.isBusy)

        VStack(spacing: 0) {
            MenuBarStatusHeaderView(store: store, panelState: panelState)

            Divider()

            MenuBarSummaryGridView(panelState: panelState)

            Divider()

            MenuBarQuickActionsView(store: store, panelState: panelState)

            Divider()

            MenuBarPreferenceActionsView(preferences: preferences)
        }
        .frame(width: 344)
        .padding(.vertical, 10)
    }
}

private struct MenuBarStatusHeaderView: View {
    @ObservedObject var store: MacVpnStore
    let panelState: MenuBarPanelState

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: panelState.symbolName)
                .font(.system(size: 26, weight: .semibold))
                .foregroundStyle(statusColor)
                .frame(width: 30, height: 32)

            VStack(alignment: .leading, spacing: 4) {
                Text(panelState.title)
                    .font(.headline)

                Text(panelState.subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 8)

            Toggle(
                "",
                isOn: Binding(
                    get: { store.status.isRunning },
                    set: { shouldRun in
                        guard !store.isBusy else {
                            return
                        }

                        if shouldRun, !store.status.isRunning {
                            store.perform(.startRoot)
                        } else if !shouldRun, store.status.isRunning {
                            store.perform(.stopRoot)
                        }
                    }
                )
            )
            .toggleStyle(.switch)
            .labelsHidden()
            .disabled(store.isBusy || panelState.primaryCommand == nil)
            .help(store.status.isRunning ? "停止网关" : "开启网关")
        }
        .padding(.horizontal, 14)
        .padding(.bottom, 10)
    }

    private var statusColor: Color {
        if store.isBusy {
            return .accentColor
        }

        if store.status.isRunning {
            return .green
        }

        if panelState.primaryCommand == nil {
            return .orange
        }

        return .secondary
    }
}

private struct MenuBarSummaryGridView: View {
    let panelState: MenuBarPanelState

    var body: some View {
        LazyVGrid(columns: columns, spacing: 8) {
            MenuBarSummaryTile(title: "Root", value: panelState.rootSummary, systemImage: "terminal")
            MenuBarSummaryTile(title: "出口 IP", value: panelState.exitIpSummary, systemImage: "network")
            MenuBarSummaryTile(title: "DNS", value: panelState.dnsSummary, systemImage: "dot.radiowaves.left.and.right")
            MenuBarSummaryTile(title: "IPv6", value: panelState.ipv6Summary, systemImage: "globe")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private var columns: [GridItem] {
        [
            GridItem(.flexible(minimum: 0), spacing: 8),
            GridItem(.flexible(minimum: 0), spacing: 8)
        ]
    }
}

private struct MenuBarSummaryTile: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: systemImage)
                .foregroundStyle(.secondary)
                .frame(width: 16)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(.secondary)

                Text(value)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }

            Spacer(minLength: 0)
        }
        .padding(8)
        .frame(minHeight: 50)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
    }
}

private struct MenuBarQuickActionsView: View {
    @ObservedObject var store: MacVpnStore
    let panelState: MenuBarPanelState

    var body: some View {
        VStack(spacing: 8) {
            HStack(spacing: 8) {
                Button {
                    store.perform(.test)
                } label: {
                    Label("自检", systemImage: "checkmark.seal")
                        .frame(maxWidth: .infinity)
                }
                .disabled(store.isBusy || !panelState.canRunTest)

                Button {
                    openImportPanel()
                } label: {
                    Label("导入", systemImage: "square.and.arrow.down")
                        .frame(maxWidth: .infinity)
                }
                .disabled(store.isBusy)
            }

            HStack(spacing: 8) {
                Button {
                    store.refresh()
                } label: {
                    Label("刷新", systemImage: "arrow.clockwise")
                        .frame(maxWidth: .infinity)
                }
                .disabled(store.isBusy)

                Button {
                    runPrimaryAction()
                } label: {
                    Label(panelState.primaryActionTitle, systemImage: panelState.primaryCommand?.systemImage ?? "power")
                        .frame(maxWidth: .infinity)
                }
                .disabled(store.isBusy || panelState.primaryCommand == nil)
            }

            Button {
                MainWindowController.shared.showFallbackWindowIfNeeded()
            } label: {
                Label("打开高级控制台", systemImage: "macwindow")
                    .frame(maxWidth: .infinity)
            }
            .keyboardShortcut("o")
        }
        .buttonStyle(.bordered)
        .controlSize(.regular)
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private func runPrimaryAction() {
        guard let command = panelState.primaryCommand else {
            return
        }

        store.perform(command)
    }

    private func openImportPanel() {
        guard case .selected(let url) = MacVpnConfigImportPanel.selectConfig() else {
            return
        }

        store.importConfig(from: url)
    }
}

private struct MenuBarPreferenceActionsView: View {
    @ObservedObject var preferences: AppPreferences

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle(
                "后台运行",
                isOn: Binding(
                    get: { preferences.runInBackground },
                    set: { preferences.setRunInBackground($0) }
                )
            )

            Toggle(
                "开机启动",
                isOn: Binding(
                    get: { preferences.launchAtLogin },
                    set: { preferences.setLaunchAtLogin($0) }
                )
            )

            if let error = preferences.lastError {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .lineLimit(2)
            }

            Button("退出 Proxy Gateway") {
                NSApp.terminate(nil)
            }
            .padding(.top, 2)
        }
        .padding(.horizontal, 14)
        .padding(.top, 10)
    }
}
