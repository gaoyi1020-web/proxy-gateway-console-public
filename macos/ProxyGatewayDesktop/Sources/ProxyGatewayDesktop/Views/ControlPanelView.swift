import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct ControlPanelView: View {
    @ObservedObject var store: MacVpnStore
    @State private var importError: String?
    @State private var showUninstallConfirmation = false
    @State private var uninstallPassword = ""
    @State private var uninstallError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("功能")
                .font(.headline)

            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 10) {
                    ControlButton(command: .startRoot, store: store, role: nil)
                    ControlButton(command: .stopRoot, store: store, role: .destructive)
                    ControlButton(command: .test, store: store, role: nil)
                    ControlButton(command: .status, store: store, role: nil)
                    ImportConfigButton(store: store, importError: $importError)
                }

                Button(role: .destructive) {
                    uninstallError = nil
                    showUninstallConfirmation = true
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "trash")
                        Text("卸载")
                    }
                    .frame(height: 30)
                }
                .buttonStyle(.bordered)
                .disabled(store.isBusy)
                .accessibilityLabel("卸载")
                .help("停止并清理 Proxy Gateway")

                if let importError {
                    Text(importError)
                        .font(.caption)
                        .foregroundStyle(.red)
                }

                if let uninstallError {
                    Text(uninstallError)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            }
        }
        .sheet(isPresented: $showUninstallConfirmation) {
            UninstallConfirmationSheet(
                store: store,
                isPresented: $showUninstallConfirmation,
                password: $uninstallPassword,
                errorMessage: $uninstallError
            )
        }
    }
}

private struct UninstallConfirmationSheet: View {
    @ObservedObject var store: MacVpnStore
    @Binding var isPresented: Bool
    @Binding var password: String
    @Binding var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("卸载 Proxy Gateway")
                .font(.headline)

            Text("这会停止 Proxy Gateway，并删除此 Mac 上的本地 App、配置、启动项和生成的运行文件。")
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            SecureField("Mac 密码", text: $password)
                .textFieldStyle(.roundedBorder)
                .disabled(store.isBusy)

            HStack {
                Spacer()

                Button("取消") {
                    password = ""
                    errorMessage = nil
                    isPresented = false
                }
                .keyboardShortcut(.cancelAction)

                Button(role: .destructive) {
                    guard !password.isEmpty else {
                        errorMessage = "需要输入 Mac 密码。"
                        return
                    }

                    let passwordToUse = password
                    password = ""
                    errorMessage = nil
                    isPresented = false
                    store.uninstall(password: passwordToUse)
                } label: {
                    Text("卸载")
                }
                .keyboardShortcut(.defaultAction)
                .disabled(store.isBusy || password.isEmpty)
            }
        }
        .padding(20)
        .frame(width: 420)
        .onDisappear {
            password = ""
        }
    }
}

private struct ImportConfigButton: View {
    @ObservedObject var store: MacVpnStore
    @Binding var importError: String?

    var body: some View {
        Button {
            openImportPanel()
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "square.and.arrow.down")
                Text("导入配置")
            }
            .frame(height: 30)
        }
        .buttonStyle(.bordered)
        .disabled(store.isBusy)
        .accessibilityLabel("导入配置")
        .help("导入 upstream.json 或 profile.json.enc")
    }

    private func openImportPanel() {
        let panel = NSOpenPanel()
        panel.title = "导入 Proxy Gateway 配置"
        panel.prompt = "导入"
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.json, UTType(filenameExtension: "enc") ?? .data]

        guard panel.runModal() == .OK, let url = panel.url else {
            return
        }

        guard MacVpnImportKind(url: url) != nil else {
            importError = "请选择 upstream.json 或 profile.json.enc。"
            return
        }

        importError = nil
        store.importConfig(from: url)
    }
}

private struct ControlButton: View {
    let command: MacVpnCommand
    @ObservedObject var store: MacVpnStore
    let role: ButtonRole?

    var body: some View {
        Button(role: role) {
            store.perform(command)
        } label: {
            HStack(spacing: 8) {
                if store.busyCommand == command {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    Image(systemName: command.systemImage)
                }

                Text(command.title)
                    .frame(minWidth: 54)
            }
            .frame(height: 30)
        }
        .buttonStyle(.bordered)
        .disabled(store.isBusy)
        .help(command.requiresAdministrator ? "需要管理员授权" : command.title)
    }
}
