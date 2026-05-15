import Foundation

final class MacVpnController {
    private let controllerPath: String
    private let loginAgentPath: String
    private let appPath: String
    private let desktopAppPath: String
    private let applicationSupportPath: String
    private let cachePath: String
    private let preferencesPath: String
    private let savedStatePath: String
    private let rootControllerPath = "/usr/local/sbin/proxygateway-macvpn-rootctl"
    private let rootDaemonPath = "/Library/LaunchDaemons/com.proxygateway.macvpn.plist"
    private let sudoersPath = "/etc/sudoers.d/proxygateway-macvpn-rootctl"

    init(homeDirectory: String = NSHomeDirectory()) {
        let homeURL = URL(fileURLWithPath: homeDirectory)
        controllerPath = homeURL
            .appendingPathComponent("ProxyGatewayMacVPN")
            .appendingPathComponent("macvpnctl.sh")
            .path
        loginAgentPath = homeURL
            .appendingPathComponent("Library")
            .appendingPathComponent("LaunchAgents")
            .appendingPathComponent("local.proxygateway.desktop.login.plist")
            .path
        appPath = homeURL
            .appendingPathComponent("Applications")
            .appendingPathComponent("Proxy Gateway Desktop.app")
            .path
        desktopAppPath = homeURL
            .appendingPathComponent("Desktop")
            .appendingPathComponent("Proxy Gateway Desktop.app")
            .path
        applicationSupportPath = homeURL
            .appendingPathComponent("Library")
            .appendingPathComponent("Application Support")
            .appendingPathComponent("Proxy Gateway")
            .path
        cachePath = homeURL
            .appendingPathComponent("Library")
            .appendingPathComponent("Caches")
            .appendingPathComponent("local.proxygateway.desktop")
            .path
        preferencesPath = homeURL
            .appendingPathComponent("Library")
            .appendingPathComponent("Preferences")
            .appendingPathComponent("local.proxygateway.desktop.plist")
            .path
        savedStatePath = homeURL
            .appendingPathComponent("Library")
            .appendingPathComponent("Saved Application State")
            .appendingPathComponent("local.proxygateway.desktop.savedState")
            .path
    }

