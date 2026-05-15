import Foundation
import UserNotifications

final class NotificationService {
    static let shared = NotificationService()

    private let bundleURL: URL
    private var center: UNUserNotificationCenter?
    private var configured = false

    init(bundleURL: URL = Bundle.main.bundleURL) {
        self.bundleURL = bundleURL
    }

    static func isNotificationBundleSupported(bundleURL: URL) -> Bool {
        bundleURL.pathExtension.lowercased() == "app"
    }

    func configure() {
        guard !configured else {
            return
        }
        configured = true
        guard let center = notificationCenter() else {
            return
        }
        center.delegate = NotificationDelegate.shared
        center.requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    func notify(command: MacVpnCommand, result: ProcessCommandResult, status: MacVpnStatus) {
        guard command != .status || !result.ok else {
            return
        }

        let title: String
        let body: String

        switch command {
        case .startRoot:
            title = result.ok ? "Proxy Gateway 已开启" : "Proxy Gateway 开启失败"
            body = result.ok ? status.displayMode : failureBody(result)
        case .stopRoot:
            title = result.ok ? "Proxy Gateway 已停止" : "Proxy Gateway 停止失败"
            body = result.ok ? status.displayMode : failureBody(result)
        case .test:
            title = result.ok ? "Proxy Gateway 自检通过" : "Proxy Gateway 自检失败"
            body = result.ok ? "连接自检已完成。" : failureBody(result)
        case .status:
            title = "Proxy Gateway 状态刷新失败"
            body = failureBody(result)
        }

        send(title: title, body: body)
    }

    private func failureBody(_ result: ProcessCommandResult) -> String {
        let output = result.redactedOutput.trimmingCharacters(in: .whitespacesAndNewlines)
        if output.isEmpty {
            return "命令退出码：\(result.exitCode)。"
        }
        return String(output.prefix(180))
    }

    private func send(title: String, body: String) {
        guard let center = notificationCenter() else {
            return
        }

        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: "proxy-gateway-\(UUID().uuidString)",
            content: content,
            trigger: nil
        )
        center.add(request) { _ in }
    }

    private func notificationCenter() -> UNUserNotificationCenter? {
        guard Self.isNotificationBundleSupported(bundleURL: bundleURL) else {
            return nil
        }

        if let center {
            return center
        }

        let currentCenter = UNUserNotificationCenter.current()
        center = currentCenter
        return currentCenter
    }
}

final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationDelegate()

    private override init() {}

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }
}
