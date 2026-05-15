import Foundation

enum MacVpnCommand: String, CaseIterable, Identifiable {
    case status
    case test
    case startRoot = "start-root"
    case stopRoot = "stop-root"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .status:
            return "刷新"
        case .test:
            return "自检"
        case .startRoot:
            return "开启"
        case .stopRoot:
            return "停止"
        }
    }

    var systemImage: String {
        switch self {
        case .status:
            return "arrow.clockwise"
        case .test:
            return "checkmark.seal"
        case .startRoot:
            return "play.fill"
        case .stopRoot:
            return "stop.fill"
        }
    }

    var requiresAdministrator: Bool {
        switch self {
        case .startRoot, .stopRoot:
            return true
        case .status, .test:
            return false
        }
    }
}
