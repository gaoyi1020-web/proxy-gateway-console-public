import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.profile_crypto import write_encrypted_profile
from agent.profile_schema import redacted_profile_template
from agent.session_store import SessionStore
from agent.unlock_server import lock, unlock, unlock_status
from agent.usb_identity import recovery_manifest_template


PROFILE_PASSPHRASE = "test-passphrase"


def make_usb(root: Path, include_profile=True):
    (root / "manifest.json").write_text(json.dumps(recovery_manifest_template()), encoding="utf-8")
    if include_profile:
        (root / "profile").mkdir()
        write_encrypted_profile(redacted_profile_template(), root / "profile" / "profile.json.enc", PROFILE_PASSPHRASE)


class UnlockServerTests(unittest.TestCase):
    def test_unlock_requires_trusted_usb_profile(self):
        with tempfile.TemporaryDirectory() as runtime, tempfile.TemporaryDirectory() as usb:
            make_usb(Path(usb), include_profile=False)
            result = unlock(SessionStore(runtime), usb)

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")

    def test_unlock_creates_redacted_token_status_and_lock_removes_it(self):
        with tempfile.TemporaryDirectory() as runtime, tempfile.TemporaryDirectory() as usb:
            make_usb(Path(usb))
            store = SessionStore(runtime)
            result = unlock(store, usb, passphrase=PROFILE_PASSPHRASE)
            status = unlock_status(store, usb)
            locked = lock(store)

        self.assertTrue(result["ok"])
        self.assertNotIn("token", result["token"])
        self.assertTrue(result["token"]["profileLoaded"])
        self.assertEqual(status["state"], "unlocked")
        self.assertTrue(status["profileLoaded"])
        self.assertTrue(locked["removedToken"])

    def test_unlock_rejects_wrong_profile_passphrase(self):
        with tempfile.TemporaryDirectory() as runtime, tempfile.TemporaryDirectory() as usb:
            make_usb(Path(usb))
            result = unlock(SessionStore(runtime), usb, passphrase="wrong-passphrase")

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertIn("invalid", result["summary"])

    def test_unlock_status_expires_stale_token(self):
        with tempfile.TemporaryDirectory() as runtime:
            store = SessionStore(runtime)
            store.write_token({
                "token": "expired-token",
                "createdAt": "2026-05-03T00:00:00Z",
                "expiresAt": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
            })
            status = unlock_status(store)

        self.assertEqual(status["state"], "locked")
        self.assertFalse(status["tokenPresent"])
        self.assertTrue(status["tokenExpired"])


if __name__ == "__main__":
    unittest.main()
