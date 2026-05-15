import Foundation

@MainActor
final class MacVpnStore: ObservableObject {
    @Published private(set) var status: MacVpnStatus = .empty
    @Published private(set) var isBusy = false
    @Published private(set) var busyCommand: MacVpnCommand?
    @Published private(set) var lastResult: ProcessCommandResult?

    private let controller: MacVpnController
    private let notificationService: NotificationService

    init(controller: MacVpnController, notificationService: NotificationService = .shared) {
        self.controller = controller
        self.notificationService = notificationService
    }

    func refresh() {
        perform(.status)
    }

    func perform(_ command: MacVpnCommand) {
        guard !isBusy else {
            return
        }

        isBusy = true
        busyCommand = command

        Task {
            let result = await controller.run(command)
            apply(result, for: command)

            if command != .status {
                let statusResult = await controller.run(.status)
                apply(statusResult, for: .status)
                notificationService.notify(command: command, result: result, status: status)
            } else if !result.ok {
                notificationService.notify(command: command, result: result, status: status)
            }

            isBusy = false
            busyCommand = nil
        }
    }

    func importConfig(from url: URL) {
        guard !isBusy else {
            return
        }

        isBusy = true
        busyCommand = nil

        Task {
            let result = await controller.importConfig(from: url)
            lastResult = result

            let statusResult = await controller.run(.status)
            let output = statusResult.stdout.isEmpty ? statusResult.stderr : statusResult.stdout
            status = MacVpnStatus.parse(output)

            isBusy = false
        }
    }

    func uninstall(password: String) {
        guard !isBusy else {
            return
        }

        isBusy = true
        busyCommand = nil

        Task {
            let result = await controller.uninstall(password: password)
            lastResult = result

            let statusResult = await controller.run(.status)
            let output = statusResult.stdout.isEmpty ? statusResult.stderr : statusResult.stdout
            status = MacVpnStatus.parse(output)

            isBusy = false
        }
    }

    private func apply(_ result: ProcessCommandResult, for command: MacVpnCommand) {
        lastResult = result

        if command == .status {
            let output = result.stdout.isEmpty ? result.stderr : result.stdout
            status = MacVpnStatus.parse(output)
        }
    }
}
