from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


RUNTIME_DIR_ENV = "GATEWAY_AGENT_RUNTIME_DIR"
TOKEN_FILE = "unlock-token.json"
SESSION_FILE = "session.json"
EVENT_LOG_FILE = "events.jsonl"

SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|secret|token|auth|server|endpoint)([=:]\s*)([^,\s\"']+)"
)


def default_runtime_dir() -> Path:
    configured = os.environ.get(RUNTIME_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    user_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if user_runtime:
        return Path(user_runtime) / "proxy-gateway"
    return Path(f"/run/user/{os.getuid()}/proxy-gateway")


def redact_text(value: str) -> str:
    return SECRET_PATTERN.sub(r"\1\2[redacted]", value)


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        redacted = {}
        for key, value in payload.items():
            if key.lower() in {"password", "passwd", "secret", "token", "auth", "credential"}:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_payload(value)
        return redacted
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, str):
        return redact_text(payload)
    return payload


class SessionStore:
    def __init__(self, runtime_dir: Path | str | None = None) -> None:
        self.runtime_dir = Path(runtime_dir).expanduser() if runtime_dir else default_runtime_dir()

    @property
    def session_path(self) -> Path:
        return self.runtime_dir / SESSION_FILE

    @property
    def token_path(self) -> Path:
        return self.runtime_dir / TOKEN_FILE

    @property
    def events_path(self) -> Path:
        return self.runtime_dir / EVENT_LOG_FILE

    @property
    def state_dir(self) -> Path:
        return self.runtime_dir / "state"

    @property
    def logs_dir(self) -> Path:
        return self.runtime_dir / "logs"

    def ensure(self) -> None:
        original_runtime_dir = self.runtime_dir
        try:
            self._create_private_dirs()
        except OSError:
            fallback = self.fallback_runtime_dir()
            if original_runtime_dir == fallback:
                raise
            self.runtime_dir = fallback
            self._create_private_dirs()

    @staticmethod
    def fallback_runtime_dir() -> Path:
        return Path(tempfile.gettempdir()) / f"proxy-gateway-{os.getuid()}"

    def _create_private_dirs(self) -> None:
        for path in (self.runtime_dir, self.state_dir, self.logs_dir):
            path.mkdir(parents=True, mode=0o700, exist_ok=True)
            try:
                path.chmod(0o700)
            except OSError:
                pass
        self._assert_writable(self.runtime_dir)

    @staticmethod
    def _assert_writable(path: Path) -> None:
        temp_name = ""
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path, prefix=".write-test-", delete=False) as handle:
                temp_name = handle.name
                handle.write("ok\n")
        finally:
            if temp_name:
                try:
                    Path(temp_name).unlink()
                except FileNotFoundError:
                    pass

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        self.ensure()
        path = self._resolve_managed_path(path)
        self._write_json_to_path(path, payload)

    def _write_json_to_path(self, path: Path, payload: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_name = handle.name
        os.replace(temp_name, path)
        path.chmod(0o600)

    def _resolve_managed_path(self, path: Path) -> Path:
        if path.name == SESSION_FILE:
            return self.session_path
        if path.name == TOKEN_FILE:
            return self.token_path
        return path

    def read_json(self, path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except json.JSONDecodeError:
            return None

    def write_session(self, payload: dict[str, Any]) -> None:
        self.ensure()
        self._write_json_to_path(self.session_path, payload)

    def read_session(self) -> dict[str, Any] | None:
        self.ensure()
        return self.read_json(self.session_path)

    def remove_session(self) -> bool:
        self.ensure()
        return self._unlink(self.session_path)

    def cleanup_stale_session(self) -> dict[str, Any]:
        payload = self.read_session()
        if payload is None:
            removed = self._unlink(self.session_path)
            return {
                "removed": removed,
                "reason": "invalid-json" if removed else "absent",
                "killedProcesses": 0,
            }
        if payload.get("version") != 2 or not payload.get("sessionId"):
            removed = self.remove_session()
            return {
                "removed": removed,
                "reason": "invalid-manifest",
                "killedProcesses": 0,
            }
        return {
            "removed": False,
            "reason": "valid",
            "killedProcesses": 0,
        }

    def write_token(self, payload: dict[str, Any]) -> None:
        self.ensure()
        self._write_json_to_path(self.token_path, payload)

    def read_token(self) -> dict[str, Any] | None:
        self.ensure()
        return self.read_json(self.token_path)

    def remove_token(self) -> bool:
        self.ensure()
        return self._unlink(self.token_path)

    def write_event(self, event: dict[str, Any], level: str = "normal") -> None:
        self.ensure()
        payload = {"level": level, **event}
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(redact_payload(payload), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        self.events_path.chmod(0o600)

    def private_state_inventory(self) -> dict[str, Any]:
        return {
            "runtimeDir": str(self.runtime_dir),
            "sessionPath": str(self.session_path),
            "tokenPath": str(self.token_path),
            "eventsPath": str(self.events_path),
            "stateDir": str(self.state_dir),
            "logsDir": str(self.logs_dir),
            "storage": "tmpfs-or-runtime-dir",
        }

    @staticmethod
    def _unlink(path: Path) -> bool:
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
