#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from .port_registry import build_session_manifest, utc_now_iso
    from .health import doctor as doctor_report
    from .diagnostics import export_diagnostics
    from .profile_crypto import ProfileCryptoError, copy_encrypted_profile, encrypted_profile_status, read_encrypted_profile, write_encrypted_profile
    from .profile_crypto import profile_digest, profile_summary
    from .profile_schema import redacted_profile_template, validate_profile
    from .upstream_profile import load_upstream_json, upstream_to_profile
    from .runtime_launcher import build_runtime_plan, phone_setup_from_session, runtime_status, start_runtime, stop_runtime
    from .session_store import SessionStore, redact_payload
    from .linux_lifecycle import lifecycle_status, uninstall_control_layer
    from .unlock_server import lock as unlock_lock
    from .unlock_server import serve_unlock
    from .unlock_server import unlock as unlock_profile
    from .unlock_server import unlock_status
    from .usb_identity import detect_usb, trusted_manifest_template
except ImportError:
    from port_registry import build_session_manifest, utc_now_iso
    from health import doctor as doctor_report
    from diagnostics import export_diagnostics
    from profile_crypto import ProfileCryptoError, copy_encrypted_profile, encrypted_profile_status, read_encrypted_profile, write_encrypted_profile
    from profile_crypto import profile_digest, profile_summary
    from profile_schema import redacted_profile_template, validate_profile
    from upstream_profile import load_upstream_json, upstream_to_profile
    from runtime_launcher import build_runtime_plan, phone_setup_from_session, runtime_status, start_runtime, stop_runtime
    from session_store import SessionStore, redact_payload
    from linux_lifecycle import lifecycle_status, uninstall_control_layer
    from unlock_server import lock as unlock_lock
    from unlock_server import serve_unlock
    from unlock_server import unlock as unlock_profile
    from unlock_server import unlock_status
    from usb_identity import detect_usb, trusted_manifest_template


AGENT_VERSION = 2
FEATURE_FLAG = "GATEWAY_AGENT_V2"
RUNTIME_DIR_ENV = "GATEWAY_AGENT_RUNTIME_DIR"
LAN_HOST_ENV = "GATEWAY_AGENT_LAN_HOST"
PROFILE_PATH_ENV = "GATEWAY_AGENT_PROFILE_PATH"
UNLOCK_TOKEN_TTL_SECONDS = 900


def runtime_dir() -> Path:
    return SessionStore().runtime_dir


def session_path() -> Path:
    return SessionStore().session_path


def enabled() -> bool:
    return os.environ.get(FEATURE_FLAG) == "1"


