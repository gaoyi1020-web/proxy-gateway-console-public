import tempfile
import unittest
from pathlib import Path

from agent.profile_crypto import (
    ProfileCryptoError,
    copy_encrypted_profile,
    encrypted_profile_status,
    profile_digest,
    read_encrypted_profile,
    write_encrypted_profile,
)
from agent.profile_schema import redacted_profile_template


class ProfileCryptoTests(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip_and_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json.enc"
            profile = redacted_profile_template()
            result = write_encrypted_profile(profile, path, "passphrase")
            decrypted = read_encrypted_profile(path, "passphrase")

        self.assertTrue(result["ok"])
        self.assertEqual(decrypted["version"], 2)
        self.assertEqual(result["profileDigest"], profile_digest(decrypted))

    def test_wrong_passphrase_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json.enc"
            write_encrypted_profile(redacted_profile_template(), path, "passphrase")

            with self.assertRaises(ProfileCryptoError):
                read_encrypted_profile(path, "wrong")

    def test_encrypted_file_does_not_expose_route_names_as_plaintext(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json.enc"
            write_encrypted_profile(redacted_profile_template(), path, "passphrase")
            text = path.read_text(encoding="utf-8")

        self.assertNotIn("failover", text)
        self.assertNotIn("lanProxy", text)

    def test_local_profile_status_reads_encrypted_source_without_decrypting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json.enc"
            write_encrypted_profile(redacted_profile_template(), path, "passphrase")

            status = encrypted_profile_status(path)

        self.assertTrue(status["present"])
        self.assertEqual(status["state"], "encrypted_profile_present")
        self.assertEqual(status["path"], str(path))

    def test_copy_encrypted_profile_preserves_decryptable_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "usb" / "profile" / "profile.json.enc"
            target = Path(tmp) / "local" / "profile.json.enc"
            write_encrypted_profile(redacted_profile_template(), source, "passphrase")

            result = copy_encrypted_profile(source, target)
            decrypted = read_encrypted_profile(target, "passphrase")

        self.assertTrue(result["ok"])
        self.assertEqual(decrypted["version"], 2)
        self.assertEqual(result["path"], str(target))

    def test_copy_encrypted_profile_refuses_plaintext_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "profile.json.enc"
            target = Path(tmp) / "profile.json"
            write_encrypted_profile(redacted_profile_template(), source, "passphrase")

            with self.assertRaises(ProfileCryptoError):
                copy_encrypted_profile(source, target)

    def test_adapter_route_profile_roundtrip_without_inline_adapter_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json.enc"
            profile = redacted_profile_template()
            profile["routes"]["remote-us"] = {
                "type": "adapter",
                "adapterKind": "sing-box-outbound",
                "authRef": "adapter:sing-box:remote-us",
                "label": "remote-us",
            }
            profile["splitRules"]["foreign"] = "remote-us"
            profile["ui"] = {
                "defaultRegion": "remote-us",
                "regions": [{"id": "remote-us", "label": "remote-us"}],
            }

            result = write_encrypted_profile(profile, path, "passphrase")
            decrypted = read_encrypted_profile(path, "passphrase")

        self.assertTrue(result["ok"])
        self.assertEqual(decrypted["routes"]["remote-us"]["type"], "adapter")
        self.assertEqual(decrypted["routes"]["remote-us"]["adapterKind"], "sing-box-outbound")
        self.assertNotIn("password", str(decrypted))


if __name__ == "__main__":
    unittest.main()
