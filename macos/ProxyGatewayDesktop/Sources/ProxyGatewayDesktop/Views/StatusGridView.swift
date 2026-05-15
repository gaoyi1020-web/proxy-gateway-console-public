import SwiftUI

struct StatusGridView: View {
    let status: MacVpnStatus

    private let columns = [
        GridItem(.flexible(minimum: 180), spacing: 12),
        GridItem(.flexible(minimum: 180), spacing: 12)
    ]

    var body: some View {
        LazyVGrid(columns: columns, alignment: .leading, spacing: 12) {
            StatusItem(title: "网关状态", value: status.displayMode, image: "power")
            StatusItem(title: "根进程", value: display(status.rootProcess), image: "terminal")
            StatusItem(title: "配置文件", value: display(status.upstreamProfile), image: "doc.text")
            StatusItem(title: "渲染配置", value: display(status.renderedConfig), image: "slider.horizontal.3")
            StatusItem(title: "核心服务", value: display(status.singBox), image: "shippingbox")
            StatusItem(title: "启动项", value: display(status.launchd), image: "gearshape.2")
        }
    }

    private func display(_ value: String) -> String {
        switch value {
        case "present":
            return "已就绪"
        case "missing":
            return "缺失"
        case "running":
            return "运行中"
        case "not running":
            return "已停止"
        case "loaded":
            return "已加载"
        case "not loaded":
            return "未加载"
        case "unknown", "":
            return "未知"
        default:
            return value
        }
    }
}

private struct StatusItem: View {
    let title: String
    let value: String
    let image: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Image(systemName: image)
                .foregroundStyle(.secondary)
                .frame(width: 18)

            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Text(value.isEmpty ? "未知" : value)
                    .font(.body.weight(.medium))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}
