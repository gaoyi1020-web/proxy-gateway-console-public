import SwiftUI

struct CommandOutputView: View {
    let result: ProcessCommandResult?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("最近结果")
                    .font(.headline)

                Spacer()

                if let result {
                    Label(result.ok ? "通过" : "失败", systemImage: result.ok ? "checkmark.circle" : "xmark.octagon")
                        .font(.caption)
                        .foregroundStyle(result.ok ? .green : .red)
                }
            }

            ScrollView {
                Text(output)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .padding(12)
            }
            .frame(minHeight: 130, maxHeight: 190)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
    }

    private var output: String {
        guard let result else {
            return "还没有执行命令。"
        }

        let body = result.redactedOutput.trimmingCharacters(in: .whitespacesAndNewlines)
        if body.isEmpty {
            return "\(result.command): exit \(result.exitCode)"
        }
        return body
    }
}
