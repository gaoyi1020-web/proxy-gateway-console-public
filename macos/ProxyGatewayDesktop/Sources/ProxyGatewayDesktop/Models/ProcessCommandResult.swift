import Foundation

struct ProcessCommandResult: Equatable {
    var ok: Bool
    var command: String
    var stdout: String
    var stderr: String
    var exitCode: Int32

    var redactedOutput: String {
        let combined = [stdout, stderr]
            .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            .joined(separator: "\n")
        return Redactor.redact(combined)
    }
}
