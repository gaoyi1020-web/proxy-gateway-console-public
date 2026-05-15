from __future__ import annotations

import socket
import uuid
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any


DEFAULT_LOOPBACK_HOST = "127.0.0.1"
DEFAULT_LISTENERS = ("dashboard", "unlock", "httpProxy", "socksProxy", "controllerApi")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PortRegistry:
    def __init__(self, port_allocator: Callable[[str], int] | None = None) -> None:
        self._allocated: set[tuple[str, int]] = set()
        self._port_allocator = port_allocator or self._allocate_ephemeral

    def allocate(self, listener_id: str, host: str = DEFAULT_LOOPBACK_HOST) -> dict[str, Any]:
        if not listener_id:
            raise ValueError("listener_id is required")
        for _ in range(64):
            port = self._port_allocator(host)
            key = (host, port)
            if key not in self._allocated:
                self._allocated.add(key)
                return {"id": listener_id, "host": host, "port": port}
        raise RuntimeError(f"could not allocate a free port for {listener_id}")

    @staticmethod
    def _allocate_ephemeral(host: str) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, 0))
            return int(sock.getsockname()[1])


def build_session_manifest(
    *,
    session_id: str | None = None,
    registry: PortRegistry | None = None,
    lan_host: str | None = None,
    include_lan: bool = False,
) -> dict[str, Any]:
    ports = registry or PortRegistry()
    listeners = {
        listener_id: _listener_payload(ports.allocate(listener_id))
        for listener_id in DEFAULT_LISTENERS
    }
    if include_lan and lan_host:
        listeners["lanProxy"] = _listener_payload(ports.allocate("lanProxy", lan_host))

    return {
        "version": 2,
        "sessionId": session_id or uuid.uuid4().hex,
        "createdAt": utc_now_iso(),
        "listeners": listeners,
        "privacy": {
            "state": "tmpfs",
            "logs": "redacted",
        },
    }


def _listener_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {"host": item["host"], "port": item["port"]}
