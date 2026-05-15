import Foundation

@MainActor
final class AppPreferences: ObservableObject {
    @Published private(set) var runInBackground: Bool
    @Published private(set) var launchAtLogin: Bool
    @Published private(set) var lastError: String?

    private let launchAtLoginManager: LaunchAtLoginManager

    init(launchAtLoginManager: LaunchAtLoginManager = LaunchAtLoginManager()) {
        AppPreferenceKeys.registerDefaults()
        self.launchAtLoginManager = launchAtLoginManager
        runInBackground = UserDefaults.standard.bool(forKey: AppPreferenceKeys.runInBackground)
        launchAtLogin = launchAtLoginManager.isEnabled
    }

    func setRunInBackground(_ enabled: Bool) {
        runInBackground = enabled
        UserDefaults.standard.set(enabled, forKey: AppPreferenceKeys.runInBackground)
        lastError = nil
    }

    func setLaunchAtLogin(_ enabled: Bool) {
        do {
            try launchAtLoginManager.setEnabled(enabled)
            launchAtLogin = launchAtLoginManager.isEnabled
            lastError = nil
        } catch {
            launchAtLogin = launchAtLoginManager.isEnabled
            lastError = error.localizedDescription
        }
    }

    func refreshLaunchAtLogin() {
        launchAtLogin = launchAtLoginManager.isEnabled
    }
}
