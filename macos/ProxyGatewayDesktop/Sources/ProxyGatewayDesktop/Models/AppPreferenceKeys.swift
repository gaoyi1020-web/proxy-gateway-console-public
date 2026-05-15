import Foundation

enum AppPreferenceKeys {
    static let runInBackground = "runInBackground"

    static func registerDefaults() {
        let defaults = UserDefaults.standard
        let hasStoredRunInBackground = defaults.object(forKey: runInBackground) != nil
        defaults.register(defaults: [
            runInBackground: true
        ])

        if !hasStoredRunInBackground {
            defaults.set(true, forKey: runInBackground)
        }
    }
}
