import SwiftUI

struct PrimaryActionPanel: View {
    @ObservedObject var store: MacVpnStore
    let viewState: MacVpnViewState

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("功能开关")
                .font(.headline)

            HStack(spacing: 14) {
                Toggle(
                    isOn: Binding(
                        get: { store.status.isRunning },
                        set: { shouldRun in
                            guard shouldRun != store.status.isRunning else {
                                return
                            }

                            store.perform(shouldRun ? .startRoot : .stopRoot)
                        }
                    )
                ) {
                    HStack(spacing: 10) {
                        Image(systemName: store.status.isRunning ? "shield.lefthalf.filled" : "shield")
                            .foregroundStyle(viewState.tone.color)
                            .frame(width: 22)

                        VStack(alignment: .leading, spacing: 3) {
                            Text(viewState.gatewaySwitchTitle)
                                .font(.body.weight(.medium))

                            Text(viewState.gatewaySwitchSubtitle)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                    }
                }
                .toggleStyle(.switch)
                .disabled(store.isBusy || gatewayToggleDisabled)

                Spacer()

                Button {
                    store.perform(.test)
                } label: {
                    Label("自检", systemImage: "checkmark.seal")
                        .frame(width: 86, height: 32)
                }
                .buttonStyle(.bordered)
                .disabled(store.isBusy || !viewState.canTest)

                Button {
                    store.refresh()
                } label: {
                    Label("刷新", systemImage: "arrow.clockwise")
                        .labelStyle(.iconOnly)
                        .frame(width: 32, height: 32)
                }
                .buttonStyle(.bordered)
                .disabled(store.isBusy)
                .help("刷新状态")
            }
        }
        .padding(14)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var gatewayToggleDisabled: Bool {
        if store.status.isRunning {
            return !viewState.canStop
        }

        return !viewState.canStart
    }
}