def read_json(path: Path) -> dict[str, Any] | None:
    return SessionStore(path.parent).read_json(path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    SessionStore(path.parent).write_json(path, payload)


def remove_session() -> bool:
    return SessionStore().remove_session()


def default_profile_path() -> Path:
    configured = os.environ.get(PROFILE_PATH_ENV)
    if configured:
        return Path(configured).expanduser()
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return base / "proxy-gateway" / "profile.json.enc"


def resolve_profile_path(profile_path: str | None = None) -> Path:
    return Path(profile_path).expanduser() if profile_path else default_profile_path()


def profile_source_status(profile_path: str | None = None, usb_root: str | None = None) -> dict[str, Any]:
    local_path = resolve_profile_path(profile_path)
    local = encrypted_profile_status(local_path)
    if local["present"] and local["state"] == "encrypted_profile_present":
        return {
            "mode": "local",
            "present": True,
            "state": local["state"],
            "path": local["path"],
            "errors": [],
        }
    usb = detect_usb(usb_root)
    if usb.get("profilePresent"):
        return {
            "mode": "recovery",
            "present": True,
            "state": "recovery_profile_present",
            "path": usb.get("profilePath", ""),
            "errors": usb.get("errors", []),
        }
    return {
        "mode": "local",
        "present": False,
        "state": local["state"],
        "path": local["path"],
        "errors": local.get("errors", []),
    }


def build_status(usb_root: str | None = None, profile_path: str | None = None) -> dict[str, Any]:
    store = SessionStore()
    store.ensure()
    manifest = store.read_session()
    usb = detect_usb(usb_root)
    unlock = unlock_status(store, usb_root)
    profile_source = profile_source_status(profile_path, usb_root)
    runtime_plan = build_runtime_plan(manifest, None)
    runtime_state = runtime_status(store)
    phone_setup = phone_setup_from_session(manifest)
    is_enabled = enabled()
    state = "locked_or_disabled"
    summary = "v2 agent disabled; v1 fallback remains active"
    if is_enabled and runtime_state.get("state") == "running":
        state = "running"
        summary = "v2 LAN proxy child is running; v1 fallback remains active"
    elif is_enabled and manifest:
        state = "manifest_ready"
        summary = "v2 session manifest is ready; no network child services are started in this slice"
    elif is_enabled:
        summary = "v2 agent enabled but locked; no session manifest exists"

    return {
        "version": AGENT_VERSION,
        "ok": True,
        "enabled": is_enabled,
        "state": state,
        "summary": summary,
        "generatedAt": utc_now_iso(),
        "runtimeDir": str(store.runtime_dir),
        "sessionPath": str(store.session_path),
        "usb": usb,
        "profileSource": profile_source,
        "unlock": unlock,
        "privateRuntime": {
            "state": "tmpfs",
            "logs": "redacted",
            "inventory": store.private_state_inventory(),
        },
        "session": manifest,
        "runtimePlan": runtime_plan,
        "runtimeState": runtime_state,
        "phoneSetup": phone_setup,
    }


def start_session(lan_host: str | None = None) -> dict[str, Any]:
    if not enabled():
        status = build_status()
        status["ok"] = False
        status["summary"] = "set GATEWAY_AGENT_V2=1 to create a v2 session manifest"
        return status

    selected_lan_host = lan_host or os.environ.get(LAN_HOST_ENV)
    try:
        manifest = build_session_manifest(
            lan_host=selected_lan_host,
            include_lan=bool(selected_lan_host),
        )
    except (OSError, RuntimeError, ValueError) as error:
        status = build_status()
        status["ok"] = False
        status["state"] = "runtime_blocked"
        status["summary"] = "v2 session manifest could not be created; dynamic port allocation is unavailable"
        status["error"] = {
            "type": type(error).__name__,
            "errno": getattr(error, "errno", None),
            "message": str(error),
        }
        return status
    store = SessionStore()
    cleanup = store.cleanup_stale_session()
    store.write_session(manifest)
    store.write_event({
        "event": "start-session",
        "sessionId": manifest["sessionId"],
        "lanHost": selected_lan_host or "",
        "cleanup": cleanup,
    })
    status = build_status()
    status["staleCleanup"] = cleanup
    return status


def stop_session(process_killer=None) -> dict[str, Any]:
    store = SessionStore()
    stop_runtime(store=store, process_killer=process_killer)
    removed = store.remove_session()
    token_removed = unlock_lock(store).get("removedToken", False)
    status = build_status()
    status["removedSession"] = removed
    status["removedToken"] = token_removed
    status["summary"] = "v2 session manifest removed; v1 fallback remains active"
    return status


def watchdog_once(
    usb_root: str | None = None,
    profile_path: str | None = None,
    process_checker=None,
    process_killer=None,
) -> dict[str, Any]:
    store = SessionStore()
    store.ensure()
    usb = detect_usb(usb_root)
    session = store.read_session()
    runtime_state = runtime_status(store, process_checker=process_checker)
    if session and usb.get("state") in {"missing", "manifest_missing", "manifest_invalid", "untrusted"}:
        stopped = stop_session(process_killer=process_killer)
        stopped["state"] = "locked_removed"
        stopped["summary"] = "USB removal or trust failure detected; v2 session locked"
        stopped["usb"] = usb
        store.write_event({"event": "watchdog", "state": stopped["state"], "reason": "usb"})
        return stopped
    if runtime_state.get("state") == "stale":
        stopped_runtime = stop_runtime(store=store, process_killer=process_killer)
        store.write_event({"event": "watchdog", "state": "stale_runtime_cleaned", "reason": "runtime-stale"})
        return {
            "ok": stopped_runtime.get("ok", False),
            "state": "stale_runtime_cleaned",
            "summary": "stale v2 child state cleaned; session manifest preserved",
            "runtimeState": runtime_state,
            "runtimeStop": stopped_runtime,
        }
    profile_source = profile_source_status(profile_path, usb_root)
    if session and runtime_state.get("state") == "running" and not profile_source.get("present"):
        stopped = stop_session(process_killer=process_killer)
        stopped["state"] = "profile_source_lost_locked"
        stopped["summary"] = "v2 local profile source disappeared; session locked and child services stopped"
        stopped["profileSource"] = profile_source
        store.write_event({"event": "watchdog", "state": stopped["state"], "reason": "profile-source-lost"})
        return stopped
    return {
        "ok": True,
        "state": "watch_ok",
        "summary": "no watchdog action required",
        "usb": usb,
        "profileSource": profile_source,
        "runtimeState": runtime_state,
    }


def watch_usb_once(usb_root: str | None = None, profile_path: str | None = None) -> dict[str, Any]:
    return watchdog_once(usb_root=usb_root, profile_path=profile_path)


def daemon_loop(
    usb_root: str | None = None,
    profile_path: str | None = None,
    interval: float = 5.0,
    iterations: int | None = None,
) -> dict[str, Any]:
    store = SessionStore()
    store.write_event({"event": "daemon-start", "usbRoot": usb_root or "", "interval": interval})
    count = 0
    last_result: dict[str, Any] = {"ok": True, "state": "daemon_started"}
    while True:
        last_result = watchdog_once(usb_root, profile_path)
        store.write_event({"event": "daemon-watch", "state": last_result.get("state", "unknown")})
        count += 1
        if iterations is not None and count >= iterations:
            return {
                "ok": True,
                "state": "daemon_checked",
                "iterations": count,
                "last": last_result,
            }
        time.sleep(max(interval, 1.0))


def self_check(usb_root: str | None = None, profile_path: str | None = None, passphrase: str = "") -> dict[str, Any]:
    store = SessionStore()
    status = build_status(usb_root, profile_path)
    lifecycle = lifecycle_status(store)
    profile_source = status["profileSource"]
    profile: dict[str, Any] | None = None
    profile_error = ""
    if passphrase and profile_source.get("present"):
        try:
            profile = read_encrypted_profile(profile_source["path"], passphrase)
        except ProfileCryptoError as error:
            profile_error = str(error)
    doctor = doctor_report(store, usb_root=usb_root, profile=profile, profile_source=profile_source)
    checks = [
        {
            "id": "feature-flag",
            "status": "pass" if status["enabled"] else "warn",
            "summary": "v2 feature flag is enabled" if status["enabled"] else "v2 feature flag is disabled",
            "detail": FEATURE_FLAG,
        },
        {
            "id": "runtime-dir",
            "status": "pass",
            "summary": "runtime path resolved",
            "detail": status["runtimeDir"],
        },
        {
            "id": "session-manifest",
            "status": "pass" if status["session"] else "warn",
            "summary": "session manifest exists" if status["session"] else "session manifest not present",
            "detail": status["sessionPath"],
        },
        {
            "id": "usb",
            "status": "pass" if status["usb"].get("trusted") else "warn",
            "summary": status["usb"].get("state", "unknown"),
            "detail": status["usb"].get("root", ""),
        },
        {
            "id": "profile-source",
            "status": "fail" if profile_error else "pass" if status["profileSource"].get("present") else "warn",
            "summary": profile_error or status["profileSource"].get("state", "missing"),
            "detail": status["profileSource"].get("mode", "local"),
        },
        {
            "id": "unlock",
            "status": "pass" if status["unlock"].get("state") == "unlocked" else "warn",
            "summary": status["unlock"].get("state", "unknown"),
            "detail": status["unlock"].get("bind", "127.0.0.1"),
        },
        {
            "id": "linux-v3-lifecycle",
            "status": "pass" if lifecycle.get("state") == "installed" else "warn",
            "summary": lifecycle.get("summary", "Linux v3 lifecycle status unavailable"),
            "detail": lifecycle.get("contract", {}).get("stop", "preserve-config"),
            "evidence": lifecycle,
        },
    ]
    seen = {item["id"] for item in checks}
    checks.extend(item for item in doctor["checks"] if item["id"] not in seen)
    has_fail = any(item["status"] == "fail" for item in checks)
    return {
        "version": AGENT_VERSION,
        "ok": not has_fail,
        "overall": "fail" if has_fail else "pass" if all(item["status"] == "pass" for item in checks) else "warn",
        "generatedAt": utc_now_iso(),
        "state": status["state"],
        "checks": checks,
        "status": status,
        "doctor": doctor,
    }


def print_json(payload: dict[str, Any]) -> None:
    # CLI stdout is the local control contract; redact_payload strips secret-like
    # fields before rendering.
    # codeql[py/clear-text-logging-sensitive-data]
    sys.stdout.write(json.dumps(redact_payload(payload), indent=2, ensure_ascii=False))
    sys.stdout.write("\n")


def passphrase_from_args(args: argparse.Namespace) -> str:
    if args.passphrase_file:
        return Path(args.passphrase_file).expanduser().read_text(encoding="utf-8").strip()
    return args.passphrase


def profile_encrypt_command(
    usb_root: str | None,
    profile_input: str,
    profile_output: str,
    passphrase: str,
) -> dict[str, Any]:
    try:
        input_path = _profile_input_path(usb_root, profile_input)
        output_path = _profile_output_path(usb_root, profile_output)
        profile = validate_profile(json.loads(input_path.read_text(encoding="utf-8")))
        return write_encrypted_profile(profile, output_path, passphrase)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, ProfileCryptoError) as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": str(error),
        }


