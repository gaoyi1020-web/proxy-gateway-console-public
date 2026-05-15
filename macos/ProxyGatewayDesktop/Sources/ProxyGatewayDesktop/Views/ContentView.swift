import SwiftUI

struct ContentView: View {
    @ObservedObject var store: MacVpnStore
    @ObservedObject var preferences: AppPreferences

    var body: some View {
        let viewState = MacVpnViewState(status: store.status)
        let panelState = MenuBarPanelState(status: store.status, isBusy: store.isBusy)

        HStack(spacing: 0) {
            AdvancedConsoleSidebar(
                status: store.status,
                viewState: viewState,
                panelState: panelState
            )

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    AdvancedConsoleHero(store: store, viewState: viewState, panelState: panelState)
                    AdvancedConsoleMetricGrid(status: store.status, panelState: panelState)

                    HStack(alignment: .top, spacing: 16) {
                        AdvancedConsoleOperations(store: store, viewState: viewState)
                            .frame(maxWidth: .infinity)

                        VStack(alignment: .leading, spacing: 16) {
                            ConfigurationCard(store: store, viewState: viewState)
                            SystemOptionsRow(preferences: preferences)
                        }
                        .frame(maxWidth: .infinity)
                    }

                    AdvancedDetailsDisclosure(store: store, viewState: viewState)
                        .padding(14)
                        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))

                    UninstallArea(store: store)
                }
                .padding(20)
            }
        }
        .frame(minWidth: 860, minHeight: 640)
    }
}

private struct AdvancedConsoleSidebar: View {
    let status: MacVpnStatus
    let viewState: MacVpnViewState
    let panelState: MenuBarPanelState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                Image(systemName: panelState.symbolName)
                    .font(.system(size: 30, weight: .semibold))
                    .foregroundStyle(viewState.tone.color)
                    .frame(width: 36, height: 36, alignment: .leading)

                Text("Proxy Gateway")
                    .font(.title3.weight(.semibold))

                Text("Advanced Console")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 10) {
                SidebarStatusRow(title: "Gateway", value: panelState.title, systemImage: "shield")
                SidebarStatusRow(title: "Root", value: panelState.rootSummary, systemImage: "terminal")
                SidebarStatusRow(title: "Config", value: panelState.configSummary, systemImage: "doc.text")
                SidebarStatusRow(title: "Scope", value: panelState.routeScopeSummary, systemImage: "point.3.connected.trianglepath.dotted")
            }

            Spacer()

            Text("日常开关请使用菜单栏。这里保留完整状态、日志、配置和卸载入口。")
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if let updatedAt = status.updatedAt {
                Label {
                    Text(updatedAt, style: .time)
                } icon: {
                    Image(systemName: "clock")
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
        }
        .padding(18)
        .frame(width: 214)
        .background(.bar)
    }
}

private struct SidebarStatusRow: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        HStack(spacing: 10) {
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
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct AdvancedConsoleHero: View {
    @ObservedObject var store: MacVpnStore
    let viewState: MacVpnViewState
    let panelState: MenuBarPanelState

    var body: some View {
        HStack(alignment: .center, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                Text(panelState.title)
                    .font(.system(size: 28, weight: .semibold))

                Text(panelState.subtitle)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)

                HStack(spacing: 8) {
                    Label(panelState.routeScopeSummary, systemImage: "network")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)

                    Label("IPv6 \(panelState.ipv6Summary)", systemImage: "globe")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.orange)
                }
            }

            Spacer()

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
            .scaleEffect(1.08)
            .disabled(store.isBusy || panelState.primaryCommand == nil)
            .help(store.status.isRunning ? "停止网关" : "开启网关")
        }
        .padding(18)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct AdvancedConsoleMetricGrid: View {
    let status: MacVpnStatus
    let panelState: MenuBarPanelState

    private let columns = [
        GridItem(.flexible(minimum: 140), spacing: 12),
        GridItem(.flexible(minimum: 140), spacing: 12),
        GridItem(.flexible(minimum: 140), spacing: 12),
        GridItem(.flexible(minimum: 140), spacing: 12)
    ]

    var body: some View {
        LazyVGrid(columns: columns, spacing: 12) {
            MetricTile(title: "Root Service", value: panelState.rootSummary, systemImage: "terminal")
            MetricTile(title: "Launchd", value: display(status.launchd), systemImage: "gearshape.2")
            MetricTile(title: "Exit IP", value: panelState.exitIpSummary, systemImage: "network")
            MetricTile(title: "IPv6", value: panelState.ipv6Summary, systemImage: "globe")
        }
    }

    private func display(_ value: String) -> String {
        switch value {
        case "loaded":
            return "已加载"
        case "not loaded":
            return "未加载"
        case "unknown", "":
            return "未知"
        default:
            return value
        }
    }
}

private struct MetricTile: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.body.weight(.medium))
                .foregroundStyle(.secondary)
                .frame(width: 18)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(.secondary)

                Text(value.isEmpty ? "未知" : value)
                    .font(.callout.weight(.semibold))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 64, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct AdvancedConsoleOperations: View {
    @ObservedObject var store: MacVpnStore
    let viewState: MacVpnViewState

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Operations")
                        .font(.headline)

                    Text(viewState.gatewaySwitchSubtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }

                Spacer()

                if store.isBusy {
                    ProgressView()
                        .controlSize(.small)
                }
            }

            HStack(spacing: 10) {
                Button {
                    store.perform(store.status.isRunning ? .stopRoot : .startRoot)
                } label: {
                    Label(store.status.isRunning ? "停止网关" : "开启网关", systemImage: store.status.isRunning ? "stop.fill" : "play.fill")
                        .frame(maxWidth: .infinity, minHeight: 34)
                }
                .buttonStyle(.borderedProminent)
                .disabled(store.isBusy || primaryActionDisabled)

                Button {
                    store.perform(.test)
                } label: {
                    Label("自检", systemImage: "checkmark.seal")
                        .frame(maxWidth: .infinity, minHeight: 34)
                }
                .buttonStyle(.bordered)
                .disabled(store.isBusy || !viewState.canTest)

                Button {
                    store.refresh()
                } label: {
                    Label("刷新", systemImage: "arrow.clockwise")
                        .frame(width: 74, height: 34)
                }
                .buttonStyle(.bordered)
                .disabled(store.isBusy)
            }

            CommandOutputView(result: store.lastResult)
        }
        .padding(14)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var primaryActionDisabled: Bool {
        if store.status.isRunning {
            return !viewState.canStop
        }

        return !viewState.canStart
    }
}
