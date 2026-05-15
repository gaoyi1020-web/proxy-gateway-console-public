import Foundation

enum Redactor {
    static func redact(_ input: String) -> String {
        input
            .components(separatedBy: .newlines)
            .map(redactLine)
            .joined(separator: "\n")
    }

    private static func redactLine(_ line: String) -> String {
        let lower = line.lowercased()
        let sensitiveMarkers = [
            "password",
            "passwd",
            "api_key",
            "apikey",
            "credential",
            "auth",
            "\"server\"",
            "server:",
            "server=",
            "server_port",
            "ss://",
            "vmess://",
            "trojan://"
        ]

        if sensitiveMarkers.contains(where: { lower.contains($0) }) {
            return "[redacted]"
        }

        return line
    }
}