def profile_decrypt_check_command(usb_root: str | None, profile_output: str, passphrase: str) -> dict[str, Any]:
    try:
        profile_path = _profile_output_path(usb_root, profile_output)
        profile = read_encrypted_profile(profile_path, passphrase)
        return {
            "ok": True,
            "path": str(profile_path),
            "summary": profile_summary(profile),
            "profileDigest": profile_digest(profile),
        }
    except (ValueError, ProfileCryptoError) as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": str(error),
        }


def profile_import_command(profile_from: str, profile_path: str | None = None) -> dict[str, Any]:
    try:
        if not profile_from:
            raise ValueError("--from is required")
        target = resolve_profile_path(profile_path)
        result = copy_encrypted_profile(profile_from, target)
        return {
            **result,
            "state": "imported",
            "profileSource": {
                "mode": "local",
                "path": result["path"],
            },
        }
    except (ValueError, ProfileCryptoError, OSError) as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": str(error),
        }


def profile_from_upstream_command(upstream_from: str, profile_output: str, passphrase: str) -> dict[str, Any]:
    try:
        if not upstream_from:
            raise ValueError("--from is required")
        output_path = _profile_output_path(None, profile_output)
        profile = upstream_to_profile(load_upstream_json(upstream_from))
        result = write_encrypted_profile(profile, output_path, passphrase)
        return {
            **result,
            "state": "converted",
            "source": "upstream-adapter",
        }
    except (ValueError, ProfileCryptoError, OSError) as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": str(error),
        }


