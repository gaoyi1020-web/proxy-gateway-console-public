from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


USB_ROOT_ENV = "GATEWAY_AGENT_USB_ROOT"
USB_MANIFEST = "manifest.json"
USB_PROFILE = "profile/profile.json.enc"
EXPECTED_PRODUCT = "PROXY_GATEWAY"
SUPPORTED_VERSION = 2
MANIFEST_MARKER_FIELD = "marker"
LEGACY_MANIFEST_MARKER_FIELD = "trustId"


def detect_usb(root: str | Path | None = None) -> dict[str, Any]:
    configured = root or os.environ.get(USB_ROOT_ENV)
    if not configured:
        return {
            "present": False,
            "trusted": False,
            "state": "not_configured",
            "root": "",
            "manifest": None,
            "errors": [],
        }

    usb_root = Path(configured).expanduser()
    if not usb_root.exists():
        return {
            "present": False,
            "trusted": False,
            "state": "missing",
            "root": str(usb_root),
            "manifest": None,
            "errors": ["usb root does not exist"],
        }

    manifest_path = usb_root / USB_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _status(usb_root, None, False, "manifest_missing", ["manifest.json missing"])
    except json.JSONDecodeError:
        return _status(usb_root, None, False, "manifest_invalid", ["manifest.json is not valid JSON"])

    errors = validate_usb_manifest(manifest)
    profile_present = (usb_root / USB_PROFILE).exists()
    trusted = not errors
    state = "trusted" if trusted else "untrusted"
    return {
        **_status(usb_root, manifest, trusted, state, errors),
        "profilePresent": profile_present,
        "profilePath": str(usb_root / USB_PROFILE),
    }


def validate_usb_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    if manifest.get("product") != EXPECTED_PRODUCT:
        errors.append("manifest product mismatch")
    if manifest.get("version") != SUPPORTED_VERSION:
        errors.append("manifest version mismatch")
    marker = manifest.get(MANIFEST_MARKER_FIELD) or manifest.get(LEGACY_MANIFEST_MARKER_FIELD)
    if not isinstance(marker, str) or len(marker) < 12:
        errors.append("manifest marker is missing or too short")
    if "secret" in manifest or "password" in manifest or "token" in manifest:
        errors.append("manifest contains secret-like fields")
    return errors


def recovery_manifest_template() -> dict[str, Any]:
    return {
        "product": EXPECTED_PRODUCT,
        "version": SUPPORTED_VERSION,
        MANIFEST_MARKER_FIELD: "replace-with-local-random-marker",
        "label": "Linux LAN Gateway Recovery",
        "policy": "public-marker-only",
    }


def _status(root: Path, manifest: dict[str, Any] | None, trusted: bool, state: str, errors: list[str]) -> dict[str, Any]:
    summary = None
    if isinstance(manifest, dict):
        marker = manifest.get(MANIFEST_MARKER_FIELD) or manifest.get(LEGACY_MANIFEST_MARKER_FIELD)
        summary = {
            "product": manifest.get("product"),
            "version": manifest.get("version"),
            "label": manifest.get("label", ""),
            "markerPresent": isinstance(marker, str) and bool(marker),
        }
    return {
        "present": True,
        "trusted": trusted,
        "state": state,
        "root": str(root),
        "manifest": summary,
        "errors": errors,
    }
