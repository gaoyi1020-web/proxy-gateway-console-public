from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

try:
    from .health import doctor
    from .port_registry import utc_now_iso
    from .session_store import SessionStore, redact_payload
except ImportError:
    from health import doctor
    from port_registry import utc_now_iso
    from session_store import SessionStore, redact_payload


def export_diagnostics(store: SessionStore, output: str | Path | None = None) -> dict[str, Any]:
    store.ensure()
    export_path = Path(output).expanduser() if output else store.runtime_dir / "recovery" / "gateway-agent-diagnostics.zip"
    export_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)

    payloads = {
        "doctor.json": doctor(store),
        "session.redacted.json": redact_payload(store.read_session() or {}),
        "private-state.json": redact_payload(store.private_state_inventory()),
        "export.json": {
            "createdAt": utc_now_iso(),
            "redacted": True,
        },
    }

    with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        if store.events_path.exists():
            archive.writestr("events.redacted.jsonl", store.events_path.read_text(encoding="utf-8"))
    export_path.chmod(0o600)
    return {
        "ok": True,
        "path": str(export_path),
        "redacted": True,
        "entries": sorted(payloads.keys()) + (["events.redacted.jsonl"] if store.events_path.exists() else []),
    }
