import unittest

from agent.profile_schema import redacted_profile_template
from agent.route_policy import decide_route, failover_order


class RoutePolicyTests(unittest.TestCase):
    def test_private_targets_go_direct(self):
        profile = redacted_profile_template()

        self.assertEqual(decide_route("10.10.0.20:443", profile)["route"], "direct")
        self.assertEqual(decide_route("localhost:8080", profile)["route"], "direct")

    def test_domestic_hint_goes_direct(self):
        profile = redacted_profile_template()

        self.assertEqual(decide_route("example.com.cn:443", profile)["route"], "direct")

    def test_foreign_default_uses_new_route(self):
        profile = redacted_profile_template()

        self.assertEqual(decide_route("google.com:443", profile)["route"], "new")

    def test_failover_order_comes_from_profile(self):
        profile = redacted_profile_template()

        self.assertEqual(failover_order(profile), ["old", "new"])


if __name__ == "__main__":
    unittest.main()
