import json
import tempfile
import unittest
from pathlib import Path

from agent.usb_identity import detect_usb, recovery_manifest_template, validate_usb_manifest


class UsbIdentityTests(unittest.TestCase):
    def test_missing_usb_root_is_not_present(self):
        status = detect_usb("/tmp/proxy-gateway-missing-usb-root")

        self.assertFalse(status["present"])
        self.assertFalse(status["trusted"])

    def test_trusts_valid_non_secret_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "profile").mkdir()
            (root / "manifest.json").write_text(json.dumps(recovery_manifest_template()), encoding="utf-8")
            (root / "profile" / "profile.json.enc").write_text("encrypted-placeholder", encoding="utf-8")
            status = detect_usb(root)

        self.assertTrue(status["present"])
        self.assertTrue(status["trusted"])
        self.assertTrue(status["profilePresent"])

    def test_rejects_secret_like_manifest(self):
        manifest = recovery_manifest_template()
        manifest["token"] = "placeholder-token"
        errors = validate_usb_manifest(manifest)

        self.assertIn("manifest contains secret-like fields", errors)


if __name__ == "__main__":
    unittest.main()
