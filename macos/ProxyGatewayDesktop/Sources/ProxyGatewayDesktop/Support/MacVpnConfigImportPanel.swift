import AppKit
import UniformTypeIdentifiers

enum MacVpnConfigImportPanel {
    enum Selection {
        case selected(URL)
        case cancelled
        case invalid
    }

    @MainActor
    static func selectConfig() -> Selection {
        let panel = NSOpenPanel()
        panel.title = "导入 Proxy Gateway 配置"
        panel.prompt = "导入"
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.json, UTType(filenameExtension: "enc") ?? .data]

        guard panel.runModal() == .OK, let url = panel.url else {
            return .cancelled
        }

        guard MacVpnImportKind(url: url) != nil else {
            return .invalid
        }

        return .selected(url)
    }
}
