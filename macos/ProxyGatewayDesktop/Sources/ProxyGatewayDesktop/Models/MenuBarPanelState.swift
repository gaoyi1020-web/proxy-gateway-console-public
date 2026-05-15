import Foundation

struct MenuBarPanelState: Equatable {
    let title: String
    let subtitle: String
    let symbolName: String
    let menuBarTitle: String
    let primaryActionTitle: String
    let primaryCommand: MacVpnCommand?
    let rootSummary: String
    let exitIpSummary: String
    let dnsSummary: String
    let ipv6Summary: String
    let configSummary: String
    let routeScopeSummary: String
    let canRunTest: Bool

    init(status: MacVpnStatus, isBusy: Bool) {
        let viewState = MacVpnViewState(status: status)

        if isBusy {
            title = "正在执行"
            subtitle = "请等待当前命令完成。"
            symbolName = "arrow.triangle.2.circlepath"
            menuBarTitle = "执行中"
            primaryActionTitle = "执行中"
            primaryCommand = nil
            canRunTest = false
        } else if status.isRunning {
            title = "网关已开启"
            subtitle = "Root 服务正在运行，当前版本聚焦 IPv4 路径。"
            symbolName = "shield.lefthalf.filled"
            menuBarTitle = "网关"
            primaryActionTitle = "停止"
            primaryCommand = .stopRoot
            canRunTest = viewState.canTest
        } else if viewState.canStart {
            title = "网关已关闭"
            subtitle = "配置已就绪，可从菜单栏开启。"
            symbolName = "shield"
            menuBarTitle = "网关"
            primaryActionTitle = "开启"
            primaryCommand = .startRoot
            canRunTest = viewState.canTest
        } else {
            title = "需要配置"
            subtitle = "导入可用配置后才能开启网关。"
            symbolName = "exclamationmark.shield"
            menuBarTitle = "网关"
            primaryActionTitle = "不可用"
            primaryCommand = nil
            canRunTest = false
        }

        rootSummary = Self.displayRootSummary(status: status)
        exitIpSummary = "未检测"
        dnsSummary = "未知"
        ipv6Summary = "未覆盖"
        configSummary = viewState.configLabel
        routeScopeSummary = "IPv4 focused"
    }

    private static func displayRootSummary(status: MacVpnStatus) -> String {
        if status.rootProcess == "running" {
            return "运行中"
        }

        if status.rootProcess == "not running" {
            return "已停止"
        }

        if status.launchd == "loaded" {
            return "已加载"
        }

        if status.launchd == "not loaded" {
            return "未加载"
        }

        return "未知"
    }
}
