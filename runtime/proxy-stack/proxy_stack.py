#!/usr/bin/env python3
"""Unified controller for the local proxy and hotspot split stack."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


HOME = Path.home()
BIN = HOME / ".local" / "bin"
SHARE = HOME / ".local" / "share"
STATE_DIR = Path(os.environ.get("PROXY_STACK_STATE_DIR", str(SHARE / "proxy-stack"))).expanduser()
GUI_GUARD_MARKER = STATE_DIR / "hotspot-gui-guard.json"
NETWORK_EVENTS_FILE = STATE_DIR / "network-events.json"
UPSTREAM_POLICY_FILE = STATE_DIR / "upstream-policy.json"
SYS_CLASS_NET = Path(os.environ.get("PROXY_STACK_SYS_CLASS_NET", "/sys/class/net"))
PHONE_TETHER_DRIVERS = {"ipheth", "rndis_host", "cdc_ether", "cdc_ncm"}
PHONE_TETHER_DEMOTE_POLICY = {
    "ipv4.never-default": "yes",
    "ipv6.never-default": "yes",
    "ipv4.route-metric": "9000",
    "ipv6.route-metric": "9000",
}
PHONE_TETHER_PROMOTE_POLICY = {
    "ipv4.never-default": "no",
    "ipv6.never-default": "no",
    "ipv4.route-metric": "50",
    "ipv6.route-metric": "50",
}
PHONE_TETHER_CHOICES = [
    {"id": "keep-current", "label": "Keep current upstream", "policy": "demote_phone"},
    {"id": "use-phone-once", "label": "Use phone port once", "policy": "explicit_phone_port"},
    {"id": "ignore-once", "label": "Ignore once", "policy": "leave_current"},
    {"id": "always-keep-current", "label": "Always keep current upstream", "policy": "save_demote_phone"},
    {"id": "always-use-phone", "label": "Always use phone port", "policy": "save_explicit_phone_port"},
]
PHONE_EGRESS_PORT = 18190
PHONE_EGRESS_TABLE = 18190
PHONE_EGRESS_PRIORITY = 18190
IPHONE_LAN_PROXY_PORT = 18181
DASHBOARD_PORT = 4077
IPHONE_LAN_PROXY_TARGET = "CN/private direct, foreign -> 127.0.0.1:18122"
LAN_GATEWAY_TABLE = "lan_gateway"
LAN_GATEWAY_NFT_FILE = STATE_DIR / "lan_gateway.nft"
LAN_GATEWAY_STATE_FILE = STATE_DIR / "lan_gateway_state.json"
LAN_GATEWAY_RESERVED_TCP_PORTS = (22, 4077, 18180, 18181, 12345, 1053)

USER_SERVICES = [
    "secondary-proxy-client.service",
    "secondary-http-proxy.service",
    "proxy-failover.service",
    "iphone-lan-proxy.service",
    "hotspot-split-proxy.service",
    "hotspot-split-dns.service",
]

SYSTEM_SERVICES = [
    "shadowsocks-libev.service",
    "privoxy.service",
    "hotspot-split-nft.service",
]

SERVICE_PORTS = {
    "secondary-proxy-client.service": [11880],
    "secondary-http-proxy.service": [18122],
    "proxy-failover.service": [18180],
    "iphone-lan-proxy.service": [18181],
    "hotspot-split-proxy.service": [12345],
    "hotspot-split-dns.service": [1053],
    "shadowsocks-libev.service": [8388],
    "privoxy.service": [8118],
}

PORTS = [
    {"id": "old-socks", "label": "Old SOCKS", "host": "127.0.0.1", "port": 1080, "scope": "local"},
    {"id": "old-http", "label": "Old HTTP", "host": "127.0.0.1", "port": 8118, "scope": "local"},
    {"id": "new-socks", "label": "New SOCKS", "host": "127.0.0.1", "port": 11880, "scope": "local"},
    {"id": "new-http", "label": "New HTTP", "host": "127.0.0.1", "port": 18122, "scope": "hotspot"},
    {"id": "failover", "label": "Failover HTTP", "host": "127.0.0.1", "port": 18180, "scope": "local"},
    {"id": "iphone-lan", "label": "iPhone LAN HTTP", "host": "LAN", "port": 18181, "scope": "lan"},
    {"id": "split-dns", "label": "Split DNS", "host": "127.0.0.1", "port": 1053, "scope": "hotspot"},
    {"id": "split-tcp", "label": "Split TCP", "host": "127.0.0.1", "port": 12345, "scope": "hotspot"},
]

LOGS = {
    "split_dns": SHARE / "hotspot-split-gateway" / "dns.log",
    "split_proxy": SHARE / "hotspot-split-gateway" / "proxy.log",
    "failover": SHARE / "proxy-failover" / "proxy-failover.log",
    "new_http": SHARE / "hotspot-proxy" / "hotspot-proxy.log",
    "old_ss": SHARE / "proxy-app" / "ss-local.log",
    "old_privoxy": SHARE / "proxy-app" / "privoxy.log",
    "iphone_lan": STATE_DIR / "iphone-lan-proxy.log",
}

DEFAULT_HOTSPOT_CONNECTION = "GY-Hotspot"
HOTSPOT_GUI_GUARD_PERMISSION = "user:root"


def run(args: list[str], timeout: int = 20, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "elapsed_ms": int((time.time() - started) * 1000),
            "cmd": args,
        }
    except Exception as error:  # noqa: BLE001 - surfaced as status.
        return {
            "ok": False,
            "code": 124,
            "stdout": "",
            "stderr": str(error),
            "elapsed_ms": int((time.time() - started) * 1000),
            "cmd": args,
        }


def service_state(name: str, user: bool) -> str:
    status = service_status(name, user)
    return status["state"]


def service_status(name: str, user: bool) -> dict[str, Any]:
    args = ["systemctl"]
    if user:
        args.append("--user")
    args += ["is-active", name]
    result = run(args, timeout=5)
    ports = SERVICE_PORTS.get(name, [])
    port_fallback = bool(ports) and any(port_listening(port) for port in ports)
    if result["ok"]:
        systemd_state = result["stdout"] or "active"
        return {
            "state": systemd_state,
            "systemd_state": systemd_state,
            "port_fallback": False,
            "ports": ports,
        }
    systemd_state = result["stdout"] or "inactive"
    if port_fallback:
        return {
            "state": "active",
            "systemd_state": systemd_state,
            "port_fallback": True,
            "ports": ports,
        }
    if name == "hotspot-split-nft.service":
        state = nft_state()["state"]
        return {
            "state": "active" if state == "loaded" else state,
            "systemd_state": systemd_state,
            "port_fallback": False,
            "ports": ports,
        }
    return {
        "state": systemd_state,
        "systemd_state": systemd_state,
        "port_fallback": False,
        "ports": ports,
    }


def service_enabled(name: str, user: bool) -> str:
    args = ["systemctl"]
    if user:
        args.append("--user")
    args += ["is-enabled", name]
    result = run(args, timeout=5)
    if result["ok"]:
        return result["stdout"] or "enabled"
    if user:
        wants = HOME / ".config" / "systemd" / "user" / "default.target.wants" / name
        return "enabled" if wants.exists() else "disabled"
    if name == "hotspot-split-nft.service":
        return "manual"
    return result["stdout"] or "unknown"


def listening_ports() -> set[int]:
    result = run(["ss", "-ltnup"], timeout=5)
    ports: set[int] = set()
    if not result["ok"]:
        return ports
    for token in result["stdout"].replace("\n", " ").split():
        if ":" not in token:
            continue
        maybe_port = token.rsplit(":", 1)[-1]
        if maybe_port.isdigit():
            ports.add(int(maybe_port))
    return ports


def port_listening(port: int) -> bool:
    return port in listening_ports()


def parse_kv(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def first_line(text: str) -> str:
    for line in text.splitlines():
        value = line.strip()
        if value:
            return value
    return ""


def parse_route_interface(text: str) -> str:
    parts = text.split()
    for index, part in enumerate(parts[:-1]):
        if part == "dev":
            return parts[index + 1]
    return ""


def parse_route_source(text: str) -> str:
    parts = text.split()
    for index, part in enumerate(parts[:-1]):
        if part == "src":
            return parts[index + 1]
    return ""


def parse_route_gateway(text: str) -> str:
    parts = text.split()
    for index, part in enumerate(parts[:-1]):
        if part == "via":
            return parts[index + 1]
    return ""


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def keep_user_writable(path: Path) -> None:
    if os.geteuid() != 0:
        return
    try:
        home_stat = HOME.stat()
        os.chown(path, home_stat.st_uid, home_stat.st_gid)
    except OSError:
        return


def write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)
    keep_user_writable(path)


def nmcli_connection_value(connection: str, field: str) -> dict[str, Any]:
    return run(["nmcli", "-g", field, "connection", "show", connection], timeout=5)


def read_gui_guard_marker() -> dict[str, Any]:
    if not GUI_GUARD_MARKER.exists():
        return {}
    try:
        return json.loads(GUI_GUARD_MARKER.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_gui_guard_marker(connection: str, enabled: bool, permissions: str) -> None:
    try:
        GUI_GUARD_MARKER.parent.mkdir(parents=True, exist_ok=True)
        GUI_GUARD_MARKER.write_text(json.dumps({
            "connection": connection,
            "enabled": enabled,
            "permissions": permissions,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        }, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        return


def hotspot_gui_guard_status(connection: str = DEFAULT_HOTSPOT_CONNECTION) -> dict[str, Any]:
    result = run(["nmcli", "-g", "connection.permissions", "connection", "show", connection], timeout=5)
    permissions = first_line(result["stdout"]).replace("\\:", ":")
    if permissions == "--":
        permissions = ""
    marker = read_gui_guard_marker()
    marker_matches = (
        marker.get("connection") == connection
        and marker.get("enabled") is True
        and marker.get("permissions") == HOTSPOT_GUI_GUARD_PERMISSION
    )
    hidden_profile = (
        not result["ok"]
        and (
            result.get("code") == 10
            or "no such connection profile" in result["stderr"]
            or "没有这样的连接配置集" in result["stderr"]
        )
    )
    enabled = result["ok"] and permissions == HOTSPOT_GUI_GUARD_PERMISSION
    source = "nmcli"
    if hidden_profile and marker_matches:
        enabled = True
        permissions = HOTSPOT_GUI_GUARD_PERMISSION
        source = "marker_hidden_profile"
    return {
        "connection": connection,
        "enabled": enabled,
        "permissions": permissions,
        "target_permission": HOTSPOT_GUI_GUARD_PERMISSION,
        "source": source,
        "marker": marker,
        "check": result,
    }


def hotspot_gui_guard_enable(connection: str = DEFAULT_HOTSPOT_CONNECTION) -> dict[str, Any]:
    before = hotspot_gui_guard_status(connection)
    result = run(
        ["nmcli", "connection", "modify", connection, "connection.permissions", HOTSPOT_GUI_GUARD_PERMISSION],
        timeout=10,
    )
    if result["ok"]:
        write_gui_guard_marker(connection, True, HOTSPOT_GUI_GUARD_PERMISSION)
    after = hotspot_gui_guard_status(connection)
    return {"ok": result["ok"] and after["enabled"], "before": before, "result": result, "after": after}


def hotspot_gui_guard_disable(connection: str = DEFAULT_HOTSPOT_CONNECTION) -> dict[str, Any]:
    before = hotspot_gui_guard_status(connection)
    result = run(["nmcli", "connection", "modify", connection, "connection.permissions", ""], timeout=10)
    if result["ok"]:
        write_gui_guard_marker(connection, False, "")
    after = hotspot_gui_guard_status(connection)
    return {"ok": result["ok"] and not after["enabled"], "before": before, "result": result, "after": after}


def hotspot_preflight(connection: str = DEFAULT_HOTSPOT_CONNECTION) -> dict[str, Any]:
    interface_result = nmcli_connection_value(connection, "connection.interface-name")
    mode_result = nmcli_connection_value(connection, "802-11-wireless.mode")
    route_result = run(["ip", "route", "get", "8.8.8.8"], timeout=5)
    devices_result = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"], timeout=5)

    hotspot_interface = first_line(interface_result["stdout"])
    hotspot_mode = first_line(mode_result["stdout"])
    default_route = first_line(route_result["stdout"])
    default_route_interface = parse_route_interface(default_route)

    base = {
        "connection": connection,
        "hotspot_interface": hotspot_interface,
        "hotspot_mode": hotspot_mode,
        "default_route": default_route,
        "default_route_interface": default_route_interface,
        "devices": devices_result["stdout"],
        "checks": {
            "connection_interface": interface_result,
            "connection_mode": mode_result,
            "default_route": route_result,
            "devices": devices_result,
        },
        "recommendation": "Use Ethernet, USB tethering, or a second Wi-Fi adapter as upstream before starting the hotspot.",
    }

    if not interface_result["ok"]:
        gui_guard = hotspot_gui_guard_status(connection)
        hidden_profile = (
            interface_result.get("code") == 10
            or "no such connection profile" in interface_result["stderr"]
            or "没有这样的连接配置集" in interface_result["stderr"]
        )
        if gui_guard["enabled"] and hidden_profile:
            return {
                **base,
                "allowed": False,
                "risk": "gui_locked",
                "gui_guard": gui_guard,
                "message": (
                    f"{connection} is locked from normal GUI activation. "
                    "Use sudo ~/.local/bin/hotspot-safe-start after moving upstream to Ethernet, USB tethering, or another Wi-Fi adapter."
                ),
            }
        return {
            **base,
            "allowed": False,
            "risk": "missing_connection",
            "message": f"Cannot inspect NetworkManager connection {connection}.",
        }
    if hotspot_mode and hotspot_mode != "ap":
        return {
            **base,
            "allowed": False,
            "risk": "not_ap_connection",
            "message": f"{connection} is not an AP/hotspot connection.",
        }
    if not hotspot_interface:
        return {
            **base,
            "allowed": False,
            "risk": "unknown_hotspot_interface",
            "message": f"{connection} has no fixed interface; refusing to start it from the safe launcher.",
        }
    if not route_result["ok"] or not default_route_interface:
        return {
            **base,
            "allowed": False,
            "risk": "no_default_route",
            "message": "No current default route was found; hotspot would only provide local connectivity.",
        }
    if hotspot_interface == default_route_interface:
        return {
            **base,
            "allowed": False,
            "risk": "would_disconnect_upstream",
            "message": (
                f"Starting {connection} on {hotspot_interface} would reuse the current default-route "
                "Wi-Fi interface and disconnect the computer from upstream internet."
            ),
        }
    return {
        **base,
        "allowed": True,
        "risk": "ok",
        "message": (
            f"{connection} uses {hotspot_interface}; current default route uses "
            f"{default_route_interface}, so safe launcher may start the hotspot."
        ),
    }


def hotspot_start_safe(connection: str = DEFAULT_HOTSPOT_CONNECTION) -> dict[str, Any]:
    preflight = hotspot_preflight(connection)
    if not preflight["allowed"]:
        return {"ok": False, "preflight": preflight, "result": None}
    gui_guard = hotspot_gui_guard_status(connection)
    if gui_guard["enabled"] and os.geteuid() != 0:
        return {
            "ok": False,
            "risk": "root_required",
            "preflight": preflight,
            "gui_guard": gui_guard,
            "result": None,
            "message": f"{connection} is GUI-locked; run sudo ~/.local/bin/hotspot-safe-start after preflight is safe.",
        }
    if gui_guard["enabled"] and os.geteuid() == 0:
        unlock = hotspot_gui_guard_disable(connection)
        if not unlock["ok"]:
            return {
                "ok": False,
                "risk": "unlock_failed",
                "preflight": preflight,
                "gui_guard": gui_guard,
                "unlock": unlock,
                "result": None,
            }
    result = run(["nmcli", "connection", "up", connection], timeout=30)
    if gui_guard["enabled"] and os.geteuid() == 0 and not result["ok"]:
        relock = hotspot_gui_guard_enable(connection)
        return {
            "ok": False,
            "preflight": preflight,
            "gui_guard": gui_guard,
            "unlock": unlock,
            "relock": relock,
            "result": result,
        }
    return {"ok": result["ok"], "preflight": preflight, "gui_guard": gui_guard, "result": result}


def interface_driver(interface: str) -> str:
    driver = SYS_CLASS_NET / interface / "device" / "driver"
    try:
        return driver.resolve().name
    except OSError:
        return ""


def read_sysfs_value(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def interface_carrier(interface: str) -> bool:
    return read_sysfs_value(SYS_CLASS_NET / interface / "carrier") == "1"


def interface_operstate(interface: str) -> str:
    return read_sysfs_value(SYS_CLASS_NET / interface / "operstate")


def nmcli_device_connection(interface: str) -> str:
    result = run(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", interface], timeout=5)
    if not result["ok"]:
        return ""
    connection = first_line(result["stdout"]).replace("\\:", ":")
    return "" if connection == "--" else connection


def phone_tether_policy_key(interface: str, connection: str, driver: str) -> str:
    return f"{driver}:{interface}:{connection}"


def read_upstream_policy() -> dict[str, Any]:
    data = read_json_file(UPSTREAM_POLICY_FILE, {"phone_tether": {}})
    if not isinstance(data, dict):
        return {"phone_tether": {}}
    if not isinstance(data.get("phone_tether"), dict):
        data["phone_tether"] = {}
    return data


def write_upstream_policy(data: dict[str, Any]) -> None:
    write_json_file(UPSTREAM_POLICY_FILE, data)


def saved_phone_tether_policy(interface: str, connection: str, driver: str) -> str:
    policy = read_upstream_policy()
    key = phone_tether_policy_key(interface, connection, driver)
    value = policy.get("phone_tether", {}).get(key, "prompt")
    return value if value in {"prompt", "keep-current", "use-phone-port"} else "prompt"


def save_phone_tether_policy(interface: str, connection: str, driver: str, value: str) -> None:
    policy = read_upstream_policy()
    policy.setdefault("phone_tether", {})
    policy["phone_tether"][phone_tether_policy_key(interface, connection, driver)] = value
    policy["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
    write_upstream_policy(policy)


def read_network_event_store() -> dict[str, Any]:
    data = read_json_file(NETWORK_EVENTS_FILE, {"events": []})
    if not isinstance(data, dict):
        return {"events": []}
    if not isinstance(data.get("events"), list):
        data["events"] = []
    return data


def write_network_event_store(data: dict[str, Any]) -> None:
    events = data.get("events", [])
    if isinstance(events, list) and len(events) > 80:
        data["events"] = events[-80:]
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
    write_json_file(NETWORK_EVENTS_FILE, data)


def default_route_probe() -> dict[str, str]:
    route_result = run(["ip", "route", "get", "8.8.8.8"], timeout=5)
    route = first_line(route_result["stdout"])
    return {
        "default_route": route,
        "default_route_interface": parse_route_interface(route),
    }


def phone_tether_plan(interface: str, connection: str = "") -> dict[str, Any]:
    driver = interface_driver(interface)
    matched = driver in PHONE_TETHER_DRIVERS
    saved_policy = saved_phone_tether_policy(interface, connection, driver) if matched else "prompt"
    return {
        "interface": interface,
        "connection": connection,
        "driver": driver,
        "matched": matched,
        "reason": "phone_tether_driver" if matched else "not_phone_tether_driver",
        "saved_policy": saved_policy,
        "policy": PHONE_TETHER_DEMOTE_POLICY,
        "choices": PHONE_TETHER_CHOICES,
        "carrier": interface_carrier(interface),
        "operstate": interface_operstate(interface),
        "connection_known": bool(connection),
    }


def discover_phone_tether_plans() -> list[dict[str, Any]]:
    try:
        interfaces = sorted(item.name for item in SYS_CLASS_NET.iterdir() if item.is_dir() or item.is_symlink())
    except OSError:
        return []
    plans = []
    for interface in interfaces:
        driver = interface_driver(interface)
        if driver not in PHONE_TETHER_DRIVERS:
            continue
        plans.append(phone_tether_plan(interface, nmcli_device_connection(interface)))
    return plans


def phone_event_matches_plan(event: dict[str, Any], plan: dict[str, Any]) -> bool:
    if event.get("type") != "phone_tether_detected":
        return False
    if event.get("interface") != plan["interface"]:
        return False
    if event.get("driver") != plan["driver"]:
        return False
    event_connection = event.get("connection", "")
    plan_connection = plan.get("connection", "")
    return event_connection == plan_connection or not event_connection or not plan_connection


def resolved_phone_event_suppresses_plan(events: list[dict[str, Any]], plan: dict[str, Any]) -> bool:
    for event in reversed(events):
        if (
            phone_event_matches_plan(event, plan)
            and event.get("status") == "resolved"
            and event.get("present") is True
            and event.get("decision") in {"ignore-once", "keep-current", "use-phone-once"}
        ):
            return True
    return False


def mark_phone_event_presence(store: dict[str, Any], plans: list[dict[str, Any]]) -> bool:
    changed = False
    for event in store.get("events", []):
        if event.get("type") != "phone_tether_detected":
            continue
        present = any(phone_event_matches_plan(event, plan) for plan in plans)
        if event.get("present") != present:
            event["present"] = present
            changed = True
    return changed


def record_phone_tether_event(plan: dict[str, Any], dispatcher_action: str = "") -> dict[str, Any]:
    store = read_network_event_store()
    events = store["events"]
    route = default_route_probe()
    now = time.strftime("%Y-%m-%d %H:%M:%S %z")
    for event in events:
        same_connection = (
            event.get("connection") == plan["connection"]
            or not event.get("connection")
            or not plan.get("connection")
        )
        if (
            event.get("status") == "pending"
            and event.get("type") == "phone_tether_detected"
            and event.get("interface") == plan["interface"]
            and same_connection
        ):
            event["updated_at"] = now
            event["observed_count"] = int(event.get("observed_count", 1)) + 1
            event["dispatcher_action"] = dispatcher_action
            event["connection"] = plan.get("connection") or event.get("connection", "")
            event["connection_known"] = bool(event.get("connection"))
            event["carrier"] = bool(plan.get("carrier"))
            event["operstate"] = plan.get("operstate", "")
            event["present"] = True
            if route["default_route"]:
                event.update(route)
            write_network_event_store(store)
            return event
    event = {
        "id": f"{int(time.time() * 1000)}-{plan['interface']}",
        "type": "phone_tether_detected",
        "status": "pending",
        "interface": plan["interface"],
        "connection": plan["connection"],
        "driver": plan["driver"],
        "connection_known": bool(plan.get("connection")),
        "carrier": bool(plan.get("carrier")),
        "operstate": plan.get("operstate", ""),
        "present": True,
        "created_at": now,
        "updated_at": now,
        "observed_count": 1,
        "dispatcher_action": dispatcher_action,
        "message": "USB phone network detected. Choose whether it may become the upstream route.",
        "choices": PHONE_TETHER_CHOICES,
        **route,
    }
    events.append(event)
    write_network_event_store(store)
    return event


def connection_policy_args(connection: str, policy: dict[str, str]) -> list[str]:
    args = ["nmcli", "connection", "modify", connection]
    for key, value in policy.items():
        args.extend([key, value])
    return args


def apply_connection_policy(connection: str, policy: dict[str, str]) -> dict[str, Any]:
    return run(connection_policy_args(connection, policy), timeout=10)


def parse_nmcli_colon_fields(text: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields.setdefault(key.strip(), []).append(value.strip())
    return fields


def phone_egress_plan(interface: str, connection: str = "") -> dict[str, Any]:
    result = run(["nmcli", "-f", "IP4", "device", "show", interface], timeout=5)
    if not result["ok"]:
        return {"ok": False, "error": "device_ip4_unavailable", "interface": interface, "connection": connection, "check": result}
    fields = parse_nmcli_colon_fields(result["stdout"])
    address = first_line("\n".join(fields.get("IP4.ADDRESS[1]", [])))
    if not address:
        return {"ok": False, "error": "missing_ipv4_address", "interface": interface, "connection": connection, "check": result}
    try:
        ip4 = ipaddress.ip_interface(address)
    except ValueError as error:
        return {"ok": False, "error": f"invalid_ipv4_address: {error}", "interface": interface, "connection": connection, "check": result}
    gateway = first_line("\n".join(fields.get("IP4.GATEWAY", [])))
    if gateway == "--":
        gateway = ""
    if not gateway:
        gateway = first_line("\n".join(fields.get("IP4.DNS[1]", [])))
    if not gateway:
        hosts = list(ip4.network.hosts())
        gateway = str(hosts[0]) if hosts else ""
    if not gateway:
        return {"ok": False, "error": "missing_ipv4_gateway", "interface": interface, "connection": connection, "check": result}
    return {
        "ok": True,
        "listen": f"127.0.0.1:{PHONE_EGRESS_PORT}",
        "interface": interface,
        "connection": connection,
        "source_ip": str(ip4.ip),
        "source_cidr": f"{ip4.ip}/32",
        "network": str(ip4.network),
        "gateway": gateway,
        "table": PHONE_EGRESS_TABLE,
        "priority": PHONE_EGRESS_PRIORITY,
        "route_scope": "source-policy-only",
        "note": "Main default route is not changed; only traffic explicitly using the phone source IP uses this table.",
    }


def current_phone_egress_plan() -> dict[str, Any]:
    plans = discover_phone_tether_plans()
    for plan in plans:
        if plan.get("connection_known") and plan.get("carrier"):
            return phone_egress_plan(plan["interface"], plan.get("connection", ""))
    events = network_events_json()["pending"]
    for event in events:
        if event.get("connection_known") and event.get("carrier"):
            return phone_egress_plan(event["interface"], event.get("connection", ""))
    return {"ok": False, "error": "no_ready_phone_tether_event", "pending": events}


def phone_egress_root_apply_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not plan.get("ok"):
        return {"ok": False, "error": "invalid_plan", "plan": plan, "results": []}
    table = str(plan["table"])
    priority = str(plan["priority"])
    source_cidr = f"{plan['source_ip']}/32"
    commands = [
        ["ip", "route", "replace", plan["network"], "dev", plan["interface"], "src", plan["source_ip"], "table", table],
        ["ip", "route", "replace", "default", "via", plan["gateway"], "dev", plan["interface"], "table", table],
    ]
    rule_check = run(["ip", "rule", "show"], timeout=5)
    if source_cidr not in rule_check["stdout"] or f"lookup {table}" not in rule_check["stdout"]:
        commands.append(["ip", "rule", "add", "from", source_cidr, "table", table, "priority", priority])
    results = [run(command, timeout=10) for command in commands]
    return {"ok": all(item["ok"] for item in results), "plan": plan, "results": results, "rule_check": rule_check}


def phone_egress_root_apply() -> dict[str, Any]:
    return phone_egress_root_apply_from_plan(current_phone_egress_plan())


def phone_egress_root_remove_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not plan.get("ok"):
        return {"ok": False, "error": "invalid_plan", "plan": plan, "results": []}
    table = str(plan["table"])
    priority = str(plan["priority"])
    source_cidr = f"{plan['source_ip']}/32"
    commands = [
        ["ip", "rule", "del", "from", source_cidr, "table", table, "priority", priority],
        ["ip", "route", "flush", "table", table],
    ]
    results = [run(command, timeout=10) for command in commands]
    return {
        "ok": all(item["ok"] or "No such" in item["stderr"] or "FIB table does not exist" in item["stderr"] for item in results),
        "plan": plan,
        "results": results,
    }


def phone_egress_root_remove() -> dict[str, Any]:
    return phone_egress_root_remove_from_plan(current_phone_egress_plan())


def phone_tether_guard_plan(interface: str, connection: str) -> dict[str, Any]:
    return phone_tether_plan(interface, connection)


def phone_tether_guard_apply(interface: str, connection: str) -> dict[str, Any]:
    plan = phone_tether_guard_plan(interface, connection)
    if not plan["matched"]:
        return {"ok": True, "applied": False, "plan": plan, "event": None, "result": None}
    event = None
    if plan["saved_policy"] == "prompt":
        event = record_phone_tether_event(plan)
    result = apply_connection_policy(connection, plan["policy"])
    return {"ok": result["ok"], "applied": result["ok"], "plan": plan, "event": event, "result": result}


def network_events_json() -> dict[str, Any]:
    plans = discover_phone_tether_plans()
    store = read_network_event_store()
    changed = mark_phone_event_presence(store, plans)
    if changed:
        write_network_event_store(store)
    for plan in plans:
        if plan["saved_policy"] == "prompt":
            store = read_network_event_store()
            if not resolved_phone_event_suppresses_plan(store["events"], plan):
                record_phone_tether_event(plan, "scan")
    store = read_network_event_store()
    events = store["events"]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "events": events,
        "pending": [event for event in events if event.get("status") == "pending"],
        "policy": read_upstream_policy(),
    }


def update_event(store: dict[str, Any], event_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    for event in store["events"]:
        if event.get("id") == event_id:
            event.update(updates)
            return event
    return None


def upstream_select(event_id: str, decision: str) -> dict[str, Any]:
    valid = {choice["id"] for choice in PHONE_TETHER_CHOICES}
    if decision not in valid:
        return {"ok": False, "error": f"unknown decision: {decision}", "event": None, "result": None}
    store = read_network_event_store()
    event = next((item for item in store["events"] if item.get("id") == event_id), None)
    if not event:
        return {"ok": False, "error": f"unknown event: {event_id}", "event": None, "result": None}
    if event.get("type") != "phone_tether_detected":
        return {"ok": False, "error": f"unsupported event type: {event.get('type')}", "event": event, "result": None}

    connection = event["connection"]
    if not connection and decision in {"use-phone-once", "always-use-phone"}:
        return {"ok": False, "error": "phone_link_not_ready", "event": event, "result": None}
    policy_result = {"ok": True, "stdout": "", "stderr": "", "code": 0, "cmd": []}
    if connection and decision in {"keep-current", "always-keep-current", "use-phone-once", "always-use-phone"}:
        policy_result = apply_connection_policy(connection, PHONE_TETHER_DEMOTE_POLICY)

    if not policy_result["ok"]:
        return {"ok": False, "error": "failed to apply NetworkManager policy", "event": event, "result": policy_result}

    if decision == "always-keep-current":
        save_phone_tether_policy(event["interface"], connection, event.get("driver", ""), "keep-current")
    if decision == "always-use-phone":
        save_phone_tether_policy(event["interface"], connection, event.get("driver", ""), "use-phone-port")
    egress_plan = None
    if decision in {"use-phone-once", "always-use-phone"}:
        egress_plan = phone_egress_plan(event["interface"], connection)

    updated = update_event(store, event_id, {
        "status": "resolved",
        "decision": decision,
        "present": True,
        "resolved_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
    })
    write_network_event_store(store)
    return {"ok": True, "event": updated, "result": policy_result, "egress_plan": egress_plan}


def tail(path: Path, lines: int = 80) -> str:
    if not path.exists():
        return ""
    try:
        content = path.read_text(errors="replace").splitlines()
    except OSError as error:
        return f"could not read {path}: {error}"
    return "\n".join(content[-lines:])


def parse_iphone_lan_clients(text: str, server: str = "") -> list[dict[str, Any]]:
    clients: list[dict[str, Any]] = []
    pattern = re.compile(r"^(?P<time>.+?) INFO accepted client (?P<ip>[0-9a-fA-F:.]+):(?P<port>\d+)$")
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        ip = match.group("ip")
        clients.append({
            "timestamp": match.group("time"),
            "ip": ip,
            "port": int(match.group("port")),
            "local": ip in {server, "127.0.0.1", "::1"},
        })
    return clients[-12:]


def parse_failover_upstreams(text: str) -> list[dict[str, str]]:
    upstreams: list[dict[str, str]] = []
    pattern = re.compile(r"^(?P<time>.+?) INFO (?P<method>[A-Z]+) (?P<target>\S+) via (?P<route>\S+)$")
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        upstreams.append({
            "timestamp": match.group("time"),
            "method": match.group("method"),
            "target": match.group("target"),
            "route": match.group("route"),
        })
    return upstreams[-12:]


def parse_new_proxy_upstreams(text: str) -> list[dict[str, str]]:
    upstreams: list[dict[str, str]] = []
    pattern = re.compile(r"^(?P<time>.+?) INFO (?P<method>[A-Z]+) (?P<target>\S+) from (?P<client>\S+)$")
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        upstreams.append({
            "timestamp": match.group("time"),
            "method": match.group("method"),
            "target": match.group("target"),
            "route": "new",
            "client": match.group("client"),
        })
    return upstreams[-12:]


def parse_iphone_lan_routes(text: str) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    pattern = re.compile(
        r"^(?P<time>.+?) INFO (?P<method>[A-Z]+) (?P<target>\S+) "
        r"route=(?P<route>\S+) reason=(?P<reason>\S+) client=(?P<client>\S+)"
    )
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        routes.append({
            "timestamp": match.group("time"),
            "method": match.group("method"),
            "target": match.group("target"),
            "route": match.group("route"),
            "reason": match.group("reason"),
            "client": match.group("client"),
        })
    return routes[-12:]


def iphone_lan_proxy_status() -> dict[str, Any]:
    route = default_route_probe()
    server = parse_route_source(route.get("default_route", ""))
    port_open = port_listening(IPHONE_LAN_PROXY_PORT)
    iphone_lan_log = tail(LOGS["iphone_lan"], 240)
    recent_clients = parse_iphone_lan_clients(iphone_lan_log, server)
    external_clients = [item for item in recent_clients if not item["local"]]
    recent_upstreams = parse_iphone_lan_routes(iphone_lan_log) or parse_new_proxy_upstreams(tail(LOGS["new_http"], 240))
    allow_cidr = ""
    if server:
        try:
            allow_cidr = str(ipaddress.ip_network(f"{server}/24", strict=False))
        except ValueError:
            allow_cidr = ""

    if external_clients:
        firewall = {
            "status": "effective_open",
            "summary": "recent LAN client reached the bridge",
            "evidence": external_clients[-1],
        }
    elif port_open and server:
        firewall = {
            "status": "listening_needs_client",
            "summary": "LAN bridge is listening; no non-local client is visible in recent logs",
            "evidence": None,
        }
    elif not port_open:
        firewall = {
            "status": "closed",
            "summary": "LAN bridge port is not listening",
            "evidence": None,
        }
    else:
        firewall = {
            "status": "unknown",
            "summary": "LAN bind address could not be determined from the default route",
            "evidence": route,
        }

    return {
        "server": server,
        "port": IPHONE_LAN_PROXY_PORT,
        "setting": f"{server}:{IPHONE_LAN_PROXY_PORT}" if server else f"LAN-IP:{IPHONE_LAN_PROXY_PORT}",
        "authentication": False,
        "target": IPHONE_LAN_PROXY_TARGET,
        "allow_cidr": allow_cidr,
        "port_open": port_open,
        "default_route": route.get("default_route", ""),
        "default_route_interface": route.get("default_route_interface", ""),
        "firewall": {
            **firewall,
            "allow_command": (
                f"sudo ufw allow in from {allow_cidr or '<LAN-CIDR>'} "
                f"to {server or '<LAN-IP>'} port {IPHONE_LAN_PROXY_PORT} proto tcp"
            ),
        },
        "recent_clients": recent_clients,
        "recent_upstreams": recent_upstreams,
    }


def lan_cidr_for_interface(interface: str) -> str:
    if not interface:
        return ""
    result = run(["ip", "-4", "-o", "addr", "show", "dev", interface, "scope", "global"], timeout=5)
    if not result["ok"]:
        return ""
    for token in result["stdout"].split():
        if "/" in token:
            try:
                return str(ipaddress.ip_interface(token).network)
            except ValueError:
                continue
    return ""


def netmask_for_cidr(cidr: str) -> str:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return ""
    if not isinstance(network, ipaddress.IPv4Network):
        return ""
    return str(network.netmask)


def ip_forward_enabled() -> bool:
    try:
        return Path("/proc/sys/net/ipv4/ip_forward").read_text().strip() == "1"
    except OSError:
        result = run(["sysctl", "-n", "net.ipv4.ip_forward"], timeout=5)
        return result["ok"] and result["stdout"].strip() == "1"


def lan_gateway_nft_state() -> dict[str, str]:
    result = run(["nft", "list", "table", "inet", LAN_GATEWAY_TABLE], timeout=5)
    if result["ok"]:
        return {"state": "loaded", "detail": result["stdout"]}
    detail = result["stderr"] or result["stdout"]
    if "Operation not permitted" in detail:
        return {"state": "needs_root_check", "detail": "run: sudo nft list table inet lan_gateway"}
    if "No such file" in detail or "not found" in detail or "No such file or directory" in detail:
        return {"state": "disabled", "detail": detail}
    return {"state": "unknown", "detail": detail}


def read_lan_gateway_marker() -> dict[str, Any]:
    data = read_json_file(LAN_GATEWAY_STATE_FILE, {"enabled": False})
    return data if isinstance(data, dict) else {"enabled": False}


def infer_lan_gateway_client_ip(server: str = "") -> str:
    clients = parse_iphone_lan_clients(tail(LOGS["iphone_lan"], 240), server)
    external = [item for item in clients if not item.get("local")]
    return external[-1]["ip"] if external else ""


def validate_single_ipv4(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return ""
    if not isinstance(address, ipaddress.IPv4Address):
        return ""
    return str(address)


def validate_mac_address(value: str) -> str:
    value = (value or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", value):
        return value
    return ""


def validate_interface_name(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_.:-]+", value or ""):
        return value
    return ""


def lan_gateway_client_mac(client_ip: str, interface: str) -> str:
    client_ip = validate_single_ipv4(client_ip)
    interface = validate_interface_name(interface)
    if not client_ip or not interface:
        return ""
    result = run(["ip", "neigh", "show", client_ip, "dev", interface], timeout=5)
    if not result["ok"]:
        return ""
    match = re.search(r"\blladdr\s+([0-9A-Fa-f:]{17})\b", result["stdout"])
    return validate_mac_address(match.group(1)) if match else ""


def lan_gateway_plan(client_ip: str = "") -> dict[str, Any]:
    route = default_route_probe()
    default_route = route.get("default_route", "")
    interface = parse_route_interface(default_route)
    server = parse_route_source(default_route)
    gateway = parse_route_gateway(default_route)
    cidr = lan_cidr_for_interface(interface)
    inferred_client = infer_lan_gateway_client_ip(server)
    selected_client = validate_single_ipv4(client_ip or inferred_client)
    client_mac = lan_gateway_client_mac(selected_client, interface)
    nft = lan_gateway_nft_state()
    marker = read_lan_gateway_marker()
    enabled = nft["state"] == "loaded" or bool(marker.get("enabled"))
    marker_stale_reasons = []

    errors = []
    if not server:
        errors.append("missing_lan_server_ip")
    if not validate_interface_name(interface):
        errors.append("missing_or_invalid_interface")
    if not gateway:
        errors.append("missing_upstream_gateway")
    if not cidr:
        errors.append("missing_lan_cidr")
    if not selected_client:
        errors.append("missing_client_ip")
    if selected_client and cidr:
        try:
            if ipaddress.ip_address(selected_client) not in ipaddress.ip_network(cidr, strict=False):
                errors.append("client_ip_outside_lan_cidr")
        except ValueError:
            errors.append("invalid_lan_cidr")
    if selected_client in {server, gateway}:
        errors.append("client_ip_conflicts_with_gateway_or_host")
    if marker.get("enabled"):
        marker_client = str(marker.get("client_ip", ""))
        marker_mac = str(marker.get("client_mac", ""))
        marker_server = str(marker.get("server", ""))
        marker_interface = str(marker.get("interface", ""))
        if selected_client and marker_client and marker_client != selected_client:
            marker_stale_reasons.append(f"client_ip:{marker_client}->{selected_client}")
        if client_mac and marker_mac and marker_mac != client_mac:
            marker_stale_reasons.append(f"client_mac:{marker_mac}->{client_mac}")
        if server and marker_server and marker_server != server:
            marker_stale_reasons.append(f"server:{marker_server}->{server}")
        if interface and marker_interface and marker_interface != interface:
            marker_stale_reasons.append(f"interface:{marker_interface}->{interface}")

    setting_client = selected_client or "<iphone-ip>"
    root_apply = f"sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip {setting_client}"
    root_remove = "sudo ~/.local/bin/proxy-stack lan-gateway-root-remove"
    return {
        "ok": not errors,
        "enabled": enabled,
        "mode": "single-client-manual-router",
        "server": server,
        "interface": interface,
        "gateway": gateway,
        "cidr": cidr,
        "client_ip": selected_client,
        "client_mac": client_mac,
        "inferred_client_ip": inferred_client,
        "ip_forward": ip_forward_enabled(),
        "manual_iphone": {
            "ip": selected_client or "<keep-current-phone-ip>",
            "subnet_mask": netmask_for_cidr(cidr) or "255.255.255.0",
            "router": server or "<this-host-lan-ip>",
            "dns": server or "<this-host-lan-ip>",
        },
        "nft": nft,
        "marker": marker,
        "marker_stale": bool(marker_stale_reasons),
        "marker_stale_reasons": marker_stale_reasons,
        "errors": errors,
        "commands": {
            "root_apply": root_apply,
            "root_remove": root_remove,
            "check": "~/.local/bin/proxy-stack lan-gateway-plan",
        },
        "notes": [
            "Set only the test iPhone Wi-Fi router to this host.",
            "Root apply matches only the selected client IP.",
            "Rollback removes only the lan_gateway nftables table.",
        ],
    }


def port_open_from_status(data: dict[str, Any], port_id: str, fallback_port: int) -> bool:
    return any(
        item.get("id") == port_id and item.get("open")
        for item in data.get("ports", [])
    ) or port_listening(fallback_port)


def ipv6_default_route_state() -> dict[str, Any]:
    result = run(["ip", "-6", "route", "show", "default"], timeout=5)
    text = result.get("stdout", "").strip()
    if result["ok"]:
        return {
            "state": "present" if text else "absent",
            "detail": first_line(text),
            "check": result,
        }
    return {
        "state": "unknown",
        "detail": first_line(result.get("stderr", "") or result.get("stdout", "")),
        "check": result,
    }


def lan_gateway_rule_text(nft: dict[str, Any]) -> dict[str, str]:
    detail = str(nft.get("detail", ""))
    if nft.get("state") == "loaded" and detail:
        return {"source": "nft", "text": detail}
    if nft.get("state") == "needs_root_check" and LAN_GATEWAY_NFT_FILE.exists():
        try:
            return {"source": "generated_file_unverified", "text": LAN_GATEWAY_NFT_FILE.read_text()}
        except OSError as error:
            return {"source": "generated_file_unreadable", "text": str(error)}
    return {"source": str(nft.get("state", "unknown")), "text": detail}


def lan_gateway_coverage_report(data: dict[str, Any]) -> dict[str, Any]:
    lan_gateway = data.get("lan_gateway", {})
    if not lan_gateway.get("enabled"):
        return {
            "status": "pass",
            "summary": "LAN gateway mode is disabled; coverage report is not required",
            "checks": [],
        }

    nft = lan_gateway.get("nft", {})
    nft_state = nft.get("state", "")
    rule_source = lan_gateway_rule_text(nft)
    nft_detail = rule_source["text"]
    rules_are_proven = rule_source["source"] == "nft"
    client_ip = str(lan_gateway.get("client_ip", ""))
    client_mac = validate_mac_address(str(lan_gateway.get("client_mac", "")))
    checks: list[dict[str, Any]] = []

    def add(check_id: str, status: str, summary: str, evidence: Any = None) -> None:
        checks.append(check_item(check_id, status, summary, evidence=evidence))

    add(
        "selected-client",
        "fail" if not client_ip else "warn" if lan_gateway.get("marker_stale") else "pass",
        (
            "No selected LAN gateway client is available"
            if not client_ip
            else "LAN gateway marker points at a previous client"
            if lan_gateway.get("marker_stale")
            else "LAN gateway has one selected client"
        ),
        {
            "client_ip": client_ip,
            "client_mac": client_mac,
            "marker_stale": lan_gateway.get("marker_stale", False),
            "marker_stale_reasons": lan_gateway.get("marker_stale_reasons", []),
        },
    )

    client_in_nft = bool(client_ip and client_ip in nft_detail)
    if nft_state == "loaded":
        nft_status = "pass" if client_in_nft else "fail"
        nft_summary = "Loaded nftables table targets the selected client" if client_in_nft else "Loaded nftables table does not show the selected client"
    elif nft_state == "needs_root_check":
        nft_status = "warn"
        nft_summary = (
            "Generated nftables file targets the selected client, but root proof is still required"
            if client_in_nft
            else "nftables table needs root check before coverage can be proven"
        )
    else:
        nft_status = "fail"
        nft_summary = "LAN gateway nftables table is not loaded"
    add("nft-client-target", nft_status, nft_summary, {
        "state": nft_state,
        "client_ip": client_ip,
        "rule_source": rule_source["source"],
        "rules_are_proven": rules_are_proven,
    })

    add(
        "ip-forward",
        "pass" if lan_gateway.get("ip_forward") else "fail",
        "IPv4 forwarding is enabled" if lan_gateway.get("ip_forward") else "IPv4 forwarding is disabled",
        {"ip_forward": lan_gateway.get("ip_forward", False)},
    )

    split_dns_open = port_open_from_status(data, "split-dns", 1053)
    dns_rules_present = (
        "udp dport 53 redirect to :1053" in nft_detail
        and "tcp dport 53 redirect to :1053" in nft_detail
    )
    if split_dns_open and (dns_rules_present or nft_state == "needs_root_check"):
        dns_status = "pass" if dns_rules_present and rules_are_proven else "warn"
    else:
        dns_status = "fail"
    add(
        "dns-redirect",
        dns_status,
        (
            "LAN DNS is redirected to split DNS"
            if dns_status == "pass"
            else "Split DNS is listening but nft DNS redirect needs root proof"
            if dns_status == "warn"
            else "LAN DNS redirect is not ready"
        ),
        {"split_dns_open": split_dns_open, "rules_present": dns_rules_present, "rule_source": rule_source["source"]},
    )

    split_tcp_open = port_open_from_status(data, "split-tcp", 12345)
    tcp_rule_present = "meta l4proto tcp redirect to :12345" in nft_detail
    if split_tcp_open and (tcp_rule_present or nft_state == "needs_root_check"):
        tcp_status = "pass" if tcp_rule_present and rules_are_proven else "warn"
    else:
        tcp_status = "fail"
    add(
        "tcp-redirect",
        tcp_status,
        (
            "LAN TCP is redirected to split proxy"
            if tcp_status == "pass"
            else "Split TCP proxy is listening but nft TCP redirect needs root proof"
            if tcp_status == "warn"
            else "LAN TCP redirect is not ready"
        ),
        {"split_tcp_open": split_tcp_open, "rules_present": tcp_rule_present, "rule_source": rule_source["source"]},
    )

    quic_rule_present = "udp dport 443 reject" in nft_detail
    add(
        "udp-quic-policy",
        "pass" if quic_rule_present and rules_are_proven else "warn",
        (
            "UDP/443 is rejected so clients fall back to TCP"
            if quic_rule_present and rules_are_proven
            else "Generated UDP/443 policy exists but still needs root proof"
            if quic_rule_present
            else "UDP/443 policy is not proven; QUIC-heavy apps may bypass or stall"
        ),
        {"rules_present": quic_rule_present, "rule_source": rule_source["source"], "policy": "reject-udp-443-force-tcp"},
    )

    ipv6_state = ipv6_default_route_state()
    ipv6_rule_present = (
        " ip6 " in nft_detail
        or "meta nfproto ipv6" in nft_detail
        or bool(client_mac and client_mac in nft_detail and "icmpv6" in nft_detail)
    )
    add(
        "ipv6-policy",
        "pass" if ipv6_rule_present and rules_are_proven else "warn",
        (
            "LAN gateway has explicit IPv6 policy"
            if ipv6_rule_present and rules_are_proven
            else "Generated IPv6 policy exists but still needs root proof"
            if ipv6_rule_present
            else "LAN gateway currently proves IPv4 only; confirm client IPv6 is blocked or routed separately"
        ),
        {
            "rules_present": ipv6_rule_present,
            "client_mac": client_mac,
            "rule_source": rule_source["source"],
            "host_ipv6_default_route": ipv6_state,
        },
    )

    recent_clients = data.get("iphone_lan_proxy", {}).get("recent_clients", [])
    matching_clients = [item for item in recent_clients if item.get("ip") == client_ip]
    add(
        "recent-client-evidence",
        "pass" if matching_clients else "warn",
        (
            "Recent LAN logs include the selected gateway client"
            if matching_clients
            else "No recent LAN client log matches the selected gateway client"
        ),
        {"client_ip": client_ip, "matches": matching_clients, "recent_clients": recent_clients[-5:]},
    )

    dns = data.get("dns_decisions", {})
    dns_ok = dns.get("domestic") != "unknown" and dns.get("foreign") != "unknown"
    add(
        "dns-decision-evidence",
        "pass" if dns_ok else "warn",
        "Domestic and foreign DNS decisions are visible" if dns_ok else "DNS decision evidence is incomplete",
        dns,
    )

    status = overall_self_check_status(checks)
    return {
        "status": status,
        "summary": (
            "LAN gateway coverage is fully proven"
            if status == "pass"
            else "LAN gateway coverage has warnings"
            if status == "warn"
            else "LAN gateway coverage has blocking failures"
        ),
        "checks": checks,
    }


def render_lan_gateway_nft(plan: dict[str, Any]) -> str:
    client_ip = validate_single_ipv4(str(plan.get("client_ip", "")))
    client_mac = validate_mac_address(str(plan.get("client_mac", "")))
    interface = validate_interface_name(str(plan.get("interface", "")))
    if not client_ip or not interface:
        raise ValueError("lan gateway nft requires a single IPv4 client and safe interface name")
    reserved = ", ".join(str(port) for port in LAN_GATEWAY_RESERVED_TCP_PORTS)
    ipv6_guard = (
        f'\n    iifname "{interface}" ether saddr {client_mac} meta nfproto ipv6 reject'
        if client_mac
        else ""
    )
    return f"""table inet {LAN_GATEWAY_TABLE} {{
  chain prerouting {{
    type nat hook prerouting priority dstnat; policy accept;

    iifname "{interface}" ip saddr {client_ip} udp dport 53 redirect to :1053
    iifname "{interface}" ip saddr {client_ip} tcp dport 53 redirect to :1053

    iifname "{interface}" ip saddr {client_ip} tcp dport {{ {reserved} }} accept
    iifname "{interface}" ip saddr {client_ip} meta l4proto tcp redirect to :12345
  }}

  chain postrouting {{
    type nat hook postrouting priority srcnat; policy accept;

    ip saddr {client_ip} oifname "{interface}" masquerade
  }}

  chain forward_guard {{
    type filter hook forward priority -20; policy accept;

    iifname "{interface}" ip saddr {client_ip} udp dport 443 reject
    {ipv6_guard.strip()}
  }}
}}
"""


def lan_gateway_root_apply(client_ip: str) -> dict[str, Any]:
    if os.geteuid() != 0:
        return {"ok": False, "error": "root_required", "run": "sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip <iphone-ip>"}
    plan = lan_gateway_plan(client_ip)
    if not plan["ok"]:
        return {"ok": False, "error": "plan_not_ready", "plan": plan}
    try:
        nft_text = render_lan_gateway_nft(plan)
    except ValueError as error:
        return {"ok": False, "error": str(error), "plan": plan}
    LAN_GATEWAY_NFT_FILE.write_text(nft_text)
    keep_user_writable(LAN_GATEWAY_NFT_FILE)
    check_result = run(["nft", "-c", "-f", str(LAN_GATEWAY_NFT_FILE)], timeout=10)
    if not check_result["ok"]:
        return {
            "ok": False,
            "error": "nft_check_failed",
            "plan": plan,
            "nft_file": str(LAN_GATEWAY_NFT_FILE),
            "check": check_result,
        }
    results = [
        run(["sysctl", "-w", "net.ipv4.ip_forward=1"], timeout=10),
        run(["nft", "delete", "table", "inet", LAN_GATEWAY_TABLE], timeout=10),
        run(["nft", "-f", str(LAN_GATEWAY_NFT_FILE)], timeout=10),
    ]
    delete_result = results[1]
    ok = results[0]["ok"] and results[2]["ok"]
    if not delete_result["ok"] and "No such file" not in (delete_result["stderr"] or delete_result["stdout"]):
        ok = False
    if ok:
        write_json_file(LAN_GATEWAY_STATE_FILE, {
            "enabled": True,
            "client_ip": plan["client_ip"],
            "client_mac": plan.get("client_mac", ""),
            "server": plan["server"],
            "interface": plan["interface"],
            "gateway": plan["gateway"],
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        })
    return {"ok": ok, "plan": plan, "nft_file": str(LAN_GATEWAY_NFT_FILE), "check": check_result, "results": results}


def lan_gateway_root_remove() -> dict[str, Any]:
    if os.geteuid() != 0:
        return {"ok": False, "error": "root_required", "run": "sudo ~/.local/bin/proxy-stack lan-gateway-root-remove"}
    result = run(["nft", "delete", "table", "inet", LAN_GATEWAY_TABLE], timeout=10)
    missing = "No such file" in (result["stderr"] or result["stdout"]) or "No such file or directory" in (result["stderr"] or result["stdout"])
    if result["ok"] or missing:
        write_json_file(LAN_GATEWAY_STATE_FILE, {
            "enabled": False,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        })
    return {"ok": result["ok"] or missing, "result": result}


def dns_decisions() -> dict[str, str]:
    text = tail(LOGS["split_dns"], 120)
    decisions = {"domestic": "unknown", "foreign": "unknown"}
    for line in text.splitlines():
        if "direct DNS www.baidu.com" in line:
            decisions["domestic"] = line
        if "remote DNS retry www.google.com" in line:
            decisions["foreign"] = line
    return decisions


def nft_state() -> dict[str, Any]:
    result = run(["nft", "list", "table", "inet", "hotspot_split"], timeout=5)
    if result["ok"]:
        return {"state": "loaded", "detail": result["stdout"]}
    detail = result["stderr"] or result["stdout"]
    service = run(["systemctl", "is-active", "hotspot-split-nft.service"], timeout=5)
    if service["ok"] and service["stdout"] == "active":
        return {"state": "loaded", "detail": "hotspot-split-nft.service is active; use sudo nft list table inet hotspot_split for rules"}
    if "Operation not permitted" in detail:
        return {"state": "needs_root_check", "detail": "run: sudo nft list table inet hotspot_split"}
    if "No such file" in detail or "not found" in detail:
        return {"state": "missing", "detail": detail}
    return {"state": "unknown", "detail": detail}


def status_json() -> dict[str, Any]:
    services = []
    for name in USER_SERVICES:
        status = service_status(name, user=True)
        services.append({
            "name": name,
            "scope": "user",
            "state": status["state"],
            "systemd_state": status["systemd_state"],
            "port_fallback": status["port_fallback"],
            "ports": status["ports"],
            "enabled": service_enabled(name, user=True),
        })
    for name in SYSTEM_SERVICES:
        status = service_status(name, user=False)
        services.append({
            "name": name,
            "scope": "system",
            "state": status["state"],
            "systemd_state": status["systemd_state"],
            "port_fallback": status["port_fallback"],
            "ports": status["ports"],
            "enabled": service_enabled(name, user=False),
        })

    current_ports = listening_ports()
    ports = []
    for item in PORTS:
        ports.append({**item, "open": int(item["port"]) in current_ports})

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "topology": [
            {"name": "Old route", "path": "1080 SOCKS -> 8118 HTTP", "role": "primary upstream"},
            {"name": "New route", "path": "11880 SOCKS -> 18122 HTTP", "role": "failover upstream"},
            {"name": "Failover", "path": "18180 HTTP -> old first, new on failure", "role": "foreign traffic bridge"},
            {"name": "Hotspot split", "path": "10.42.0.0/16 DNS:1053 TCP:12345", "role": "domestic direct, foreign proxy"},
        ],
        "services": services,
        "ports": ports,
        "iphone_lan_proxy": iphone_lan_proxy_status(),
        "lan_gateway": lan_gateway_plan(),
        "nft": nft_state(),
        "hotspot_preflight": hotspot_preflight(),
        "hotspot_gui_guard": hotspot_gui_guard_status(),
        "network_events": network_events_json(),
        "commands": {
            "root_apply": "sudo ~/.local/bin/hotspot-split-gateway root-apply",
            "root_remove": "sudo ~/.local/bin/hotspot-split-gateway root-remove",
            "status": "~/.local/bin/proxy-stack status",
            "self_check": "~/.local/bin/proxy-stack self-check",
            "self_check_deep": "~/.local/bin/proxy-stack self-check --deep",
            "test": "~/.local/bin/proxy-stack test",
            "hotspot_preflight": "~/.local/bin/proxy-stack hotspot-preflight",
            "hotspot_start_safe": "~/.local/bin/proxy-stack hotspot-start-safe",
            "hotspot_gui_guard_status": "~/.local/bin/proxy-stack hotspot-gui-guard-status",
            "hotspot_gui_guard_enable": "sudo ~/.local/bin/proxy-stack hotspot-gui-guard-enable",
            "hotspot_gui_guard_disable": "sudo ~/.local/bin/proxy-stack hotspot-gui-guard-disable",
            "network_events": "~/.local/bin/proxy-stack network-events",
            "upstream_select": "~/.local/bin/proxy-stack upstream-select <event-id> <decision>",
            "phone_egress_plan": "~/.local/bin/proxy-stack phone-egress-plan",
            "phone_egress_root_apply": "sudo ~/.local/bin/proxy-stack phone-egress-root-apply",
            "phone_egress_root_remove": "sudo ~/.local/bin/proxy-stack phone-egress-root-remove",
            "iphone_lan_proxy_plan": "~/.local/bin/iphone-lan-proxy plan",
            "lan_gateway_plan": "~/.local/bin/proxy-stack lan-gateway-plan",
            "lan_gateway_root_apply": "sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip <iphone-ip>",
            "lan_gateway_root_remove": "sudo ~/.local/bin/proxy-stack lan-gateway-root-remove",
        },
        "raw": {
            "old_proxy": {
                "old_socks": "open" if any(item["id"] == "old-socks" and item["open"] for item in ports) else "closed",
                "old_http": "open" if any(item["id"] == "old-http" and item["open"] for item in ports) else "closed",
            },
            "note": "Detailed legacy status is available through the individual proxy-app and hotspot-split-gateway CLIs.",
        },
        "dns_decisions": dns_decisions(),
    }


def status_text() -> str:
    data = status_json()
    lines = [f"proxy stack status @ {data['generated_at']}"]
    lines.append("")
    lines.append("Services:")
    for service in data["services"]:
        lines.append(f"  {service['scope']:6} {service['name']:<40} {service['state']:<10} {service['enabled']}")
    lines.append("")
    lines.append("Ports:")
    for port in data["ports"]:
        state = "open" if port["open"] else "closed"
        lines.append(f"  {port['label']:<14} {port['host']}:{port['port']:<5} {state}")
    lines.append("")
    lines.append(f"nft: {data['nft']['state']} - {data['nft']['detail'].splitlines()[0] if data['nft']['detail'] else ''}")
    iphone_lan = data.get("iphone_lan_proxy", {})
    firewall = iphone_lan.get("firewall", {})
    lines.append(f"iPhone LAN proxy: {iphone_lan.get('setting', 'LAN-IP:18181')} - {firewall.get('status', 'unknown')}")
    lan_gateway = data.get("lan_gateway", {})
    lan_gateway_state = "enabled" if lan_gateway.get("enabled") else "disabled"
    lines.append(f"LAN gateway: {lan_gateway_state} client={lan_gateway.get('client_ip') or '--'} router={lan_gateway.get('server') or '--'}")
    lines.append(f"domestic dns: {data['dns_decisions']['domestic']}")
    lines.append(f"foreign dns:  {data['dns_decisions']['foreign']}")
    guard = data["hotspot_preflight"]
    lines.append(f"hotspot guard: {guard['risk']} - {guard['message']}")
    gui_guard = data["hotspot_gui_guard"]
    lines.append(f"hotspot gui guard: {'enabled' if gui_guard['enabled'] else 'disabled'} - permissions={gui_guard['permissions'] or '--'}")
    return "\n".join(lines)


def test_all() -> dict[str, Any]:
    return {
        "dns_baidu": run(["dig", "@127.0.0.1", "-p", "1053", "+time=4", "+tries=1", "www.baidu.com"], timeout=10),
        "dns_google": run(["dig", "@127.0.0.1", "-p", "1053", "+time=4", "+tries=1", "www.google.com"], timeout=10),
        "failover": run([str(BIN / "proxy-failover"), "test"], timeout=25),
        "old_proxy": run([str(BIN / "proxy-app"), "--test"], timeout=25),
    }


def check_item(check_id: str, status: str, summary: str, detail: str = "", evidence: Any = None) -> dict[str, Any]:
    item = {"id": check_id, "status": status, "summary": summary}
    if detail:
        item["detail"] = detail
    if evidence is not None:
        item["evidence"] = evidence
    return item


def overall_self_check_status(checks: list[dict[str, Any]]) -> str:
    statuses = {item["status"] for item in checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def self_check(deep: bool = False) -> dict[str, Any]:
    data = status_json()
    checks: list[dict[str, Any]] = []

    inactive_services = [
        f"{item['scope']}:{item['name']}={item['state']}"
        for item in data["services"]
        if item.get("state") != "active"
    ]
    port_fallback_services = [
        f"{item['scope']}:{item['name']} systemd={item.get('systemd_state', 'unknown')} ports={item.get('ports', [])}"
        for item in data["services"]
        if item.get("state") == "active" and item.get("port_fallback")
    ]
    checks.append(check_item(
        "services",
        "pass" if not inactive_services else "fail",
        (
            "Core proxy services are active or their expected endpoints are listening"
            if port_fallback_services and not inactive_services
            else "Core proxy services are active"
            if not inactive_services
            else "Some core proxy services are inactive"
        ),
        evidence=inactive_services or {
            "active": [f"{item['scope']}:{item['name']}" for item in data["services"]],
            "port_fallback": port_fallback_services,
        },
    ))

    dashboard_state = service_state("proxy-dashboard.service", user=True)
    dashboard_port_open = port_listening(DASHBOARD_PORT)
    dashboard_ok = dashboard_state == "active" or dashboard_port_open
    checks.append(check_item(
        "dashboard-service",
        "pass" if dashboard_ok else "fail",
        (
            "Dashboard service is active"
            if dashboard_state == "active"
            else "Dashboard endpoint is listening"
            if dashboard_port_open
            else "Dashboard service is not active"
        ),
        evidence={"state": dashboard_state, "port_open": dashboard_port_open, "url": f"http://127.0.0.1:{DASHBOARD_PORT}"},
    ))

    closed_ports = [f"{item['host']}:{item['port']} ({item['id']})" for item in data["ports"] if not item.get("open")]
    checks.append(check_item(
        "ports",
        "pass" if not closed_ports else "fail",
        "Core proxy ports are listening" if not closed_ports else "Some core proxy ports are closed",
        evidence=closed_ports or [f"{item['host']}:{item['port']}" for item in data["ports"]],
    ))

    iphone_lan = data.get("iphone_lan_proxy", {})
    iphone_lan_port_open = bool(iphone_lan.get("port_open")) or any(
        item.get("id") == "iphone-lan" and item.get("open") for item in data["ports"]
    )
    iphone_lan_firewall = iphone_lan.get("firewall", {})
    iphone_lan_firewall_status = iphone_lan_firewall.get("status", "unknown")
    if not iphone_lan_port_open:
        iphone_lan_status = "fail"
        iphone_lan_summary = "iPhone LAN proxy port is not listening"
    elif iphone_lan_firewall_status == "effective_open":
        iphone_lan_status = "pass"
        iphone_lan_summary = "iPhone LAN proxy is reachable from LAN"
    else:
        iphone_lan_status = "warn"
        iphone_lan_summary = "iPhone LAN proxy is listening but needs a phone-side reachability check"
    checks.append(check_item(
        "iphone-lan-proxy",
        iphone_lan_status,
        iphone_lan_summary,
        detail=iphone_lan_firewall.get("summary", ""),
        evidence={
            "setting": iphone_lan.get("setting", f"LAN-IP:{IPHONE_LAN_PROXY_PORT}"),
            "authentication": iphone_lan.get("authentication", False),
            "target": iphone_lan.get("target", IPHONE_LAN_PROXY_TARGET),
            "port_open": iphone_lan_port_open,
            "firewall": iphone_lan_firewall,
            "recent_clients": iphone_lan.get("recent_clients", []),
            "recent_upstreams": iphone_lan.get("recent_upstreams", []),
        },
    ))

    lan_gateway = data.get("lan_gateway", {})
    if lan_gateway.get("enabled"):
        if lan_gateway.get("marker_stale"):
            lan_gateway_status = "warn"
            lan_gateway_summary = "LAN gateway rules appear to target a previous client"
        else:
            lan_gateway_status = "pass" if lan_gateway.get("ok") else "fail"
            lan_gateway_summary = "LAN gateway mode is enabled for one client" if lan_gateway.get("ok") else "LAN gateway mode is enabled but plan is not ready"
    else:
        lan_gateway_status = "pass"
        lan_gateway_summary = "LAN gateway mode is disabled"
    checks.append(check_item(
        "lan-gateway",
        lan_gateway_status,
        lan_gateway_summary,
        detail=", ".join(lan_gateway.get("errors", [])),
        evidence={
            "enabled": lan_gateway.get("enabled", False),
            "client_ip": lan_gateway.get("client_ip", ""),
            "server": lan_gateway.get("server", ""),
            "interface": lan_gateway.get("interface", ""),
            "gateway": lan_gateway.get("gateway", ""),
            "ip_forward": lan_gateway.get("ip_forward", False),
            "nft": lan_gateway.get("nft", {}),
            "marker": lan_gateway.get("marker", {}),
            "marker_stale": lan_gateway.get("marker_stale", False),
            "marker_stale_reasons": lan_gateway.get("marker_stale_reasons", []),
            "commands": lan_gateway.get("commands", {}),
        },
    ))

    nft_status = data["nft"]["state"]
    checks.append(check_item(
        "nftables",
        "pass" if nft_status == "loaded" else "warn" if nft_status == "needs_root_check" else "fail",
        "Hotspot split nftables table is loaded" if nft_status == "loaded" else "Hotspot split nftables state needs attention",
        detail=first_line(data["nft"].get("detail", "")),
        evidence={"state": nft_status},
    ))

    dns = data["dns_decisions"]
    dns_ok = dns.get("domestic") != "unknown" and dns.get("foreign") != "unknown"
    checks.append(check_item(
        "dns-decisions",
        "pass" if dns_ok else "warn",
        "Domestic and foreign DNS decisions are visible" if dns_ok else "DNS decision evidence is incomplete",
        evidence=dns,
    ))

    preflight = data["hotspot_preflight"]
    guard_ok = preflight.get("allowed") or preflight.get("risk") in {"gui_locked", "would_disconnect_upstream"}
    checks.append(check_item(
        "hotspot-guard",
        "pass" if preflight.get("allowed") else "warn" if guard_ok else "fail",
        "Hotspot guard allows start" if preflight.get("allowed") else "Hotspot guard is blocking unsafe start",
        detail=preflight.get("message", ""),
        evidence={"risk": preflight.get("risk"), "default_route_interface": preflight.get("default_route_interface")},
    ))

    events = data["network_events"]
    pending_count = len(events.get("pending", []))
    checks.append(check_item(
        "network-events",
        "pass" if pending_count == 0 else "warn",
        "No pending upstream decisions" if pending_count == 0 else "Pending upstream decisions need a user choice",
        evidence={"pending": pending_count},
    ))

    phone_plans = discover_phone_tether_plans()
    phone_port_open = port_listening(PHONE_EGRESS_PORT)
    if phone_plans:
        egress_plan = current_phone_egress_plan()
        egress_ok = egress_plan.get("ok") and phone_port_open
        checks.append(check_item(
            "phone-egress",
            "pass" if egress_ok else "fail",
            "Explicit phone egress port is ready" if egress_ok else "Explicit phone egress port is not ready",
            evidence={
                "listen": f"127.0.0.1:{PHONE_EGRESS_PORT}",
                "port_open": phone_port_open,
                "plan": egress_plan,
            },
        ))
    else:
        checks.append(check_item(
            "phone-egress",
            "pass",
            "No USB phone egress is currently required",
            evidence={"listen": f"127.0.0.1:{PHONE_EGRESS_PORT}", "phone_detected": False},
        ))

    lan_gateway_coverage = None
    deep_tests = None
    if deep:
        lan_gateway_coverage = lan_gateway_coverage_report(data)
        checks.append(check_item(
            "lan-gateway-coverage",
            lan_gateway_coverage["status"],
            lan_gateway_coverage["summary"],
            evidence=lan_gateway_coverage,
        ))

        deep_tests = test_all()
        failed = {name: result for name, result in deep_tests.items() if not result.get("ok")}
        checks.append(check_item(
            "deep-connectivity",
            "pass" if not failed else "fail",
            "DNS and proxy connectivity tests passed" if not failed else "DNS or proxy connectivity tests failed",
            evidence=failed or deep_tests,
        ))

    overall = overall_self_check_status(checks)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "mode": "deep" if deep else "quick",
        "overall": overall,
        "ok": overall != "fail",
        "checks": checks,
        "lan_gateway_coverage": lan_gateway_coverage,
        "deep_tests": deep_tests,
        "commands": {
            "quick": "~/.local/bin/proxy-stack self-check",
            "deep": "~/.local/bin/proxy-stack self-check --deep",
            "status": "~/.local/bin/proxy-stack status",
            "dashboard": "http://127.0.0.1:4077/api/self-check",
        },
    }


def restart_user_services() -> dict[str, Any]:
    commands = [
        ["systemctl", "--user", "restart", "secondary-proxy-client.service"],
        ["systemctl", "--user", "restart", "secondary-http-proxy.service"],
        ["systemctl", "--user", "restart", "proxy-failover.service"],
        ["systemctl", "--user", "restart", "hotspot-split-proxy.service", "hotspot-split-dns.service"],
    ]
    results = []
    for command in commands:
        results.append(run(command, timeout=20))
        if not results[-1]["ok"]:
            break
    return {"ok": all(item["ok"] for item in results), "results": results}


def update_cn_routes() -> dict[str, Any]:
    return run([str(BIN / "hotspot-split-gateway"), "update-cn"], timeout=90)


def logs_json(lines: int = 80) -> dict[str, str]:
    return {name: tail(path, lines) for name, path in LOGS.items()}


def export_profile_template() -> dict[str, Any]:
    """Return a redacted v2 portable profile template with local-only route hints."""
    return {
        "version": 2,
        "name": "portable-private-gateway",
        "routes": {
            "old": {
                "type": "http",
                "endpoint": "http://127.0.0.1:8118",
                "authRef": "usb-profile:old",
            },
            "new": {
                "type": "http",
                "endpoint": "http://127.0.0.1:18122",
                "authRef": "usb-profile:new",
            },
            "failover": {
                "type": "failover",
                "endpoint": "http://127.0.0.1:18180",
                "order": ["old", "new"],
            },
            "lanProxy": {
                "type": "lanProxy",
                "bind": "dynamic",
                "policy": "cn-private-direct-foreign-proxy",
                "settingHint": "LAN-IP:dynamic",
            },
        },
        "splitRules": {
            "policy": "cn-private-direct-foreign-proxy",
            "domestic": "direct",
            "private": "direct",
            "foreign": "new",
        },
        "privacy": {
            "logs": "redacted",
            "state": "tmpfs-or-usb",
        },
        "notes": [
            "Template is redacted; do not store real proxy credentials in this JSON.",
            "Encrypted USB profile storage owns real secrets in v2.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Proxy stack control surface")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("json")
    sub.add_parser("test")
    self_check_parser = sub.add_parser("self-check")
    self_check_parser.add_argument("--deep", action="store_true")
    sub.add_parser("restart-user")
    sub.add_parser("update-cn")
    preflight_parser = sub.add_parser("hotspot-preflight")
    preflight_parser.add_argument("connection", nargs="?", default=DEFAULT_HOTSPOT_CONNECTION)
    start_parser = sub.add_parser("hotspot-start-safe")
    start_parser.add_argument("connection", nargs="?", default=DEFAULT_HOTSPOT_CONNECTION)
    gui_guard_status_parser = sub.add_parser("hotspot-gui-guard-status")
    gui_guard_status_parser.add_argument("connection", nargs="?", default=DEFAULT_HOTSPOT_CONNECTION)
    gui_guard_enable_parser = sub.add_parser("hotspot-gui-guard-enable")
    gui_guard_enable_parser.add_argument("connection", nargs="?", default=DEFAULT_HOTSPOT_CONNECTION)
    gui_guard_disable_parser = sub.add_parser("hotspot-gui-guard-disable")
    gui_guard_disable_parser.add_argument("connection", nargs="?", default=DEFAULT_HOTSPOT_CONNECTION)
    phone_guard_parser = sub.add_parser("phone-tether-guard-apply")
    phone_guard_parser.add_argument("interface")
    phone_guard_parser.add_argument("connection")
    sub.add_parser("network-events")
    upstream_select_parser = sub.add_parser("upstream-select")
    upstream_select_parser.add_argument("event_id")
    upstream_select_parser.add_argument("decision", choices=[choice["id"] for choice in PHONE_TETHER_CHOICES])
    sub.add_parser("phone-egress-plan")
    sub.add_parser("phone-egress-root-apply")
    sub.add_parser("phone-egress-root-remove")
    lan_gateway_plan_parser = sub.add_parser("lan-gateway-plan")
    lan_gateway_plan_parser.add_argument("--client-ip", default="")
    lan_gateway_apply_parser = sub.add_parser("lan-gateway-root-apply")
    lan_gateway_apply_parser.add_argument("--client-ip", required=True)
    sub.add_parser("lan-gateway-root-remove")
    sub.add_parser("export-profile-template")
    log_parser = sub.add_parser("logs")
    log_parser.add_argument("--lines", type=int, default=80)
    args = parser.parse_args()

    if args.cmd in (None, "status"):
        print(status_text())
        return 0
    if args.cmd == "json":
        print(json.dumps(status_json(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "test":
        result = test_all()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if all(item["ok"] for item in result.values()) else 1
    if args.cmd == "self-check":
        result = self_check(deep=args.deep)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "restart-user":
        result = restart_user_services()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "update-cn":
        result = update_cn_routes()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "hotspot-preflight":
        result = hotspot_preflight(args.connection)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["allowed"] else 1
    if args.cmd == "hotspot-start-safe":
        result = hotspot_start_safe(args.connection)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "hotspot-gui-guard-status":
        result = hotspot_gui_guard_status(args.connection)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["enabled"] or result["check"]["ok"] else 1
    if args.cmd == "hotspot-gui-guard-enable":
        result = hotspot_gui_guard_enable(args.connection)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "hotspot-gui-guard-disable":
        result = hotspot_gui_guard_disable(args.connection)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "phone-tether-guard-apply":
        result = phone_tether_guard_apply(args.interface, args.connection)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "network-events":
        print(json.dumps(network_events_json(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "upstream-select":
        result = upstream_select(args.event_id, args.decision)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "phone-egress-plan":
        result = current_phone_egress_plan()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "phone-egress-root-apply":
        result = phone_egress_root_apply()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "phone-egress-root-remove":
        result = phone_egress_root_remove()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "lan-gateway-plan":
        result = lan_gateway_plan(args.client_ip)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "lan-gateway-root-apply":
        result = lan_gateway_root_apply(args.client_ip)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "lan-gateway-root-remove":
        result = lan_gateway_root_remove()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "export-profile-template":
        print(json.dumps(export_profile_template(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "logs":
        print(json.dumps(logs_json(args.lines), ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
