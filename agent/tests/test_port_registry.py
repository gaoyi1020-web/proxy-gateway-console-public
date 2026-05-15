import unittest

from agent.port_registry import PortRegistry, build_session_manifest


def fake_allocator():
    next_port = 40000

    def allocate(_host):
        nonlocal next_port
        next_port += 1
        return next_port

    return allocate


class PortRegistryTests(unittest.TestCase):
    def test_allocates_unique_loopback_ports(self):
        registry = PortRegistry(port_allocator=fake_allocator())
        first = registry.allocate("first")
        second = registry.allocate("second")

        self.assertEqual(first["host"], "127.0.0.1")
        self.assertEqual(second["host"], "127.0.0.1")
        self.assertNotEqual(first["port"], second["port"])
        self.assertGreater(first["port"], 0)
        self.assertGreater(second["port"], 0)

    def test_manifest_uses_dynamic_loopback_ports(self):
        manifest = build_session_manifest(session_id="test-session", registry=PortRegistry(port_allocator=fake_allocator()))

        self.assertEqual(manifest["version"], 2)
        self.assertEqual(manifest["sessionId"], "test-session")
        self.assertEqual(manifest["privacy"]["state"], "tmpfs")
        self.assertEqual(set(manifest["listeners"]), {"dashboard", "unlock", "httpProxy", "socksProxy", "controllerApi"})
        for listener in manifest["listeners"].values():
            self.assertEqual(listener["host"], "127.0.0.1")
            self.assertGreater(listener["port"], 0)

    def test_manifest_adds_lan_listener_only_when_requested(self):
        without_lan = build_session_manifest(
            session_id="without-lan",
            registry=PortRegistry(port_allocator=fake_allocator()),
            lan_host="10.10.0.10",
        )
        with_lan = build_session_manifest(
            session_id="with-lan",
            registry=PortRegistry(port_allocator=fake_allocator()),
            lan_host="10.10.0.10",
            include_lan=True,
        )

        self.assertNotIn("lanProxy", without_lan["listeners"])
        self.assertEqual(with_lan["listeners"]["lanProxy"]["host"], "10.10.0.10")
        self.assertGreater(with_lan["listeners"]["lanProxy"]["port"], 0)


if __name__ == "__main__":
    unittest.main()
