import Foundation
import XCTest
@testable import ProxyGatewayDesktop

final class MacVpnStatusTests: XCTestCase {
    func testParsesMacVpnStatusOutput() {
        let output = """
        Mac VPN kit status:
          mode: root-running
          app_dir: ~/ProxyGatewayMacVPN
          upstream profile: present
          rendered config: present
          sing-box: present
          launchd plist: missing
          launchd: not loaded
          root process: running
        """

        let status = MacVpnStatus.parse(output)

        XCTAssertEqual(status.mode, "root-running")
        XCTAssertEqual(status.upstreamProfile, "present")
        XCTAssertEqual(status.renderedConfig, "present")
        XCTAssertEqual(status.singBox, "present")
        XCTAssertEqual(status.launchd, "not loaded")
        XCTAssertEqual(status.rootProcess, "running")
        XCTAssertTrue(status.isRunning)
    }

    func testRedactsSensitiveOutputLines() {
        let output = """
        safe line
        password: secret
        server=example.com
        """

        let redacted = Redactor.redact(output)

        XCTAssertTrue(redacted.contains("safe line"))
        XCTAssertFalse(redacted.contains("secret"))
        XCTAssertFalse(redacted.contains("example.com"))
    }

    func testViewStateNeedsConfigWhenProfileMissing() {
        let status = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: staged
          upstream profile: missing
          rendered config: missing
          root process: not running
        """)

        let viewState = MacVpnViewState(status: status)

        XCTAssertEqual(viewState.title, "需要配置")
        XCTAssertFalse(viewState.canStart)
        XCTAssertTrue(viewState.canImportConfig)
    }

    func testViewStateRunningWhenRootProcessIsRunning() {
        let status = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: root-running
          upstream profile: present
          rendered config: present
          root process: running
        """)

        let viewState = MacVpnViewState(status: status)

        XCTAssertEqual(viewState.title, "运行中")
        XCTAssertFalse(viewState.canStart)
        XCTAssertTrue(viewState.canStop)
        XCTAssertTrue(viewState.canTest)
    }

    func testViewStateStoppedWhenConfigIsReadyAndProcessIsStopped() {
        let status = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: staged
          upstream profile: present
          rendered config: present
          root process: not running
        """)

        let viewState = MacVpnViewState(status: status)

        XCTAssertEqual(viewState.title, "已停止")
        XCTAssertTrue(viewState.canStart)
        XCTAssertFalse(viewState.canStop)
        XCTAssertTrue(viewState.canTest)
    }

    func testDisplayModeUsesGatewayTerminology() {
        let rootStatus = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: root-running
          root process: running
        """)

        let stagedStatus = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: staged
          root process: not running
        """)

        XCTAssertEqual(rootStatus.displayMode, "网关运行中")
        XCTAssertEqual(stagedStatus.displayMode, "配置就绪")
    }

    func testViewStateUsesMainWindowControlLabels() {
        let runningStatus = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: root-running
          upstream profile: present
          rendered config: present
          root process: running
        """)

        let missingConfigStatus = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: staged
          upstream profile: missing
          rendered config: missing
          root process: not running
        """)

        XCTAssertEqual(MacVpnViewState(status: runningStatus).title, "运行中")
        XCTAssertEqual(MacVpnViewState(status: runningStatus).configLabel, "可用")
        XCTAssertEqual(MacVpnViewState(status: missingConfigStatus).title, "需要配置")
        XCTAssertEqual(MacVpnViewState(status: missingConfigStatus).configLabel, "未导入")
    }

    func testMenuBarPanelStateSummarizesRunningGateway() {
        let status = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: root-running
          upstream profile: present
          rendered config: present
          launchd: loaded
          root process: running
        """)

        let panelState = MenuBarPanelState(status: status, isBusy: false)

        XCTAssertEqual(panelState.title, "网关已开启")
        XCTAssertEqual(panelState.subtitle, "Root 服务正在运行，当前版本聚焦 IPv4 路径。")
        XCTAssertEqual(panelState.symbolName, "shield.lefthalf.filled")
        XCTAssertEqual(panelState.menuBarTitle, "网关")
        XCTAssertEqual(panelState.primaryActionTitle, "停止")
        XCTAssertEqual(panelState.primaryCommand, .stopRoot)
        XCTAssertEqual(panelState.rootSummary, "运行中")
        XCTAssertEqual(panelState.exitIpSummary, "未检测")
        XCTAssertEqual(panelState.dnsSummary, "未知")
        XCTAssertEqual(panelState.ipv6Summary, "未覆盖")
        XCTAssertTrue(panelState.canRunTest)
    }

    func testMenuBarPanelStateSummarizesReadyStoppedGateway() {
        let status = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: staged
          upstream profile: present
          rendered config: present
          launchd: not loaded
          root process: not running
        """)

        let panelState = MenuBarPanelState(status: status, isBusy: false)

        XCTAssertEqual(panelState.title, "网关已关闭")
        XCTAssertEqual(panelState.subtitle, "配置已就绪，可从菜单栏开启。")
        XCTAssertEqual(panelState.symbolName, "shield")
        XCTAssertEqual(panelState.primaryActionTitle, "开启")
        XCTAssertEqual(panelState.primaryCommand, .startRoot)
        XCTAssertEqual(panelState.rootSummary, "已停止")
        XCTAssertTrue(panelState.canRunTest)
    }

    func testMenuBarPanelStateDisablesActionsWhenBusy() {
        let status = MacVpnStatus.parse("""
        Mac VPN kit status:
          mode: root-running
          upstream profile: present
          rendered config: present
          root process: running
        """)

        let panelState = MenuBarPanelState(status: status, isBusy: true)

        XCTAssertEqual(panelState.title, "正在执行")
        XCTAssertEqual(panelState.subtitle, "请等待当前命令完成。")
        XCTAssertEqual(panelState.symbolName, "arrow.triangle.2.circlepath")
        XCTAssertNil(panelState.primaryCommand)
        XCTAssertFalse(panelState.canRunTest)
    }

    func testNotificationBundleSupportRequiresAppBundle() {
        XCTAssertTrue(NotificationService.isNotificationBundleSupported(bundleURL: URL(fileURLWithPath: "/Applications/Proxy Gateway Desktop.app")))
        XCTAssertFalse(NotificationService.isNotificationBundleSupported(bundleURL: URL(fileURLWithPath: "/tmp/ProxyGatewayDesktop/.build/debug")))
    }
}
