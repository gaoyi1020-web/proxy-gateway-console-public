import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_writes_session_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(tmp)
            store.write_session({"version": 2, "token": "secret-value"})

            self.assertEqual(store.read_session()["version"], 2)
            self.assertEqual(oct(store.session_path.stat().st_mode & 0o777), "0o600")

    def test_event_log_redacts_secret_like_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(tmp)
            store.write_event({"event": "test", "password": "secret", "message": "token=abc123"})
            text = Path(store.events_path).read_text(encoding="utf-8")

            self.assertIn("[redacted]", text)
            self.assertNotIn("abc123", text)
            self.assertNotIn("secret", text)

    def test_private_state_inventory_uses_runtime_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(tmp)
            inventory = store.private_state_inventory()

            self.assertEqual(inventory["runtimeDir"], tmp)
            self.assertTrue(inventory["sessionPath"].endswith("session.json"))

    def test_cleanup_stale_session_removes_invalid_manifest_without_killing_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(tmp)
            store.write_session({"version": 1})
            result = store.cleanup_stale_session()

            self.assertTrue(result["removed"])
            self.assertEqual(result["reason"], "invalid-manifest")
            self.assertEqual(result["killedProcesses"], 0)
            self.assertIsNone(store.read_session())

    def test_ensure_falls_back_when_runtime_subdirs_are_not_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "primary"
            primary.mkdir()
            fallback_base = Path(tmp) / "fallback"
            expected_fallback = fallback_base / f"proxy-gateway-{os.getuid()}"
            original_mkdir = Path.mkdir

            def mkdir_with_state_failure(path: Path, *args, **kwargs):
                if path == primary / "state":
                    raise OSError(errno.EROFS, "read-only filesystem")
                return original_mkdir(path, *args, **kwargs)

            store = SessionStore(primary)
            with mock.patch("agent.session_store.tempfile.gettempdir", return_value=str(fallback_base)):
                with mock.patch.object(Path, "mkdir", mkdir_with_state_failure):
                    store.ensure()

            self.assertEqual(store.runtime_dir, expected_fallback)
            self.assertTrue(store.state_dir.exists())
            self.assertTrue(store.logs_dir.exists())

    def test_write_session_uses_fallback_path_after_runtime_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "primary"
            primary.mkdir()
            fallback_base = Path(tmp) / "fallback"
            expected_fallback = fallback_base / f"proxy-gateway-{os.getuid()}"
            original_mkdir = Path.mkdir

            def mkdir_with_state_failure(path: Path, *args, **kwargs):
                if path == primary / "state":
                    raise OSError(errno.EROFS, "read-only filesystem")
                return original_mkdir(path, *args, **kwargs)

            store = SessionStore(primary)
            with mock.patch("agent.session_store.tempfile.gettempdir", return_value=str(fallback_base)):
                with mock.patch.object(Path, "mkdir", mkdir_with_state_failure):
                    store.write_session({"version": 2})

            self.assertEqual(store.runtime_dir, expected_fallback)
            self.assertTrue((expected_fallback / "session.json").exists())
            self.assertFalse((primary / "session.json").exists())
            self.assertEqual(store.read_session()["version"], 2)


if __name__ == "__main__":
    unittest.main()
