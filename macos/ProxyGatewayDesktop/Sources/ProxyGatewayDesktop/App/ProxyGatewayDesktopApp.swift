import AppKit
import SwiftUI

@main
struct ProxyGatewayDesktopApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var store: MacVpnStore
    @StateObject private var preferences: AppPreferences

    init() {
        let services = AppServices.shared
        _store = StateObject(wrappedValue: services.store)
        _preferences = StateObject(wrappedValue: services.preferences)
    }

    var body: some Scene {
        MenuBarExtra {
            StatusBarMenuView(store: store, preferences: preferences)
                .onAppear {
                    store.refresh()
                    preferences.refreshLaunchAtLogin()
                }
        } label: {
            let panelState = MenuBarPanelState(status: store.status, isBusy: store.isBusy)
            Label(panelState.menuBarTitle, systemImage: panelState.symbolName)
        }
        .menuBarExtraStyle(.window)
    }
}

@MainActor
final class AppServices {
    static let shared = AppServices()

    let store = MacVpnStore(controller: MacVpnController())
    let preferences = AppPreferences()

    private init() {}
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        AppPreferenceKeys.registerDefaults()
        NSApp.setActivationPolicy(.accessory)
        NotificationService.shared.configure()

        AppServices.shared.store.refresh()
        AppServices.shared.preferences.refreshLaunchAtLogin()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        !UserDefaults.standard.bool(forKey: AppPreferenceKeys.runInBackground)
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            MainWindowController.shared.showFallbackWindowIfNeeded()
        }

        return true
    }
}
