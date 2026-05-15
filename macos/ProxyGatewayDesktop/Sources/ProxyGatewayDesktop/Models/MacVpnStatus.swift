import Foundation

struct MacVpnStatus: Equatable {
    var mode: String
    var appDirectory: String
    var upstreamProfile: String
    var renderedConfig: String
    var singBox: String
    var launchd: String
    var rootProcess: String
    var updatedAt: Date?
    var rawOutput: String

    static let empty = MacVpnStatus(
        mode: "unknown",
        appDirectory: "",
        upstreamProfile: "unknown",
        renderedConfig: "unknown",
        singBox: "unknown",
        launchd: "unknown",
        rootProcess: "unknown",
        updatedAt: nil,
        rawOutput: ""
    )

    var isRunning: Bool {
        mode == "root-running" || mode == "running" || rootProcess == "running" || launchd == "loaded"
    }

    var displayMode: String {
        switch mode {
        case "root-running":
            return "网关运行中"
        case "running":
            return "用户网关运行中"
        case "staged":
            return "配置就绪"
        case "unknown":
            return "未知"
        default:
            return mode
        }
    }

    static func parse(_ output: String, updatedAt: Date = Date()) -> MacVpnStatus {
        var status = MacVpnStatus.empty
        status.updatedAt = updatedAt
        status.rawOutput = Redactor.redact(output)

        for line in output.components(separatedBy: .newlines) {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard let separator = trimmed.firstIndex(of: ":") else {
                continue
            }

            let key = trimmed[..<separator].trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let value = trimmed[trimmed.index(after: separator)...].trimmingCharacters(in: .whitespacesAndNewlines)

            switch key {
            case "mode":
                status.mode = value
            case "app_dir":
                status.appDirectory = value
            case "upstream profile":
                status.upstreamProfile = value
            case "rendered config":
                status.renderedConfig = value
            case "sing-box":
                status.singBox = value
            case "launchd":
                status.launchd = value
            case "root process":
                status.rootProcess = value
            default:
                continue
            }
        }

        return status
    }
}
