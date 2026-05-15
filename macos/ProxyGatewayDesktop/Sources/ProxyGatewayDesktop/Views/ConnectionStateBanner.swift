import SwiftUI

struct ConnectionStateBanner: View {
    let viewState: MacVpnViewState
    let isBusy: Bool
    let updatedAt: Date?

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: viewState.symbolName)
                .font(.system(size: 32, weight: .semibold))
                .foregroundStyle(viewState.tone.color)
                .frame(width: 42, height: 42)

            VStack(alignment: .leading, spacing: 4) {
                Text("Proxy Gateway")
                    .font(.title2.weight(.semibold))

                HStack(spacing: 8) {
                    Circle()
                        .fill(isBusy ? Color.accentColor : viewState.tone.color)
                        .frame(width: 8, height: 8)

                    Text(isBusy ? "执行中" : viewState.title)
                        .font(.headline)
                }

                Text(viewState.subtitle)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            if let updatedAt {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("最后更新")
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    Text(updatedAt, style: .time)
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}
