use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

#[tauri::command]
pub fn linux_desktop_package_status() -> Value {
    let home = std::env::var("HOME").unwrap_or_default();
    let root = PathBuf::from(&home);
    let install_root = root.join(".local/share/proxy-gateway-desktop/self-use");
    let bin_dir = root.join(".local/bin");
    let launcher = bin_dir.join("proxy-gateway-desktop");
    let release_binary = install_root.join("bin/proxy-gateway-test");
    let sidecar = install_root.join("bin/gateway-agent");
    let desktop_entry = root.join(".local/share/applications/proxy-gateway-desktop.desktop");
    let desktop_copy = root.join("Desktop/Proxy Gateway Desktop.desktop");
    let icon = root.join(".local/share/icons/hicolor/128x128/apps/proxy-gateway-desktop.png");
    let legacy_desktop_entries = vec![
        root.join(".local/share/applications/proxy-app.desktop"),
        root.join(".local/share/applications/proxy-dashboard.desktop"),
    ];
    let legacy_present: Vec<String> = legacy_desktop_entries
        .iter()
        .filter(|entry| present(entry))
        .map(path_string)
        .collect();
    let launcher_backups = launcher_backups(&bin_dir);
    let desktop_entry_text = fs::read_to_string(&desktop_entry).unwrap_or_default();
    let mode = launcher_mode(&launcher);
    let checks = json!({
        "launcher": executable(&launcher),
        "releaseBinary": executable(&release_binary),
        "sidecar": executable(&sidecar),
        "desktopEntry": present(&desktop_entry),
        "singleDesktopEntry": legacy_present.is_empty() && !present(&desktop_copy),
        "icon": present(&icon),
        "desktopEntryIcon": desktop_entry_text.lines().any(|line| line == "Icon=proxy-gateway-desktop"),
        "launcherBackupsArchived": launcher_backups.is_empty(),
    });
    let installed = checks["launcher"].as_bool().unwrap_or(false)
        && checks["releaseBinary"].as_bool().unwrap_or(false)
        && checks["sidecar"].as_bool().unwrap_or(false)
        && checks["desktopEntry"].as_bool().unwrap_or(false);
    let ok = installed
        && mode == "release"
        && checks["singleDesktopEntry"].as_bool().unwrap_or(false)
        && checks["icon"].as_bool().unwrap_or(false)
        && checks["desktopEntryIcon"].as_bool().unwrap_or(false)
        && checks["launcherBackupsArchived"].as_bool().unwrap_or(false);
    let summary = if ok {
        "Linux desktop self-use package is installed"
    } else if mode == "dev" {
        "launcher still uses a dev command"
    } else if installed && !checks["singleDesktopEntry"].as_bool().unwrap_or(false) {
        "Linux desktop package has duplicate launcher entries"
    } else if installed && !checks["launcherBackupsArchived"].as_bool().unwrap_or(false) {
        "Linux desktop package has launcher backups outside the archive"
    } else if installed
        && (!checks["icon"].as_bool().unwrap_or(false)
            || !checks["desktopEntryIcon"].as_bool().unwrap_or(false))
    {
        "Linux desktop package icon is incomplete"
    } else {
        "Linux desktop package is incomplete"
    };

    json!({
        "ok": ok,
        "state": if installed { "installed" } else { "missing" },
        "launcherMode": mode,
        "summary": summary,
        "installRoot": path_string(&install_root),
        "launcher": path_string(&launcher),
        "releaseBinary": path_string(&release_binary),
        "sidecar": path_string(&sidecar),
        "desktopEntry": path_string(&desktop_entry),
        "desktopCopy": path_string(&desktop_copy),
        "icon": path_string(&icon),
        "legacyDesktopEntries": legacy_desktop_entries.iter().map(path_string).collect::<Vec<_>>(),
        "legacyPresent": legacy_present,
        "launcherBackups": launcher_backups,
        "checks": checks
    })
}

fn path_string(path: &PathBuf) -> String {
    path.to_string_lossy().to_string()
}

fn present(path: &Path) -> bool {
    fs::metadata(path)
        .map(|metadata| metadata.is_file() || metadata.is_dir())
        .unwrap_or(false)
}

fn executable(path: &Path) -> bool {
    fs::metadata(path)
        .map(|metadata| metadata.is_file() && executable_mode(&metadata))
        .unwrap_or(false)
}

#[cfg(unix)]
fn executable_mode(metadata: &fs::Metadata) -> bool {
    use std::os::unix::fs::PermissionsExt;
    metadata.permissions().mode() & 0o111 != 0
}

#[cfg(not(unix))]
fn executable_mode(metadata: &fs::Metadata) -> bool {
    metadata.is_file()
}

fn launcher_mode(path: &Path) -> String {
    let text = fs::read_to_string(path).unwrap_or_default();
    if text.contains("desktop:dev")
        || text.contains("tauri dev")
        || text.contains("npm run desktop:dev")
        || text.contains("vite --host 127.0.0.1")
    {
        "dev".to_string()
    } else if text.contains("proxy-gateway-test") {
        "release".to_string()
    } else if text.is_empty() {
        "missing".to_string()
    } else {
        "unknown".to_string()
    }
}

fn launcher_backups(bin_dir: &Path) -> Vec<String> {
    fs::read_dir(bin_dir)
        .map(|entries| {
            entries
                .flatten()
                .filter_map(|entry| {
                    let name = entry.file_name();
                    let name = name.to_string_lossy();
                    if name.starts_with("proxy-gateway-desktop.bak.") {
                        Some(entry.path().to_string_lossy().to_string())
                    } else {
                        None
                    }
                })
                .collect()
        })
        .unwrap_or_default()
}