def profile_export_command(profile_path: str | None, profile_to: str) -> dict[str, Any]:
    try:
        if not profile_to:
            raise ValueError("--to is required")
        result = copy_encrypted_profile(resolve_profile_path(profile_path), profile_to)
        return {
            **result,
            "state": "exported",
        }
    except (ValueError, ProfileCryptoError, OSError) as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": str(error),
        }


def unlock_local_profile(store: SessionStore, profile_path: str | None, passphrase: str) -> dict[str, Any]:
    source = profile_source_status(profile_path)
    if not source.get("present"):
        return {
            "ok": False,
            "state": "blocked",
            "summary": "encrypted local profile is required before unlock",
            "profileSource": source,
        }
    try:
        profile = read_encrypted_profile(source["path"], passphrase)
    except ProfileCryptoError as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": str(error),
            "profileSource": source,
        }
    summary = profile_summary(profile)
    token = {
        "token": secrets.token_urlsafe(32),
        "createdAt": utc_now_iso(),
        "expiresInSeconds": UNLOCK_TOKEN_TTL_SECONDS,
        "expiresAt": _expires_at_iso(UNLOCK_TOKEN_TTL_SECONDS),
        "passphraseSupplied": bool(passphrase),
        "profileLoaded": True,
        "profileDigest": profile_digest(profile),
        "profileSummary": summary,
        "profileSource": {"mode": source["mode"]},
    }
    store.write_token(token)
    store.write_event({"event": "unlock", "state": "unlocked", "profileSource": {"mode": source["mode"]}, "profile": summary, "token": token["token"]})
    safe_token = {key: value for key, value in token.items() if key != "token"}
    return {
        "ok": True,
        "state": "unlocked",
        "summary": "encrypted local profile loaded and unlock token created in private runtime state",
        "token": safe_token,
        "profileSource": source,
    }


