import SwiftUI

struct SystemOptionsRow: View {
    @ObservedObject var preferences: AppPreferences

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("运行方式")
                .font(.headline)

            HStack(spacing: 18) {
                Toggle(
                    "后台运行",
                    isOn: Binding(
                        get: { preferences.runInBackground },
                        set: { preferences.setRunInBackground($0) }
                    )
                )

                Toggle(
                    "开机启动",
                    isOn: Binding(
                        get: { preferences.launchAtLogin },
                        set: { preferences.setLaunchAtLogin($0) }
                    )
                )

                Spacer()
            }

            if let error = preferences.lastError {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .lineLimit(1)
            }
        }
        .padding(14)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}
