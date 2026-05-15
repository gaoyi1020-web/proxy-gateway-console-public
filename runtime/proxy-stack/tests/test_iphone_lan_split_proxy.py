import importlib.util
import sys
import unittest
from ipaddress import ip_network
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "iphone_lan_split_proxy.py"


def load_module():
    spec = importlib.util.spec_from_file_location("iphone_lan_split_proxy", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RouteDecisionTests(unittest.TestCase):
    def test_directs_private_and_cn_ips(self):
        module = load_module()
        networks = [ip_network("203.0.113.0/24")]

        private = module.choose_route("10.10.0.30", networks, [], [])
        cn = module.choose_route("203.0.113.10", networks, [], [])

        self.assertEqual(private.mode, "direct")
        self.assertEqual(private.reason, "private")
        self.assertEqual(cn.mode, "direct")
        self.assertEqual(cn.reason, "cn-ip")

    def test_proxies_foreign_ips(self):
        module = load_module()
        decision = module.choose_route("8.8.8.8", [], [], [])

        self.assertEqual(decision.mode, "proxy")
        self.assertEqual(decision.reason, "foreign-ip")

    def test_uses_resolved_ips_for_domains(self):
        module = load_module()
        networks = [ip_network("203.0.113.0/24")]

        direct = module.choose_route("cdn.example", networks, [], [], resolver=lambda host: ["203.0.113.10"])
        proxy = module.choose_route("video.example", networks, [], [], resolver=lambda host: ["8.8.8.8"])

        self.assertEqual(direct.mode, "direct")
        self.assertEqual(direct.reason, "cn-ip")
        self.assertEqual(proxy.mode, "proxy")
        self.assertEqual(proxy.reason, "foreign-ip")

    def test_force_proxy_wins_before_resolution(self):
        module = load_module()
        decision = module.choose_route(
            "rr4---sn-o097znss.googlevideo.com",
            [ip_network("203.0.113.0/24")],
            [],
            ["googlevideo.com"],
            resolver=lambda host: ["203.0.113.10"],
        )

        self.assertEqual(decision.mode, "proxy")
        self.assertEqual(decision.reason, "force-proxy")


if __name__ == "__main__":
    unittest.main()
