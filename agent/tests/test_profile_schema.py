import unittest

from agent.profile_schema import ProfileValidationError, migrate_v1_runtime, redacted_profile_template, validate_profile


class ProfileSchemaTests(unittest.TestCase):
    def test_accepts_redacted_template(self):
        profile = validate_profile(redacted_profile_template())

        self.assertEqual(profile["version"], 2)
        self.assertIn("old", profile["routes"])
        self.assertEqual(profile["routes"]["failover"]["order"], ["old", "new"])

    def test_rejects_unsupported_version(self):
        profile = redacted_profile_template()
        profile["version"] = 1

        with self.assertRaises(ProfileValidationError):
            validate_profile(profile)

    def test_rejects_missing_failover_route(self):
        profile = redacted_profile_template()
        profile["routes"]["failover"]["order"] = ["old", "missing"]

        with self.assertRaises(ProfileValidationError):
            validate_profile(profile)

    def test_rejects_inline_secret_fields(self):
        profile = redacted_profile_template()
        profile["routes"]["new"]["password"] = "real-secret"

        with self.assertRaises(ProfileValidationError):
            validate_profile(profile)

    def test_migrates_v1_runtime_without_secret_values(self):
        profile = migrate_v1_runtime(
            {
                "ports": [
                    {"id": "old-http", "host": "127.0.0.1", "port": 8118},
                    {"id": "new-http", "host": "127.0.0.1", "port": 18122},
                    {"id": "failover", "host": "127.0.0.1", "port": 18180},
                ],
                "iphone_lan_proxy": {"setting": "10.10.0.10:18181"},
            }
        )

        self.assertEqual(profile["routes"]["old"]["endpoint"], "http://127.0.0.1:8118")
        self.assertEqual(profile["routes"]["new"]["endpoint"], "http://127.0.0.1:18122")
        self.assertEqual(profile["routes"]["lanProxy"]["settingHint"], "10.10.0.10:18181")

    def test_accepts_ui_region_metadata(self):
        profile = redacted_profile_template()
        profile["ui"] = {
            "defaultRegion": "new",
            "regions": [
                {"id": "old", "label": "Old"},
                {"id": "new", "label": "New"},
            ],
        }

        validated = validate_profile(profile)

        self.assertEqual(validated["ui"]["defaultRegion"], "new")
        self.assertEqual(validated["ui"]["regions"][1]["label"], "New")

    def test_rejects_ui_default_region_missing_route(self):
        profile = redacted_profile_template()
        profile["ui"] = {
            "defaultRegion": "missing",
            "regions": [{"id": "missing", "label": "Missing"}],
        }

        with self.assertRaises(ProfileValidationError):
            validate_profile(profile)

    def test_rejects_ui_region_without_route(self):
        profile = redacted_profile_template()
        profile["ui"] = {
            "defaultRegion": "new",
            "regions": [{"id": "ghost", "label": "Ghost"}],
        }

        with self.assertRaises(ProfileValidationError):
            validate_profile(profile)


if __name__ == "__main__":
    unittest.main()
