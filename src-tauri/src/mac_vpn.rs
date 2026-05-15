use serde::Serialize;

#[cfg(target_os = "macos")]
use std::path::PathBuf;
#[cfg(target_os = "macos")]
use std::process::Command;

#[cfg(target_os = "macos")]
use crate::redaction::redact;

#[derive(Serialize)]
pub struct MacVpnCommandResult {
    ok: bool,
    platform: String,
    command: String,
    stdout: String,
    stderr: String,
}

fn blocked(command: &str, message: &str) -> MacVpnCommandResult {
    MacVpnCommandResult {
        ok: false,
        platform: std::env::consts::OS.to_string(),
        command: command.to_string(),
        stdout: String::new(),
        stderr: message.to_string(),
    }
}

#[cfg(target_os = "macos")]
fn command_result(
    command: &str,
    output: std::io::Result<std::process::Output>,
) -> MacVpnCommandResult {
    match output {
        Ok(output) => MacVpnCommandResult {
            ok: output.status.success(),
            platform: "macos".to_string(),
            command: command.to_string(),
            stdout: redact(&String::from_utf8_lossy(&output.stdout)),
            stderr: redact(&String::from_utf8_lossy(&output.stderr)),
        },
        Err(error) => MacVpnCommandResult {
            ok: false,
            platform: "macos".to_string(),
            command: command.to_string(),
            stdout: String::new(),
            stderr: error.to_string(),
        },
    }
}

#[cfg(target_os = "macos")]
fn controller_path() -> Result<PathBuf, String> {
    let home = std::env::var_os("HOME").ok_or_else(|| "HOME is unavailable".to_string())?;
    Ok(PathBuf::from(home)
        .join("ProxyGatewayMacVPN")
        .join("macvpnctl.sh"))
}

#[cfg(target_os = "macos")]
fn run_controller(command: &str) -> MacVpnCommandResult {
    let path = match controller_path() {
        Ok(path) => path,
        Err(error) => return blocked(command, &error),
    };
    if !path.is_file() {
        return blocked(
            command,
            "Mac VPN controller is missing at ~/ProxyGatewayMacVPN/macvpnctl.sh",
        );
    }
    command_result(command, Command::new(path).arg(command).output())
}

#[cfg(target_os = "macos")]
fn run_controller_as_admin(command: &str) -> MacVpnCommandResult {
    let path = match controller_path() {
        Ok(path) => path,
        Err(error) => return blocked(command, &error),
    };
    if !path.is_file() {
        return blocked(
            command,
            "Mac VPN controller is missing at ~/ProxyGatewayMacVPN/macvpnctl.sh",
        );
    }
    let shell_command = format!("{} {}", shell_quote(&path.to_string_lossy()), command);
    let apple_script = format!(
        "do shell script {} with administrator privileges",
        apple_script_string(&shell_command)
    );
    command_result(
        command,
        Command::new("osascript")
            .args(["-e", apple_script.as_str()])
            .output(),
    )
}

#[cfg(target_os = "macos")]
fn shell_quote(value: &str) -> String {
    format!("'{}'", value.replace('\'', "'\\''"))
}

#[cfg(target_os = "macos")]
fn apple_script_string(value: &str) -> String {
    let escaped = value.replace('\\', "\\\\").replace('"', "\\\"");
    format!("\"{escaped}\"")
}

fn require_confirm(
    command: &str,
    confirm: &str,
    expected: &str,
) -> Result<(), MacVpnCommandResult> {
    if confirm == expected {
        Ok(())
    } else {
        Err(blocked(command, "explicit confirmation token is required"))
    }
}

#[tauri::command]
pub fn mac_vpn_status() -> MacVpnCommandResult {
    #[cfg(target_os = "macos")]
    {
        return run_controller("status");
    }

    #[allow(unreachable_code)]
    blocked("status", "Mac VPN controls are only implemented for macOS")
}

#[tauri::command]
pub fn mac_vpn_test() -> MacVpnCommandResult {
    #[cfg(target_os = "macos")]
    {
        return run_controller("test");
    }

    #[allow(unreachable_code)]
    blocked("test", "Mac VPN controls are only implemented for macOS")
}

#[tauri::command]
pub fn mac_vpn_prepare_underlay(confirm: String) -> MacVpnCommandResult {
    let command = "prepare-independent-underlay";
    if let Err(result) = require_confirm(command, &confirm, "PREPARE_MAC_VPN_UNDERLAY") {
        return result;
    }

    #[cfg(target_os = "macos")]
    {
        return run_controller(command);
    }

    #[allow(unreachable_code)]
    blocked(command, "Mac VPN controls are only implemented for macOS")
}

#[tauri::command]
pub fn mac_vpn_start_root(confirm: String) -> MacVpnCommandResult {
    let command = "start-root";
    if let Err(result) = require_confirm(command, &confirm, "START_MAC_VPN_ROOT") {
        return result;
    }

    #[cfg(target_os = "macos")]
    {
        return run_controller_as_admin(command);
    }

    #[allow(unreachable_code)]
    blocked(command, "Mac VPN controls are only implemented for macOS")
}

#[tauri::command]
pub fn mac_vpn_stop_root(confirm: String) -> MacVpnCommandResult {
    let command = "stop-root";
    if let Err(result) = require_confirm(command, &confirm, "STOP_MAC_VPN_ROOT") {
        return result;
    }

    #[cfg(target_os = "macos")]
    {
        return run_controller_as_admin(command);
    }

    #[allow(unreachable_code)]
    blocked(command, "Mac VPN controls are only implemented for macOS")
}

#[tauri::command]
pub fn mac_vpn_restore_lan_gateway(confirm: String) -> MacVpnCommandResult {
    let command = "restore-lan-gateway";
    if let Err(result) = require_confirm(command, &confirm, "RESTORE_MAC_LAN_GATEWAY") {
        return result;
    }

    #[cfg(target_os = "macos")]
    {
        return run_controller(command);
    }

    #[allow(unreachable_code)]
    blocked(command, "Mac VPN controls are only implemented for macOS")
}
