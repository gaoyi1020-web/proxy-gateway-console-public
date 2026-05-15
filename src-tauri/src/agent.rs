use base64::{engine::general_purpose, Engine as _};
use serde::Serialize;
use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;

use crate::redaction::redact;

#[derive(Serialize)]
pub struct CommandResult {
    ok: bool,
    stdout: String,
    stderr: String,
}

async fn run_agent(app: AppHandle, args: Vec<String>) -> Result<CommandResult, String> {
    let output = app
        .shell()
        .sidecar("binaries/gateway-agent")
        .map_err(|error| error.to_string())?
        .env("GATEWAY_AGENT_V2", "1")
        .args(args)
        .output()
        .await
        .map_err(|error| error.to_string())?;

    Ok(CommandResult {
        ok: output.status.success(),
        stdout: redact(&String::from_utf8_lossy(&output.stdout)),
        stderr: redact(&String::from_utf8_lossy(&output.stderr)),
    })
}

#[tauri::command]
pub async fn agent_status(app: AppHandle) -> Result<CommandResult, String> {
    run_agent(app, vec!["status".to_string()]).await
}

#[tauri::command]
pub async fn agent_self_check(app: AppHandle) -> Result<CommandResult, String> {
    run_agent(app, vec!["self-check".to_string()]).await
}

#[tauri::command]
pub async fn agent_uninstall_plan(app: AppHandle) -> Result<CommandResult, String> {
    run_agent(
        app,
        vec![
            "uninstall".to_string(),
            "--dry-run".to_string(),
        ],
    )
    .await
}

#[tauri::command]
pub async fn agent_start(app: AppHandle, lan_host: String) -> Result<CommandResult, String> {
    if lan_host != "127.0.0.1" {
        return Err("desktop test app only allows loopback LAN host in this slice".to_string());
    }
    run_agent(
        app,
        vec![
            "start".to_string(),
            "--lan-host".to_string(),
            "127.0.0.1".to_string(),
        ],
    )
    .await
}

#[tauri::command]
pub async fn agent_stop(app: AppHandle) -> Result<CommandResult, String> {
    run_agent(app, vec!["stop".to_string()]).await
}

#[tauri::command]
pub async fn agent_runtime_start(
    app: AppHandle,
    profile_path: String,
    passphrase: String,
) -> Result<CommandResult, String> {
    if profile_path.trim().is_empty() || passphrase.is_empty() {
        return Err("profile path and passphrase are required".to_string());
    }
    let passphrase_file = write_passphrase_file(&passphrase)?;
    let result = run_agent(
        app,
        vec![
            "runtime-start".to_string(),
            "--profile-path".to_string(),
            profile_path,
            "--passphrase-file".to_string(),
            passphrase_file.to_string_lossy().to_string(),
            "--allow-child".to_string(),
        ],
    )
    .await;
    let _ = fs::remove_file(passphrase_file);
    result
}

#[tauri::command]
pub async fn agent_runtime_stop(app: AppHandle) -> Result<CommandResult, String> {
    run_agent(app, vec!["stop".to_string()]).await
}

#[tauri::command]
pub async fn agent_profile_import(
    app: AppHandle,
    file_name: String,
    content_base64: String,
) -> Result<Value, String> {
    let safe_name = file_name.trim();
    if safe_name != "profile.json.enc" && !safe_name.ends_with(".json.enc") {
        return Ok(json!({
            "ok": false,
            "state": "blocked",
            "summary": "Linux import only accepts profile.json.enc"
        }));
    }

    let bytes = general_purpose::STANDARD
        .decode(content_base64.trim())
        .map_err(|error| error.to_string())?;
    if bytes.is_empty() || bytes.len() > 1024 * 1024 {
        return Ok(json!({
            "ok": false,
            "state": "blocked",
            "summary": "encrypted profile size is invalid"
        }));
    }
    validate_profile_envelope(&bytes)?;

    let temp_profile = temp_profile_path();
    fs::write(&temp_profile, bytes).map_err(|error| error.to_string())?;
    let result = run_agent(
        app,
        vec![
            "profile-import".to_string(),
            "--from".to_string(),
            temp_profile.to_string_lossy().to_string(),
        ],
    )
    .await;
    let _ = fs::remove_file(&temp_profile);

    let command = result?;
    match serde_json::from_str::<Value>(&command.stdout) {
        Ok(value) => Ok(redact_import_value(value)),
        Err(_) => Ok(json!({
            "ok": false,
            "state": "blocked",
            "summary": if command.stderr.is_empty() { "profile import failed" } else { command.stderr.as_str() }
        })),
    }
}

fn write_passphrase_file(passphrase: &str) -> Result<PathBuf, String> {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "proxy-gateway-passphrase-{}-{nanos}.txt",
        std::process::id()
    ));
    fs::write(&path, passphrase).map_err(|error| error.to_string())?;
    Ok(path)
}

fn temp_profile_path() -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or_default();
    std::env::temp_dir().join(format!(
        "proxy-gateway-profile-{}-{nanos}.json.enc",
        std::process::id()
    ))
}

fn validate_profile_envelope(bytes: &[u8]) -> Result<(), String> {
    let envelope: Value = serde_json::from_slice(bytes).map_err(|_| "encrypted profile is not valid JSON".to_string())?;
    let expected = [
        ("product", json!("PROXY_GATEWAY_PROFILE")),
        ("version", json!(1)),
        ("algorithm", json!("AES-256-GCM")),
        ("kdf", json!("PBKDF2-HMAC-SHA256")),
        ("iterations", json!(390000)),
    ];
    for (key, value) in expected {
        if envelope.get(key) != Some(&value) {
            return Err(format!("encrypted profile {key} mismatch"));
        }
    }
    for key in ["salt", "nonce", "ciphertext"] {
        if !envelope.get(key).is_some_and(Value::is_string) {
            return Err("encrypted profile envelope is incomplete".to_string());
        }
    }
    Ok(())
}

fn redact_import_value(value: Value) -> Value {
    json!({
        "ok": value.get("ok").and_then(Value::as_bool).unwrap_or(false),
        "state": value.get("state").and_then(Value::as_str).unwrap_or("unknown"),
        "summary": value.get("summary").and_then(Value::as_str).unwrap_or(""),
        "profileSource": {
            "mode": value
                .get("profileSource")
                .and_then(|source| source.get("mode"))
                .and_then(Value::as_str)
                .unwrap_or("local"),
            "path": value
                .get("profileSource")
                .and_then(|source| source.get("path"))
                .and_then(Value::as_str)
                .unwrap_or("")
        }
    })
}
