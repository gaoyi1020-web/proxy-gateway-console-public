import SwiftUI

struct LifecycleSettingsView: View {
    @ObservedObject var preferences: AppPreferences

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("运行方式")
                .font(.headline)

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

            if let error = preferences.lastError {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .lineLimit(2)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}
