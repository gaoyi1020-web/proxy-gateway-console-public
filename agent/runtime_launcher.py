from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
from ipaddress import ip_address
from pathlib import Path
from typing import Any

try:
    from .port_registry import utc_now_iso
    from .session_store import SessionStore
except ImportError:
    from port_registry import utc_now_iso
    from session_store import SessionStore


V1_FALLBACK_SERVICES = (
    "proxy-failover.service",
    "iphone-lan-proxy.service",
    "hotspot-split-proxy.service",
    "hotspot-split-dns.service",
)
RUNTIME_CHILDREN_FILE = "runtime-children.json"
V1_FAILOVER_HOST = "127.0.0.1"
V1_FAILOVER_PORT = 18180


def build_runtime_plan(session: dict[str, Any] | None, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    listeners = session.get("listeners", {}) if session else {}
    routes = profile.get("routes", {}) if profile else {}
    children = []
    errors = []
    for listener_id, listener in listeners.items():
        if not _valid_listener(listener):
            errors.append(f"invalid listener: {listener_id}")
            continue
        children.append(
            {
                "id": listener_id,
                "host": listener.get("host", ""),
                "port": listener.get("port", 0),
                "action": "planned",
            }
        )
    return {
        "ok": not errors,
        "mode": "dry-run",
        "summary": "runtime child services are planned only; v1 fallback remains active" if not errors else "runtime plan has invalid listeners",
        "children": children,
        "errors": errors,
        "routes": sorted(routes),
        "profileLoaded": profile is not None,
        "fallback": {
            "enabled": True,
            "services": list(V1_FALLBACK_SERVICES),
        },
    }


def start_runtime(
    plan: dict[str, Any],
    dry_run: bool = True,
    allow_child: bool = False,
    store: SessionStore | None = None,
    process_factory=None,
) -> dict[str, Any]:
    if not plan.get("ok", False):
        return {
            "ok": False,
            "state": "blocked",
            "summary": "runtime launch blocked by invalid plan",
            "errors": plan.get("errors", []),
        }
    if dry_run:
        return {
            "ok": True,
            "state": "planned",
            "summary": "dry-run runtime launch completed without starting child services",
            "children": plan.get("children", []),
        }
    if not allow_child:
        return {
            "ok": False,
            "state": "blocked",
            "summary": "explicit child start flag is required",
            "fallback": plan.get("fallback", {}),
        }
    if not plan.get("profileLoaded"):
        return {
            "ok": False,
            "state": "blocked",
            "summary": "encrypted profile must be loaded before v2 child services start",
            "fallback": plan.get("fallback", {}),
        }
    lan_child = _child_by_id(plan, "lanProxy")
    if not lan_child:
        return {
            "ok": False,
            "state": "blocked",
            "summary": "lanProxy listener is required before v2 child services start",
            "fallback": plan.get("fallback", {}),
        }
    active_store = store or SessionStore()
    active_store.ensure()
    stop_runtime(store=active_store)
    command = _lan_proxy_command(lan_child)
    spawn = process_factory or _spawn_process
    try:
        process = spawn(command)
    except OSError as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": "v2 LAN proxy child failed to start; v1 fallback remains active",
            "error": {
                "type": type(error).__name__,
                "errno": getattr(error, "errno", None),
                "message": str(error),
            },
            "fallback": plan.get("fallback", {}),
        }
    child_state = {
        "version": 2,
        "startedAt": utc_now_iso(),
        "children": [
            {
                "id": "lanProxy",
                "pid": int(process.pid),
                "host": lan_child["host"],
                "port": lan_child["port"],
                "upstream": f"{V1_FAILOVER_HOST}:{V1_FAILOVER_PORT}",
                "command": _redacted_command(command),
            }
        ],
    }
    _write_child_state(active_store, child_state)
    return {
        "ok": True,
        "state": "running",
        "summary": "v2 LAN proxy child started; v1 fallback remains active",
        "children": child_state["children"],
        "fallback": plan.get("fallback", {}),
    }


def _valid_listener(listener: dict[str, Any]) -> bool:
    host = listener.get("host")
    port = listener.get("port")
    return isinstance(host, str) and bool(host) and isinstance(port, int) and 0 < port <= 65535


def stop_runtime(store: SessionStore | None = None, process_killer=None) -> dict[str, Any]:
    active_store = store or SessionStore()
    active_store.ensure()
    state_path = _child_state_path(active_store)
    state = active_store.read_json(state_path) or {}
    children = state.get("children") if isinstance(state.get("children"), list) else []
    killer = process_killer or _terminate_pid
    stopped = 0
    errors = []
    for child in children:
        pid = child.get("pid")
        if not isinstance(pid, int):
            continue
        try:
            if killer(pid):
                stopped += 1
        except OSError as error:
            errors.append({"pid": pid, "type": type(error).__name__, "message": str(error)})
    active_store._unlink(state_path)
    return {
        "ok": not errors,
        "state": "stopped",
        "summary": "v2 child services stopped" if stopped else "no v2 child services were running",
        "stoppedChildProcesses": stopped,
        "errors": errors,
    }


def _child_by_id(plan: dict[str, Any], child_id: str) -> dict[str, Any] | None:
    for child in plan.get("children", []):
        if child.get("id") == child_id:
            return child
    return None


