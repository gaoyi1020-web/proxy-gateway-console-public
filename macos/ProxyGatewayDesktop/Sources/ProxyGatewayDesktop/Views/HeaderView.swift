import SwiftUI

struct HeaderView: View {
    let status: MacVpnStatus
    let isBusy: Bool

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: status.isRunning ? "shield.lefthalf.filled" : "shield")
                .font(.system(size: 28, weight: .semibold))
                .foregroundStyle(status.isRunning ? .green : .secondary)
                .frame(width: 34)

            VStack(alignment: .leading, spacing: 4) {
                Text("Proxy Gateway")
                    .font(.title2.weight(.semibold))

                HStack(spacing: 8) {
                    Circle()
                        .fill(status.isRunning ? Color.green : Color.secondary)
                        .frame(width: 8, height: 8)

                    Text(isBusy ? "执行中" : status.displayMode)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            if let updatedAt = status.updatedAt {
                Text(updatedAt, style: .time)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
    }
}
