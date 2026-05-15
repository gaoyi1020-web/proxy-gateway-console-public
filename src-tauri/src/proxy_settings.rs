use serde::Serialize;
#[cfg(any(target_os = "macos", target_os = "windows"))]
use std::process::Command;

#[cfg(any(target_os = "macos", target_os = "windows"))]
use crate::redaction::redact;

#[derive(Serialize)]
pub struct ProxyCommandResult {
    ok: bool,
    platform: String,
    stdout: String,
    stderr: String,
}

#[cfg(any(target_os = "macos", target_os = "windows"))]
fn command_result(
    platform: &str,
    output: std::io::Result<std::process::Output>,
) -> ProxyCommandResult {
    match output {
        Ok(output) => ProxyCommandResult {
            ok: output.status.success(),
            platform: platform.to_string(),
            stdout: redact(&String::from_utf8_lossy(&output.stdout)),
            stderr: redact(&String::from_utf8_lossy(&output.stderr)),
        },
        Err(error) => ProxyCommandResult {
            ok: false,
            platform: platform.to_string(),
            stdout: String::new(),
            stderr: error.to_string(),
        },
    }
}

fn blocked(message: &str) -> ProxyCommandResult {
    ProxyCommandResult {
        ok: false,
        platform: std::env::consts::OS.to_string(),
        stdout: String::new(),
        stderr: message.to_string(),
    }
}

#[tauri::command]
pub fn system_proxy_status() -> ProxyCommandResult {
    #[cfg(target_os = "macos")]
    {
        return command_result(
            "macos",
            Command::new("networksetup")
                .arg("-listallnetworkservices")
                .output(),
        );
    }

    #[cfg(target_os = "windows")]
    {
        return command_result(
            "windows",
            Command::new("powershell")
                .args([
                    "-NoProfile",
                    "-Command",
                    "Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' | Select-Object ProxyEnable,ProxyServer | ConvertTo-Json -Compress",
                ])
                .output(),
        );
    }

    #[allow(unreachable_code)]
    blocked("system proxy controls are only implemented for macOS and Windows in this slice")
}

#[tauri::command]
pub fn system_proxy_apply(host: String, port: u16, confirm: String) -> ProxyCommandResult {
    if confirm != "APPLY_SYSTEM_PROXY" {
        return blocked("explicit confirmation token is required");
    }
    if host != "127.0.0.1" {
        return blocked("desktop test app only applies loopback proxy settings");
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    let _ = port;

    #[cfg(target_os = "macos")]
    {
        let port = port.to_string();
        let web = Command::new("networksetup")
            .args(["-setwebproxy", "Wi-Fi", &host, &port])
            .output();
        let web_result = command_result("macos", web);
        if !web_result.ok {
            return web_result;
        }
        return command_result(
            "macos",
            Command::new("networksetup")
                .args(["-setsecurewebproxy", "Wi-Fi", &host, &port])
                .output(),
        );
    }

    #[cfg(target_os = "windows")]
    {
        let proxy = format!("{}:{}", host, port);
        return command_result(
            "windows",
            Command::new("powershell")
                .args([
                    "-NoProfile",
                    "-Command",
                    &format!(
                        "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -Name ProxyEnable -Value 1; Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -Name ProxyServer -Value '{}'",
                        proxy
                    ),
                ])
                .output(),
        );
    }

    #[allow(unreachable_code)]
    blocked("system proxy controls are only implemented for macOS and Windows in this slice")
}

#[tauri::command]
pub fn system_proxy_clear(confirm: String) -> ProxyCommandResult {
    if confirm != "CLEAR_SYSTEM_PROXY" {
        return blocked("explicit confirmation token is required");
    }

    #[cfg(target_os = "macos")]
    {
        let web = Command::new("networksetup")
            .args(["-setwebproxystate", "Wi-Fi", "off"])
            .output();
        let web_result = command_result("macos", web);
        if !web_result.ok {
            return web_result;
        }
        return command_result(
            "macos",
            Command::new("networksetup")
                .args(["-setsecurewebproxystate", "Wi-Fi", "off"])
                .output(),
        );
    }

    #[cfg(target_os = "windows")]
    {
        return command_result(
            "windows",
            Command::new("powershell")
                .args([
                    "-NoProfile",
                    "-Command",
                    "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -Name ProxyEnable -Value 0",
                ])
                .output(),
        );
    }

    #[allow(unreachable_code)]
    blocked("system proxy controls are only implemented for macOS and Windows in this slice")
}
