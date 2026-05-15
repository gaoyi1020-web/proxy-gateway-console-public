import SwiftUI

struct UninstallArea: View {
    @ObservedObject var store: MacVpnStore
    @State private var showUninstallConfirmation = false
    @State private var uninstallPassword = ""
    @State private var uninstallError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()

            Button(role: .destructive) {
                uninstallError = nil
                showUninstallConfirmation = true
            } label: {
                Label("卸载", systemImage: "trash")
            }
            .buttonStyle(.bordered)
            .disabled(store.isBusy)
            .accessibilityLabel("卸载")
            .help("停止并清理 Proxy Gateway")

            if let uninstallError {
                Text(uninstallError)
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
        .sheet(isPresented: $showUninstallConfirmation) {
            VStack(alignment: .leading, spacing: 14) {
                Text("卸载 Proxy Gateway")
                    .font(.headline)

                Text("这会停止 Proxy Gateway，并删除此 Mac 上的本地 App、配置、启动项和生成的运行文件。")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)

                SecureField("Mac 密码", text: $uninstallPassword)
                    .textFieldStyle(.roundedBorder)
                    .disabled(store.isBusy)

                HStack {
                    Spacer()

                    Button("取消") {
                        uninstallPassword = ""
                        uninstallError = nil
                        showUninstallConfirmation = false
                    }
                    .keyboardShortcut(.cancelAction)

                    Button(role: .destructive) {
                        guard !uninstallPassword.isEmpty else {
                            uninstallError = "需要输入 Mac 密码。"
                            return
                        }

                        let passwordToUse = uninstallPassword
                        uninstallPassword = ""
                        uninstallError = nil
                        showUninstallConfirmation = false
                        store.uninstall(password: passwordToUse)
                    } label: {
                        Text("卸载")
                    }
                    .keyboardShortcut(.defaultAction)
                    .disabled(store.isBusy || uninstallPassword.isEmpty)
                }
            }
            .padding(20)
            .frame(width: 420)
            .onDisappear {
                uninstallPassword = ""
            }
        }
    }
}
