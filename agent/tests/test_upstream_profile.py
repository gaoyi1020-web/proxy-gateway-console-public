import unittest

from agent.profile_schema import validate_profile
from agent.upstream_profile import upstream_to_profile


class UpstreamProfileTests(unittest.TestCase):
    def test_sing_box_upstream_converts_to_profile_without_inline_secrets(self):
        upstream = {
            "final": "us",
            "outbounds": [
                {
                    "type": "shadowsocks",
                    "tag": "us",
                    "server": "203.0.113.10",
                    "server_port": 443,
                    "method": "2022-blake3-aes-128-gcm",
                    "password": "private-password",
                },
                {
                    "type": "shadowsocks",
                    "tag": "jp",
                    "server": "203.0.113.11",
                    "server_port": 443,
                    "method": "2022-blake3-aes-128-gcm",
                    "password": "private-password-2",
                },
            ],
        }

        profile = upstream_to_profile(upstream, name="converted")
        validated = validate_profile(profile)

        self.assertEqual(validated["name"], "converted")
        self.assertEqual(validated["routes"]["us"]["type"], "adapter")
        self.assertEqual(validated["routes"]["us"]["authRef"], "adapter:sing-box:us")
        self.assertEqual(validated["splitRules"]["foreign"], "us")
        self.assertEqual(validated["ui"]["defaultRegion"], "us")
        self.assertEqual([item["id"] for item in validated["ui"]["regions"]], ["us", "jp"])
        rendered = repr(validated)
        self.assertNotIn("203.0.113.10", rendered)
        self.assertNotIn("private-password", rendered)
        self.assertNotIn("server_port", rendered)
        self.assertNotIn("method", rendered)

    def test_sing_box_upstream_requires_usable_outbound_tags(self):
        with self.assertRaises(ValueError):
            upstream_to_profile({"final": "missing", "outbounds": [{"type": "direct"}]})


if __name__ == "__main__":
    unittest.main()
