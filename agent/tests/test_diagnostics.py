import tempfile
import unittest
import zipfile

from agent.diagnostics import export_diagnostics
from agent.session_store import SessionStore


class DiagnosticsTests(unittest.TestCase):
    def test_export_diagnostics_zip_is_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(tmp)
            store.write_session({"version": 2, "sessionId": "abc", "token": "secret-token"})
            store.write_event({"event": "test", "password": "secret-password"})
            result = export_diagnostics(store)

            with zipfile.ZipFile(result["path"]) as archive:
                names = archive.namelist()
                session = archive.read("session.redacted.json").decode("utf-8")
                events = archive.read("events.redacted.jsonl").decode("utf-8")

        self.assertTrue(result["ok"])
        self.assertIn("doctor.json", names)
        self.assertIn("[redacted]", session)
        self.assertIn("[redacted]", events)
        self.assertNotIn("secret-token", session)
        self.assertNotIn("secret-password", events)


if __name__ == "__main__":
    unittest.main()
