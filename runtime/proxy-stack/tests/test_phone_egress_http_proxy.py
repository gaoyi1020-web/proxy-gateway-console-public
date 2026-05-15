import socket
import unittest

from phone_egress_http_proxy import bind_address_for_source


class PhoneEgressProxyTests(unittest.TestCase):
    def test_ipv4_source_only_binds_ipv4_family(self):
        self.assertEqual(
            bind_address_for_source("172.20.10.2", socket.AF_INET),
            ("172.20.10.2", 0),
        )
        self.assertIsNone(bind_address_for_source("172.20.10.2", socket.AF_INET6))

    def test_ipv6_source_only_binds_ipv6_family(self):
        self.assertEqual(
            bind_address_for_source("2001:db8::2", socket.AF_INET6),
            ("2001:db8::2", 0, 0, 0),
        )
        self.assertIsNone(bind_address_for_source("2001:db8::2", socket.AF_INET))


if __name__ == "__main__":
    unittest.main()
