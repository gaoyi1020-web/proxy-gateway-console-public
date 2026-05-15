from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

try:
    from .profile_crypto import ProfileCryptoError, profile_digest, profile_summary, read_encrypted_profile
    from .session_store import SessionStore
    from .usb_identity import detect_usb
    from .port_registry import utc_now_iso
except ImportError:
    from profile_crypto import ProfileCryptoError, profile_digest, profile_summary, read_encrypted_profile
    from session_store import SessionStore
    from usb_identity import detect_usb
    from port_registry import utc_now_iso


TOKEN_TTL_SECONDS = 900


def unlock_status(store: SessionStore, usb_root: str | None = None) -> dict[str, Any]:
    token = store.read_token()
    token_expired = False
    if token and _token_expired(token):
        store.remove_token()
        store.write_event({"event": "unlock-token-expired", "expiresAt": token.get("expiresAt", "")})
        token = None
        token_expired = True
    usb = detect_usb(usb_root)
    state = "unlocked" if token else "locked"
    if usb.get("state") in {"missing", "manifest_missing", "manifest_invalid", "untrusted"}:
        state = "blocked"
    return {
        "ok": True,
        "state": state,
        "bind": "127.0.0.1",
        "tokenPresent": bool(token),
        "tokenExpired": token_expired,
        "tokenExpiresAt": token.get("expiresAt") if token else "",
        "profileLoaded": bool(token and token.get("profileLoaded")),
        "profileSummary": token.get("profileSummary") if token else None,
        "profileDigest": token.get("profileDigest", "") if token else "",
        "usb": usb,
    }


def unlock(store: SessionStore, usb_root: str | None = None, passphrase: str = "") -> dict[str, Any]:
    usb = detect_usb(usb_root)
    if not usb.get("trusted"):
        return {
            "ok": False,
            "state": "blocked",
            "summary": "trusted recovery manifest is required before unlock",
            "usb": usb,
        }
    if not usb.get("profilePresent"):
        return {
            "ok": False,
            "state": "blocked",
            "summary": "encrypted profile/profile.json.enc is required before unlock",
            "usb": usb,
        }
    try:
        profile = read_encrypted_profile(usb["profilePath"], passphrase)
    except ProfileCryptoError as error:
        return {
            "ok": False,
            "state": "blocked",
            "summary": str(error),
            "usb": usb,
        }
    summary = profile_summary(profile)
    token = {
        "token": secrets.token_urlsafe(32),
        "createdAt": utc_now_iso(),
        "expiresInSeconds": TOKEN_TTL_SECONDS,
        "expiresAt": _expires_at_iso(TOKEN_TTL_SECONDS),
        "passphraseSupplied": bool(passphrase),
        "profileLoaded": True,
        "profileDigest": profile_digest(profile),
        "profileSummary": summary,
    }
    store.write_token(token)
    store.write_event({"event": "unlock", "state": "unlocked", "usbRoot": usb.get("root"), "profile": summary, "token": token["token"]})
    safe_token = {key: value for key, value in token.items() if key != "token"}
    return {
        "ok": True,
        "state": "unlocked",
        "summary": "encrypted profile loaded and unlock token created in private runtime state",
        "token": safe_token,
        "usb": usb,
    }


def lock(store: SessionStore) -> dict[str, Any]:
    removed = store.remove_token()
    store.write_event({"event": "lock", "removedToken": removed})
    return {
        "ok": True,
        "state": "locked",
        "removedToken": removed,
    }


def serve_unlock(store: SessionStore, usb_root: str | None = None, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/status":
                self._json(200, unlock_status(store, usb_root))
                return
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_unlock_html(unlock_status(store, usb_root)).encode("utf-8"))

        def do_POST(self) -> None:
            if self.path == "/api/unlock":
                payload = self._body_json()
                self._json(200, unlock(store, usb_root, str(payload.get("passphrase", ""))))
                return
            if self.path == "/api/lock":
                self._json(200, lock(store))
                return
            self._json(404, {"ok": False, "error": "not found"})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        def _body_json(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("content-length", "0"))
            except ValueError:
                length = 0
            if length <= 0:
                return {}
            try:
                raw = self.rfile.read(min(length, 16_384))
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}
            return payload if isinstance(payload, dict) else {}

    return ThreadingHTTPServer((host, port), Handler)


def _unlock_html(status: dict[str, Any]) -> str:
    usb = status.get("usb", {})
    state = status.get("state", "locked")
    usb_state = usb.get("state", "unknown")
    token = "present" if status.get("tokenPresent") else "absent"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Linux LAN Gateway</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #102033;
      --muted: #607086;
      --line: #d8e3ef;
      --panel: #ffffff;
      --ok: #15805d;
      --warn: #a05b00;
      --bg: #f6f8fb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 960px; margin: 0 auto; padding: 24px 16px; }}
    header {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 22px; }}
    h1 {{ margin: 0 0 4px; font-size: 24px; line-height: 1.15; }}
    p {{ margin: 0; color: var(--muted); font-size: 13px; }}
    .pill {{ border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; font-size: 12px; background: var(--panel); }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid var(--line); border-left: 3px solid var(--warn); border-radius: 8px; background: var(--panel); padding: 16px; min-height: 96px; }}
    .card.ok {{ border-left-color: var(--ok); }}
    .label {{ font-size: 12px; color: var(--muted); margin-bottom: 8px; }}
    .value {{ font-size: 18px; font-weight: 700; overflow-wrap: anywhere; }}
    .note {{ margin-top: 18px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 14px; }}
    @media (max-width: 640px) {{
      main {{ padding: 16px 8px; }}
      header {{ display: block; }}
      .pill {{ display: inline-block; margin-top: 12px; }}
      .grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 20px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Linux LAN Gateway</h1>
        <p>本地解锁入口，仅绑定 127.0.0.1。</p>
      </div>
      <div class="pill">read-only unlock surface</div>
    </header>
    <section class="grid" aria-label="unlock status">
      <article class="card {'ok' if state == 'unlocked' else ''}">
        <div class="label">解锁状态</div>
        <div class="value">{state}</div>
      </article>
      <article class="card {'ok' if usb.get('trusted') else ''}">
        <div class="label">配置介质</div>
        <div class="value">{usb_state}</div>
      </article>
      <article class="card">
        <div class="label">会话令牌</div>
        <div class="value">{token}</div>
      </article>
      <article class="card ok">
        <div class="label">绑定地址</div>
        <div class="value">127.0.0.1</div>
      </article>
    </section>
    <section class="note">
      <p>页面不显示密钥、服务器认证或完整日志。当前解锁入口可使用可信恢复介质和加密 profile 文件。</p>
    </section>
  </main>
</body>
</html>"""


def _expires_at_iso(ttl_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat().replace("+00:00", "Z")


def _token_expired(token: dict[str, Any]) -> bool:
    expires_at = token.get("expiresAt")
    if not isinstance(expires_at, str) or not expires_at:
        return True
    try:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return parsed <= datetime.now(timezone.utc)
