from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Callable

try:
    from .runtime_launcher import stop_runtime
    from .session_store import SessionStore
except ImportError:
    from runtime_launcher import stop_runtime
    from session_store import SessionStore


SERVICE_NAME = "gateway-agent.service"


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def _config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured).expanduser() if configured else _home() / ".config"


def project_paths(store: SessionStore | None = None) -> dict[str, Path]:
    selected_store = store or SessionStore()
    home = _home()
    config_home = _config_home()
    return {
        "configDir": config_home / "proxy-gateway",
        "runtimeDir": selected_store.runtime_dir,
        "wrapper": home / ".local" / "bin" / "gateway-agent",
        "service": config_home / "systemd" / "user" / SERVICE_NAME,
    }


def _path_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "present": path.exists(),
    }


def lifecycle_status(store: SessionStore | None = None) -> dict[str, Any]:
    selected_store = store or SessionStore()
    paths = project_paths(selected_store)
    config = _path_status(paths["configDir"])
    config["profilePresent"] = (paths["configDir"] / "profile.json.enc").exists()
    runtime = _path_status(paths["runtimeDir"])
    service = _path_status(paths["service"])
    wrapper = _path_status(paths["wrapper"])
    installed = service["present"] or wrapper["present"]
    return {
        "ok": True,
        "state": "installed" if installed else "not_installed",
        "summary": "Linux v3 control layer is installed" if installed else "Linux v3 control layer is not installed",
        "contract": {
            "stop": "preserve-config",
            "uninstall": "purge-project-owned",
        },
        "config": config,
        "runtime": runtime,
        "service": service,
        "wrapper": wrapper,
        "commands": {
            "stop": str(paths["wrapper"]) + " stop",
            "uninstallDryRun": str(paths["wrapper"]) + " uninstall --dry-run",
            "uninstallApply": str(paths["wrapper"]) + " uninstall --apply",
        },
    }


def stop_control_layer(
    store: SessionStore | None = None,
    process_killer: Callable[[int], bool] | None = None,
) -> dict[str, Any]:
    selected_store = store or SessionStore()
    runtime_stop = stop_runtime(store=selected_store, process_killer=process_killer)
    removed_session = selected_store.remove_session()
    removed_token = selected_store.remove_token()
    status = lifecycle_status(selected_store)
    return {
        **status,
        "state": "stopped",
        "summary": "Linux v3 control layer stopped; local configuration preserved",
        "runtimeStop": runtime_stop,
        "removedSession": removed_session,
        "removedToken": removed_token,
    }


def _remove_path(path: Path) -> dict[str, Any]:
    existed = path.exists()
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed = True
        error = ""
    except FileNotFoundError:
        removed = False
        error = ""
    except OSError as exc:
        removed = False
        error = str(exc)
    return {
        "path": str(path),
        "existed": existed,
        "removed": removed,
        "error": error,
    }


def uninstall_control_layer(
    apply: bool = False,
    store: SessionStore | None = None,
    process_killer: Callable[[int], bool] | None = None,
) -> dict[str, Any]:
    selected_store = store or SessionStore()
    paths = project_paths(selected_store)
    planned = [paths["service"], paths["wrapper"], paths["configDir"], paths["runtimeDir"]]
    if not apply:
        return {
            **lifecycle_status(selected_store),
            "applied": False,
            "state": "dry_run",
            "summary": "Dry-run only; no Linux v3 project-owned files were removed",
            "remove": [str(path) for path in planned],
        }

    stopped = stop_control_layer(selected_store, process_killer=process_killer)
    removed = [_remove_path(path) for path in planned]
    ok = all(not item["error"] for item in removed)
    return {
        **lifecycle_status(selected_store),
        "ok": ok,
        "applied": True,
        "state": "uninstalled" if ok else "partial",
        "summary": "Linux v3 project-owned control files removed" if ok else "Linux v3 uninstall completed with errors",
        "stop": stopped,
        "removed": removed,
    }
