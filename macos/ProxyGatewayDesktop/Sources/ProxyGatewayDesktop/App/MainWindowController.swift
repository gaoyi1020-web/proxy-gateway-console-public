import AppKit
import SwiftUI

@MainActor
final class MainWindowController: NSObject, NSWindowDelegate {
    static let shared = MainWindowController()

    private var consoleWindow: NSWindow?

    private override init() {}

    @discardableResult
    func focusExistingMainWindow() -> Bool {
        guard let window = NSApp.windows.first(where: { $0.title == "Proxy Gateway Advanced Console" }) else {
            return false
        }

        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
        return true
    }

    func showFallbackWindowIfNeeded() {
        if focusExistingMainWindow() {
            return
        }

        let window = consoleWindow ?? makeWindow()
        consoleWindow = window
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
    }

    func windowWillClose(_ notification: Notification) {
        if UserDefaults.standard.bool(forKey: AppPreferenceKeys.runInBackground) {
            NSApp.setActivationPolicy(.accessory)
        }
    }

    private func makeWindow() -> NSWindow {
        let rootView = ContentView(
            store: AppServices.shared.store,
            preferences: AppServices.shared.preferences
        )
        .frame(minWidth: 760, minHeight: 620)

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 860, height: 680),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Proxy Gateway Advanced Console"
        window.contentView = NSHostingView(rootView: rootView)
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.center()
        return window
    }
}
