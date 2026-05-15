from __future__ import annotations

from typing import Any

try:
    from .profile_schema import ProfileValidationError, validate_profile
    from .runtime_launcher import build_runtime_plan, phone_setup_from_session
    from .session_store import SessionStore
    from .usb_identity import detect_usb
except ImportError:
    from profile_schema import ProfileValidationError, validate_profile
    from runtime_launcher import build_runtime_plan, phone_setup_from_session
    from session_store import SessionStore
    from usb_identity import detect_usb


def doctor(
    store: SessionStore,
    profile: dict[str, Any] | None = None,
    usb_root: str | None = None,
    profile_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    store.ensure()
    session = store.read_session()
    token = store.read_token()
    usb = detect_usb(usb_root)
    checks = [
        _check("runtime-dir", True, "runtime directory resolved", str(store.runtime_dir)),
        _check("session-manifest", bool(session), "session manifest present" if session else "session manifest absent", str(store.session_path)),
        _check("usb", bool(usb.get("trusted")), usb.get("state", "unknown"), usb.get("root", "")),
        _check(
            "profile-source",
            bool(profile_source and profile_source.get("present")),
            profile_source.get("state", "missing") if profile_source else "missing",
            profile_source.get("mode", "local") if profile_source else "local",
        ),
        _check("token", bool(token), "unlock token present" if token else "unlock token absent", str(store.token_path)),
    ]
    if profile is not None:
        try:
            validate_profile(profile)
            checks.append(_check("profile-schema", True, "profile schema valid", "redacted profile object"))
        except ProfileValidationError as error:
            checks.append(_check("profile-schema", False, "profile schema invalid", str(error), fail=True))
    else:
        checks.append(_check(
            "profile-schema",
            bool(token and token.get("profileLoaded")),
            "profile loaded" if token and token.get("profileLoaded") else "profile not loaded",
            token.get("profileDigest", "") if token else "unlock required",
        ))

    has_fail = any(item["status"] == "fail" for item in checks)
    has_warn = any(item["status"] == "warn" for item in checks)
    return {
        "ok": not has_fail,
        "overall": "fail" if has_fail else "warn" if has_warn else "pass",
        "checks": checks,
        "privateState": store.private_state_inventory(),
        "runtimePlan": build_runtime_plan(session, profile),
        "phoneSetup": phone_setup_from_session(session),
    }


def _check(check_id: str, ok: bool, summary: str, detail: str = "", fail: bool = False) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "pass" if ok else "fail" if fail else "warn",
        "summary": summary,
        "detail": detail,
    }