def _child_state_path(store: SessionStore) -> Path:
    return store.state_dir / RUNTIME_CHILDREN_FILE


def runtime_status(store: SessionStore | None = None, process_checker=None) -> dict[str, Any]:
    active_store = store or SessionStore()
    active_store.ensure()
    state = active_store.read_json(_child_state_path(active_store)) or {}
    children = state.get("children") if isinstance(state.get("children"), list) else []
    checker = process_checker or _pid_is_running
    active_children = []
    stale_children = []
    for child in children:
        pid = child.get("pid")
        if isinstance(pid, int) and checker(pid):
            active_children.append(child)
        else:
            stale_children.append(child)
    if active_children:
        runtime_state = "running"
    elif stale_children:
        runtime_state = "stale"
    else:
        runtime_state = "stopped"
    return {
        "ok": runtime_state != "stale",
        "state": runtime_state,
        "children": active_children,
        "staleChildren": stale_children,
        "statePath": str(_child_state_path(active_store)),
    }


def _write_child_state(store: SessionStore, payload: dict[str, Any]) -> None:
    store.write_json(_child_state_path(store), payload)


def _lan_proxy_command(listener: dict[str, Any]) -> list[str]:
    script = Path(__file__).with_name("lan_proxy_child.py")
    return [
        sys.executable,
        str(script),
        "--listen-host",
        str(listener["host"]),
        "--listen-port",
        str(listener["port"]),
        "--upstream-host",
        V1_FAILOVER_HOST,
        "--upstream-port",
        str(V1_FAILOVER_PORT),
    ]


def _redacted_command(command: list[str]) -> list[str]:
    return list(command)


def _spawn_process(command: list[str]):
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _terminate_pid(pid: int) -> bool:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except OSError:
        os.kill(pid, signal.SIGTERM)
    return True


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def phone_setup_from_session(session: dict[str, Any] | None, listener_checker=None) -> dict[str, Any]:
    listener = (session or {}).get("listeners", {}).get("lanProxy")
    if not listener:
        return {
            "setupVersion": 2,
            "enabled": False,
            "state": "lan_listener_off",
            "observedClients": [],
            "summary": "LAN listener is off; keep using v1 iPhone LAN proxy if needed",
        }
    if not _valid_listener(listener):
        return {
            "setupVersion": 2,
            "enabled": False,
            "state": "lan_listener_invalid",
            "observedClients": [],
            "summary": "LAN listener settings are invalid; keep using v1 iPhone LAN proxy if needed",
        }
    host = listener.get("host")
    port = listener.get("port")
    setting = f"{host}:{port}"
    if _is_loopback_host(str(host)):
        return {
            "setupVersion": 2,
            "enabled": False,
            "state": "lan_listener_local_only",
            "setting": setting,
            "authentication": False,
            "observedClients": [],
            "summary": "LAN listener is bound to loopback and cannot be used by a phone; keep using v1 iPhone LAN proxy if needed",
        }
    if _is_unspecified_host(str(host)):
        return {
            "setupVersion": 2,
            "enabled": False,
            "state": "lan_listener_unspecified",
            "setting": setting,
            "authentication": False,
            "observedClients": [],
            "summary": "LAN listener must publish a concrete LAN address before phone setup is available",
        }
    checker = listener_checker or _tcp_listener_open
    if not checker(str(host), int(port)):
        return {
            "setupVersion": 2,
            "enabled": False,
            "state": "lan_listener_stale",
            "setting": setting,
            "authentication": False,
            "observedClients": [],
            "summary": "LAN listener is recorded in the session but is not currently listening; keep using v1 iPhone LAN proxy if needed",
        }
    return {
        "setupVersion": 2,
        "enabled": True,
        "state": "lan_listener_on",
        "setting": setting,
        "authentication": False,
        "manualProxy": {
            "server": host,
            "port": port,
            "authentication": False,
        },
        "pac": {
            "available": True,
            "filename": "proxy-gateway-v2.pac",
            "mimeType": "application/x-ns-proxy-autoconfig",
            "content": _pac_content(str(host), int(port)),
        },
        "routePolicy": {
            "summary": "CN/private direct, foreign proxy is enforced by the LAN proxy runtime",
            "split": "cn-private-direct-foreign-proxy",
        },
        "observedClients": [],
        "summary": "Use this session-specific LAN proxy setting for the test client only",
    }


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _is_unspecified_host(host: str) -> bool:
    try:
        return ip_address(host).is_unspecified
    except ValueError:
        return False


def _tcp_listener_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _pac_content(proxy_host: str, proxy_port: int) -> str:
    proxy = f"PROXY {proxy_host}:{proxy_port}; DIRECT"
    return (
        "function FindProxyForURL(url, host) {\n"
        "  if (isPlainHostName(host) || dnsDomainIs(host, \".local\")) { return \"DIRECT\"; }\n"
        "  if (shExpMatch(host, \"10.*\") || shExpMatch(host, \"192.168.*\") || shExpMatch(host, \"172.16.*\") || shExpMatch(host, \"172.17.*\") || shExpMatch(host, \"172.18.*\") || shExpMatch(host, \"172.19.*\") || shExpMatch(host, \"172.2?.*\") || shExpMatch(host, \"172.30.*\") || shExpMatch(host, \"172.31.*\")) { return \"DIRECT\"; }\n"
        f"  return \"{proxy}\";\n"
        "}\n"
    )
