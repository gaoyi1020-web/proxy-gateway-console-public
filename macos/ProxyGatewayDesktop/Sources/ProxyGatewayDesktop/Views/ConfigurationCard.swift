import SwiftUI

struct ConfigurationCard: View {
    @ObservedObject var store: MacVpnStore
    let viewState: MacVpnViewState
    @State private var importError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("配置")
                        .font(.headline)

                    Text(viewState.configLabel)
                        .font(.callout.weight(.medium))
                        .foregroundStyle(configColor)
                }

                Spacer()

                Button {
                    openImportPanel()
                } label: {
                    Label("导入配置", systemImage: "square.and.arrow.down")
                }
                .buttonStyle(.bordered)
                .disabled(store.isBusy || !viewState.canImportConfig)
                .accessibilityLabel("导入配置")
                .help("导入 upstream.json 或 profile.json.enc")
            }

            if let importError {
                Text(importError)
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
        .padding(12)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var configColor: Color {
        switch viewState.configLabel {
        case "可用":
            return .green
        case "需检查":
            return .red
        default:
            return .orange
        }
    }

    private func openImportPanel() {
        switch MacVpnConfigImportPanel.selectConfig() {
        case .selected(let url):
            importError = nil
            store.importConfig(from: url)
        case .cancelled:
            return
        case .invalid:
            importError = "请选择 upstream.json 或 profile.json.enc。"
        }
    }
}
