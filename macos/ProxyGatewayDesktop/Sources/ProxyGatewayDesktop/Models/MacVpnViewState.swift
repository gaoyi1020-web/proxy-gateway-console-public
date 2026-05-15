import SwiftUI

enum MacVpnViewTone: String, Equatable {
    case running
    case stopped
    case needsConfig
    case error

    var color: Color {
        switch self {
        case .running:
            return .green
        case .stopped:
            return .secondary
        case .needsConfig:
            return .orange
        case .error:
            return .red
        }
    }
}

struct MacVpnViewState: Equatable {
    let title: String
    let subtitle: String
    let symbolName: String
    let tone: MacVpnViewTone
    let configLabel: String
    let gatewaySwitchTitle: String
    let gatewaySwitchSubtitle: String
    let canStart: Bool
    let canStop: Bool
    let canTest: Bool
    let canImportConfig: Bool
    let detailRows: [DetailRow]

    struct DetailRow: Equatable, Identifiable {
        let id: String
        let label: String
        let value: String
    }

    init(status: MacVpnStatus) {
        let hasConfig = status.upstreamProfile == "present"
        let hasRenderedConfig = status.renderedConfig == "present"
        let isRunning = status.isRunning

        if isRunning {
            title = "运行中"
            subtitle = "Proxy Gateway 正在接管此 Mac 的网络出口。"
            symbolName = "shield.lefthalf.filled"
            tone = .running
            gatewaySwitchTitle = "网络网关已开启"
            gatewaySwitchSubtitle = "关闭只停止当前服务，已导入配置会保留。"
        } else if hasConfig {
            title = hasRenderedConfig ? "已停止" : "需要配置"
            subtitle = hasRenderedConfig ? "配置已就绪，可随时开启。" : "配置需要重新导入或检查。"
            symbolName = hasRenderedConfig ? "shield" : "exclamationmark.shield"
            tone = hasRenderedConfig ? .stopped : .needsConfig
            gatewaySwitchTitle = hasRenderedConfig ? "网络网关未开启" : "网络网关不可用"
            gatewaySwitchSubtitle = hasRenderedConfig ? "开启后此 Mac 使用 Proxy Gateway 出口。" : "先导入可用配置后才能开启。"
        } else {
            title = "需要配置"
            subtitle = "导入配置后才能开启。"
            symbolName = "exclamationmark.shield"
            tone = .needsConfig
            gatewaySwitchTitle = "网络网关不可用"
            gatewaySwitchSubtitle = "先导入配置后才能开启。"
        }

        configLabel = hasConfig ? (hasRenderedConfig ? "可用" : "需检查") : "未导入"
        canStart = hasConfig && hasRenderedConfig && !isRunning
        canStop = isRunning
        canTest = hasConfig
        canImportConfig = true
        detailRows = [
            DetailRow(id: "mode", label: "运行模式", value: status.displayMode),
            DetailRow(id: "profile", label: "配置文件", value: status.upstreamProfile),
            DetailRow(id: "rendered", label: "渲染配置", value: status.renderedConfig),
            DetailRow(id: "singBox", label: "核心服务", value: status.singBox),
            DetailRow(id: "launchd", label: "启动项", value: status.launchd),
            DetailRow(id: "rootProcess", label: "根进程", value: status.rootProcess)
        ]
    }
}