def runtime_start_command(
    profile_path: str | None,
    passphrase: str,
    allow_child: bool = False,
    process_factory=None,
) -> dict[str, Any]:
    store = SessionStore()
    source = profile_source_status(profile_path)
    if not source.get("present"):
        return {
            "ok": False,
            "state": "blocked",
            "summary": "encrypted local profile is required before v2 child services start",
            "profileSource": source,
        }
    try:
        profile = read_encrypted_profile(source["path"], passphrase)
    except ProfileCryptoError as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": str(error),
            "profileSource": source,
        }
    plan = build_runtime_plan(store.read_session(), profile)
    return start_runtime(
        plan,
        dry_run=False,
        allow_child=allow_child,
        store=store,
        process_factory=process_factory,
    )


def _expires_at_iso(ttl_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat().replace("+00:00", "Z")


def _profile_input_path(usb_root: str | None, profile_input: str) -> Path:
    if profile_input:
        return Path(profile_input).expanduser()
    if usb_root:
        return Path(usb_root).expanduser() / "profile" / "profile.template.json"
    raise ValueError("--profile-input or --usb-root is required")


def _profile_output_path(usb_root: str | None, profile_output: str) -> Path:
    if profile_output:
        return Path(profile_output).expanduser()
    if usb_root:
        return Path(usb_root).expanduser() / "profile" / "profile.json.enc"
    raise ValueError("--profile-output or --usb-root is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Linux LAN Gateway v2 local agent")
    parser.add_argument(
        "command",
        choices=(
            "status",
            "lifecycle-status",
            "start",
            "stop",
            "lock",
            "self-check",
            "doctor",
            "usb-status",
            "unlock-status",
            "unlock",
            "unlock-server",
            "watch-usb-once",
            "watchdog-once",
            "daemon",
            "profile-template",
            "profile-encrypt",
            "profile-from-upstream",
            "profile-decrypt-check",
            "profile-import",
            "profile-export",
            "usb-manifest-template",
            "runtime-plan",
            "runtime-start-dry-run",
            "runtime-start",
            "phone-setup",
            "export-diagnostics",
            "uninstall",
        ),
    )
    parser.add_argument("--usb-root", default=None)
    parser.add_argument("--lan-host", default=None)
    parser.add_argument("--passphrase", default="")
    parser.add_argument("--passphrase-file", default="")
    parser.add_argument("--profile-input", default="")
    parser.add_argument("--profile-output", default="")
    parser.add_argument("--profile-path", default="")
    parser.add_argument("--from", dest="profile_from", default="")
    parser.add_argument("--to", dest="profile_to", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--output", default="")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--allow-child", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "status":
        print_json(build_status(args.usb_root, args.profile_path))
        return 0
    if args.command == "lifecycle-status":
        print_json(lifecycle_status())
        return 0
    if args.command == "start":
        result = start_session(args.lan_host)
        print_json(result)
        return 0 if result.get("ok") else 2
    if args.command == "stop":
        print_json(stop_session())
        return 0
    if args.command == "lock":
        result = stop_session()
        result["summary"] = "v2 locked; session and unlock token removed"
        print_json(result)
        return 0
    if args.command == "self-check":
        print_json(self_check(args.usb_root, args.profile_path, passphrase_from_args(args)))
        return 0
    if args.command == "doctor":
        print_json(doctor_report(SessionStore(), usb_root=args.usb_root))
        return 0
    if args.command == "usb-status":
        print_json(detect_usb(args.usb_root))
        return 0
    if args.command == "unlock-status":
        print_json(unlock_status(SessionStore(), args.usb_root))
        return 0
    if args.command == "unlock":
        source = profile_source_status(args.profile_path, args.usb_root)
        if source.get("mode") == "local" and source.get("present"):
            result = unlock_local_profile(SessionStore(), args.profile_path, passphrase_from_args(args))
        else:
            result = unlock_profile(SessionStore(), args.usb_root, passphrase_from_args(args))
        print_json(result)
        return 0 if result.get("ok") else 2
    if args.command == "unlock-server":
        if args.host != "127.0.0.1":
            print_json({"ok": False, "error": "unlock server only binds to 127.0.0.1"})
            return 2
        server = serve_unlock(SessionStore(), args.usb_root, host=args.host, port=args.port)
        print_json({"ok": True, "url": f"http://{server.server_address[0]}:{server.server_address[1]}"})
        server.serve_forever()
        return 0
    if args.command == "watch-usb-once":
        print_json(watch_usb_once(args.usb_root, args.profile_path))
        return 0
    if args.command == "watchdog-once":
        print_json(watchdog_once(args.usb_root, args.profile_path))
        return 0
    if args.command == "daemon":
        result = daemon_loop(args.usb_root, args.profile_path, args.interval, iterations=1 if args.once else None)
        if args.once:
            print_json(result)
        return 0
    if args.command == "profile-template":
        print_json(redacted_profile_template())
        return 0
    if args.command == "profile-encrypt":
        result = profile_encrypt_command(args.usb_root, args.profile_input, args.profile_output, passphrase_from_args(args))
        print_json(result)
        return 0 if result.get("ok") else 2
    if args.command == "profile-from-upstream":
        result = profile_from_upstream_command(args.profile_from, args.profile_output, passphrase_from_args(args))
        print_json(result)
        return 0 if result.get("ok") else 2
    if args.command == "profile-decrypt-check":
        result = profile_decrypt_check_command(args.usb_root, args.profile_output, passphrase_from_args(args))
        print_json(result)
        return 0 if result.get("ok") else 2
    if args.command == "profile-import":
        result = profile_import_command(args.profile_from, args.profile_path)
        print_json(result)
        return 0 if result.get("ok") else 2
    if args.command == "profile-export":
        result = profile_export_command(args.profile_path, args.profile_to)
        print_json(result)
        return 0 if result.get("ok") else 2
    if args.command == "usb-manifest-template":
        print_json(trusted_manifest_template())
        return 0
    if args.command == "runtime-plan":
        print_json(build_runtime_plan(SessionStore().read_session(), None))
        return 0
    if args.command == "runtime-start-dry-run":
        print_json(start_runtime(build_runtime_plan(SessionStore().read_session(), None), dry_run=True))
        return 0
    if args.command == "runtime-start":
        result = runtime_start_command(args.profile_path, passphrase_from_args(args), allow_child=args.allow_child)
        print_json(result)
        return 0 if result.get("ok") else 2
    if args.command == "phone-setup":
        print_json(phone_setup_from_session(SessionStore().read_session()))
        return 0
    if args.command == "export-diagnostics":
        print_json(export_diagnostics(SessionStore(), args.output or None))
        return 0
    if args.command == "uninstall":
        result = uninstall_control_layer(apply=bool(args.apply))
        print_json(result)
        return 0 if result.get("ok") else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
