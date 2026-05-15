import json
import tempfile
import unittest
from pathlib import Path

from agent.usb_identity import detect_usb, trusted_manifest_template


class UsbIdentityTests(unittest.TestCase):
    def test_missing_usb_root_is_not_present(self):
        status = detect_usb("/tmp/proxy-gateway-missing-usb-root")

        self.assertFalse(status["present"])
        self.assertFalse(status["trusted"])

    def test_trusts_valid_non_secret_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "profile").mkdir()
            (root / "manifest.json").write_text(json.dumps(trusted_manifest_template()), encoding="utf-8")
            (root / "profile" / "profile.json.enc").write_text("encrypted-placeholder", encoding="utf-8")
            status = detect_usb(root)

        self.assertTrue(status["present"])
        self.assertTrue(status["trusted"])
        self.assertTrue(status["profilePresent"])

    def test_rejects_secret_like_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = trusted_manifest_template()
            manifest["token"] = "secret"
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            status = detect_usb(root)

        self.assertFalse(status["trusted"])
        self.assertIn("manifest contains secret-like fields", status["errors"])


if __name__ == "__main__":
    unittest.main()