    func run(_ command: MacVpnCommand) async -> ProcessCommandResult {
        await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                continuation.resume(returning: self.runSync(command))
            }
        }
    }

    func importConfig(from url: URL) async -> ProcessCommandResult {
        await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                continuation.resume(returning: self.runImportConfigSync(from: url))
            }
        }
    }

    func uninstall(password: String) async -> ProcessCommandResult {
        await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                continuation.resume(returning: self.runUninstallSync(password: password))
            }
        }
    }

    private func runSync(_ command: MacVpnCommand) -> ProcessCommandResult {
        guard FileManager.default.isExecutableFile(atPath: controllerPath) else {
            return ProcessCommandResult(
                ok: false,
                command: command.rawValue,
                stdout: "",
                stderr: "Proxy Gateway controller is missing at ~/ProxyGatewayMacVPN/macvpnctl.sh",
                exitCode: 127
            )
        }

        if command.requiresAdministrator {
            return runAdministratorCommand(command)
        }

        return runProcess(executable: controllerPath, arguments: [command.rawValue], commandName: command.rawValue)
    }

    private func runImportConfigSync(from url: URL) -> ProcessCommandResult {
        guard FileManager.default.isExecutableFile(atPath: controllerPath) else {
            return ProcessCommandResult(
                ok: false,
                command: "import-config",
                stdout: "",
                stderr: "Proxy Gateway controller is missing at ~/ProxyGatewayMacVPN/macvpnctl.sh",
                exitCode: 127
            )
        }

        guard let kind = MacVpnImportKind(url: url) else {
            return ProcessCommandResult(
                ok: false,
                command: "import-config",
                stdout: "",
                stderr: "Choose upstream.json or profile.json.enc.",
                exitCode: 2
            )
        }

        var results = [
            runProcess(
                executable: controllerPath,
                arguments: [kind.importCommand, "--from", url.path],
                commandName: kind.resultCommandName
            )
        ]

        if results.last?.ok == true, kind.shouldRenderAndValidate {
            results.append(runProcess(executable: controllerPath, arguments: ["render-config"], commandName: "render-config"))
        }
        if results.last?.ok == true, kind.shouldRenderAndValidate {
            results.append(runProcess(executable: controllerPath, arguments: ["validate"], commandName: "validate"))
        }
        if results.last?.ok == true {
            results.append(runProcess(executable: controllerPath, arguments: ["profile-status"], commandName: "profile-status"))
        }

        return combine(commandName: "import-config", results: results)
    }

    private func runUninstallSync(password: String) -> ProcessCommandResult {
        guard !password.isEmpty else {
            return ProcessCommandResult(
                ok: false,
                command: "uninstall",
                stdout: "",
                stderr: "Mac password is required.",
                exitCode: 2
            )
        }

        let sudoInput = "\(password)\n"
        let verifyPassword = runProcess(
            executable: "/usr/bin/sudo",
            arguments: ["-S", "-p", "", "-v"],
            commandName: "uninstall:verify-password",
            standardInput: sudoInput
        )
        guard verifyPassword.ok else {
            return ProcessCommandResult(
                ok: false,
                command: "uninstall",
                stdout: "",
                stderr: "Mac password verification failed.",
                exitCode: verifyPassword.exitCode
            )
        }

        var results: [ProcessCommandResult] = []
        if FileManager.default.isExecutableFile(atPath: rootControllerPath) {
            results.append(runProcess(
                executable: "/usr/bin/sudo",
                arguments: ["-S", "-p", "", rootControllerPath, "stop"],
                commandName: "uninstall:stop-root",
                standardInput: sudoInput
            ))
        } else {
            results.append(ProcessCommandResult(
                ok: true,
                command: "uninstall:stop-root",
                stdout: "root controller is not installed; skipped root stop\n",
                stderr: "",
                exitCode: 0
            ))
        }

        if FileManager.default.isExecutableFile(atPath: controllerPath) {
            results.append(runProcess(
                executable: controllerPath,
                arguments: ["uninstall"],
                commandName: "uninstall:macvpnctl"
            ))
        } else {
            results.append(ProcessCommandResult(
                ok: true,
                command: "uninstall:macvpnctl",
                stdout: "Proxy Gateway controller is not installed; skipped kit uninstall\n",
                stderr: "",
                exitCode: 0
            ))
        }

        results.append(runProcess(
            executable: "/bin/rm",
            arguments: ["-f", loginAgentPath],
            commandName: "uninstall:remove-login-agent"
        ))
        results.append(clearAppPreferences())
        results.append(removeUserPath(appPath, commandName: "uninstall:remove-app"))
        results.append(removeUserPath(desktopAppPath, commandName: "uninstall:remove-desktop-app"))
        results.append(removeUserPath(applicationSupportPath, commandName: "uninstall:remove-application-support"))
        results.append(removeUserPath(cachePath, commandName: "uninstall:remove-cache"))
        results.append(removeUserPath(preferencesPath, commandName: "uninstall:remove-preferences-file"))
        results.append(removeUserPath(savedStatePath, commandName: "uninstall:remove-saved-state"))
        results.append(ignoreFailure(runProcess(
            executable: "/usr/bin/sudo",
            arguments: ["-S", "-p", "", "/bin/launchctl", "bootout", "system", rootDaemonPath],
            commandName: "uninstall:root-bootout",
            standardInput: sudoInput
        ), fallbackStdout: "root daemon was already stopped or not loaded\n"))
        results.append(runProcess(
            executable: "/usr/bin/sudo",
            arguments: ["-S", "-p", "", "/bin/rm", "-f", rootDaemonPath, rootControllerPath, sudoersPath],
            commandName: "uninstall:remove-root-artifacts",
            standardInput: sudoInput
        ))

        return combine(commandName: "uninstall", results: results)
    }

    private func runAdministratorCommand(_ command: MacVpnCommand) -> ProcessCommandResult {
        let rootControllerResult = runRootController(command)
        if rootControllerResult.ok {
            return rootControllerResult
        }

        let shellCommand = "\(shellQuote(controllerPath)) \(command.rawValue)"
        let script = "do shell script \(appleScriptString(shellCommand)) with administrator privileges"
        return runProcess(executable: "/usr/bin/osascript", arguments: ["-e", script], commandName: command.rawValue)
    }

    private func runRootController(_ command: MacVpnCommand) -> ProcessCommandResult {
        guard FileManager.default.isExecutableFile(atPath: rootControllerPath) else {
            return ProcessCommandResult(
                ok: false,
                command: command.rawValue,
                stdout: "",
                stderr: "root controller is not installed",
                exitCode: 127
            )
        }

        let action: String
        switch command {
        case .startRoot:
            action = "start"
        case .stopRoot:
            action = "stop"
        default:
            action = command.rawValue
        }

        return runProcess(
            executable: "/usr/bin/sudo",
            arguments: ["-n", rootControllerPath, action],
            commandName: "\(command.rawValue):rootctl"
        )
    }

    private func runProcess(
        executable: String,
        arguments: [String],
        commandName: String,
        standardInput: String? = nil
    ) -> ProcessCommandResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe
        let stdinPipe = standardInput.map { _ in Pipe() }
        if let stdinPipe {
            process.standardInput = stdinPipe
        }

        do {
            try process.run()
            if let standardInput, let data = standardInput.data(using: .utf8), let stdinPipe {
                stdinPipe.fileHandleForWriting.write(data)
                stdinPipe.fileHandleForWriting.closeFile()
            }
            process.waitUntilExit()
        } catch {
            return ProcessCommandResult(
                ok: false,
                command: commandName,
                stdout: "",
                stderr: error.localizedDescription,
                exitCode: 127
            )
        }

        let stdout = String(data: stdoutPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        let stderr = String(data: stderrPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""

        return ProcessCommandResult(
            ok: process.terminationStatus == 0,
            command: commandName,
            stdout: stdout,
            stderr: stderr,
            exitCode: process.terminationStatus
        )
    }

    private func clearAppPreferences() -> ProcessCommandResult {
        let result = runProcess(
            executable: "/usr/bin/defaults",
            arguments: ["delete", "local.proxygateway.desktop"],
            commandName: "uninstall:clear-app-preferences"
        )
        guard !result.ok else {
            return result
        }

        return ProcessCommandResult(
            ok: true,
            command: result.command,
            stdout: "app preferences already clear\n",
            stderr: "",
            exitCode: 0
        )
    }

    private func removeUserPath(_ path: String, commandName: String) -> ProcessCommandResult {
        runProcess(executable: "/bin/rm", arguments: ["-rf", path], commandName: commandName)
    }

    private func ignoreFailure(_ result: ProcessCommandResult, fallbackStdout: String) -> ProcessCommandResult {
        guard !result.ok else {
            return result
        }

        return ProcessCommandResult(
            ok: true,
            command: result.command,
            stdout: fallbackStdout,
            stderr: "",
            exitCode: 0
        )
    }

    private func combine(commandName: String, results: [ProcessCommandResult]) -> ProcessCommandResult {
        let failed = results.first { !$0.ok }
        let stdout = results
            .map { result in
                let output = result.stdout.trimmingCharacters(in: .whitespacesAndNewlines)
                return output.isEmpty ? "" : "$ \(result.command)\n\(output)"
            }
            .filter { !$0.isEmpty }
            .joined(separator: "\n\n")
        let stderr = results
            .map { result in
                let output = result.stderr.trimmingCharacters(in: .whitespacesAndNewlines)
                return output.isEmpty ? "" : "$ \(result.command)\n\(output)"
            }
            .filter { !$0.isEmpty }
            .joined(separator: "\n\n")

        return ProcessCommandResult(
            ok: failed == nil,
            command: commandName,
            stdout: stdout,
            stderr: stderr,
            exitCode: failed?.exitCode ?? 0
        )
    }

    private func shellQuote(_ value: String) -> String {
        "'\(value.replacingOccurrences(of: "'", with: "'\\''"))'"
    }

    private func appleScriptString(_ value: String) -> String {
        let escaped = value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
        return "\"\(escaped)\""
    }
}
