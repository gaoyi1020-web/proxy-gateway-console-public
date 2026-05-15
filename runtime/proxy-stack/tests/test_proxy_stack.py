import importlib.util
import json
import tempfile
import unittest
from ipaddress import ip_interface
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "proxy_stack.py"


def load_module():
    spec = importlib.util.spec_from_file_location("proxy_stack", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HotspotPreflightTests(unittest.TestCase):
    def test_blocks_when_hotspot_uses_current_default_wifi(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            joined = " ".join(args)
            if "connection show GY-Hotspot" in joined and "connection.interface-name" in joined:
                return {"ok": True, "stdout": "wlp0s20f3", "stderr": "", "code": 0}
            if "connection show GY-Hotspot" in joined and "802-11-wireless.mode" in joined:
                return {"ok": True, "stdout": "ap", "stderr": "", "code": 0}
            if args[:3] == ["ip", "route", "get"]:
                return {"ok": True, "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3 src 10.10.0.50", "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "-t", "-f"]:
                return {"ok": True, "stdout": "wlp0s20f3:wifi:connected:CMCC-NHE9", "stderr": "", "code": 0}
            return {"ok": False, "stdout": "", "stderr": joined, "code": 1}

        module.run = fake_run

        result = module.hotspot_preflight("GY-Hotspot")

        self.assertFalse(result["allowed"])
        self.assertEqual(result["risk"], "would_disconnect_upstream")
        self.assertEqual(result["hotspot_interface"], "wlp0s20f3")
        self.assertEqual(result["default_route_interface"], "wlp0s20f3")

    def test_allows_when_upstream_default_route_uses_another_interface(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            joined = " ".join(args)
            if "connection show GY-Hotspot" in joined and "connection.interface-name" in joined:
                return {"ok": True, "stdout": "wlp0s20f3", "stderr": "", "code": 0}
            if "connection show GY-Hotspot" in joined and "802-11-wireless.mode" in joined:
                return {"ok": True, "stdout": "ap", "stderr": "", "code": 0}
            if args[:3] == ["ip", "route", "get"]:
                return {"ok": True, "stdout": "8.8.8.8 via 192.168.1.1 dev enx001122334455 src 192.168.1.20", "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "-t", "-f"]:
                return {"ok": True, "stdout": "enx001122334455:ethernet:connected:USB Ethernet", "stderr": "", "code": 0}
            return {"ok": False, "stdout": "", "stderr": joined, "code": 1}

        module.run = fake_run

        result = module.hotspot_preflight("GY-Hotspot")

        self.assertTrue(result["allowed"])
        self.assertEqual(result["risk"], "ok")
        self.assertEqual(result["hotspot_interface"], "wlp0s20f3")
        self.assertEqual(result["default_route_interface"], "enx001122334455")

    def test_safe_start_refuses_to_activate_blocked_hotspot(self):
        module = load_module()
        calls = []

        def fake_run(args, timeout=20, env=None):
            calls.append(args)
            joined = " ".join(args)
            if "connection show GY-Hotspot" in joined and "connection.interface-name" in joined:
                return {"ok": True, "stdout": "wlp0s20f3", "stderr": "", "code": 0}
            if "connection show GY-Hotspot" in joined and "802-11-wireless.mode" in joined:
                return {"ok": True, "stdout": "ap", "stderr": "", "code": 0}
            if args[:3] == ["ip", "route", "get"]:
                return {"ok": True, "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3 src 10.10.0.50", "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "-t", "-f"]:
                return {"ok": True, "stdout": "wlp0s20f3:wifi:connected:CMCC-NHE9", "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "connection", "up"]:
                return {"ok": True, "stdout": "started", "stderr": "", "code": 0}
            return {"ok": False, "stdout": "", "stderr": joined, "code": 1}

        module.run = fake_run

        result = module.hotspot_start_safe("GY-Hotspot")

        self.assertFalse(result["ok"])
        self.assertEqual(result["preflight"]["risk"], "would_disconnect_upstream")
        self.assertNotIn(["nmcli", "connection", "up", "GY-Hotspot"], calls)

    def test_gui_guard_status_detects_locked_connection(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            if args[:3] == ["nmcli", "-g", "connection.permissions"]:
                return {"ok": True, "stdout": "user\\:root", "stderr": "", "code": 0}
            return {"ok": False, "stdout": "", "stderr": "unexpected", "code": 1}

        module.run = fake_run

        result = module.hotspot_gui_guard_status("GY-Hotspot")

        self.assertTrue(result["enabled"])
        self.assertEqual(result["permissions"], "user:root")

    def test_gui_guard_enable_sets_blocked_permission(self):
        module = load_module()
        calls = []
        permissions = {"value": "--"}

        def fake_run(args, timeout=20, env=None):
            calls.append(args)
            if args[:3] == ["nmcli", "-g", "connection.permissions"]:
                return {"ok": True, "stdout": permissions["value"], "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "connection", "modify"]:
                permissions["value"] = args[-1]
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}
            return {"ok": False, "stdout": "", "stderr": "unexpected", "code": 1}

        module.run = fake_run

        result = module.hotspot_gui_guard_enable("GY-Hotspot")

        self.assertTrue(result["ok"])
        self.assertIn(
            ["nmcli", "connection", "modify", "GY-Hotspot", "connection.permissions", "user:root"],
            calls,
        )

    def test_gui_guard_status_uses_marker_when_locked_profile_is_hidden(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            if args[:3] == ["nmcli", "-g", "connection.permissions"]:
                return {"ok": False, "stdout": "", "stderr": "Error: GY-Hotspot - no such connection profile.", "code": 10}
            return {"ok": False, "stdout": "", "stderr": "unexpected", "code": 1}

        module.run = fake_run

        with tempfile.TemporaryDirectory() as tmp:
            module.GUI_GUARD_MARKER = Path(tmp) / "hotspot-gui-guard.json"
            module.GUI_GUARD_MARKER.write_text('{"connection":"GY-Hotspot","enabled":true,"permissions":"user:root"}')

            result = module.hotspot_gui_guard_status("GY-Hotspot")

        self.assertTrue(result["enabled"])
        self.assertEqual(result["source"], "marker_hidden_profile")

    def test_preflight_reports_gui_locked_when_profile_is_hidden_by_guard(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            if "connection show GY-Hotspot" in " ".join(args):
                return {"ok": False, "stdout": "", "stderr": "Error: GY-Hotspot - no such connection profile.", "code": 10}
            if args[:3] == ["ip", "route", "get"]:
                return {"ok": True, "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3 src 10.10.0.50", "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "-t", "-f"]:
                return {"ok": True, "stdout": "wlp0s20f3:wifi:connected:CMCC-NHE9", "stderr": "", "code": 0}
            return {"ok": False, "stdout": "", "stderr": "unexpected", "code": 1}

        module.run = fake_run

        with tempfile.TemporaryDirectory() as tmp:
            module.GUI_GUARD_MARKER = Path(tmp) / "hotspot-gui-guard.json"
            module.GUI_GUARD_MARKER.write_text('{"connection":"GY-Hotspot","enabled":true,"permissions":"user:root"}')

            result = module.hotspot_preflight("GY-Hotspot")

        self.assertFalse(result["allowed"])
        self.assertEqual(result["risk"], "gui_locked")

    def test_safe_start_reports_root_required_when_gui_guard_locked_and_preflight_allows(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            joined = " ".join(args)
            if "connection show GY-Hotspot" in joined and "connection.interface-name" in joined:
                return {"ok": True, "stdout": "wlp0s20f3", "stderr": "", "code": 0}
            if "connection show GY-Hotspot" in joined and "802-11-wireless.mode" in joined:
                return {"ok": True, "stdout": "ap", "stderr": "", "code": 0}
            if args[:3] == ["ip", "route", "get"]:
                return {"ok": True, "stdout": "8.8.8.8 via 192.168.1.1 dev enx001122334455 src 192.168.1.20", "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "-t", "-f"]:
                return {"ok": True, "stdout": "enx001122334455:ethernet:connected:USB Ethernet", "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "-g", "connection.permissions"]:
                return {"ok": True, "stdout": "user\\:root", "stderr": "", "code": 0}
            if args[:3] == ["nmcli", "connection", "up"]:
                self.fail("safe start should not call nmcli up while GUI guard is locked for non-root")
            return {"ok": False, "stdout": "", "stderr": joined, "code": 1}

        module.run = fake_run
        module.os.geteuid = lambda: 1000

        result = module.hotspot_start_safe("GY-Hotspot")

        self.assertFalse(result["ok"])
        self.assertEqual(result["risk"], "root_required")


class PhoneTetherGuardTests(unittest.TestCase):
    def test_detects_iphone_tether_driver(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "drivers" / "ipheth").mkdir(parents=True)
            (root / "enxiphone" / "device").mkdir(parents=True)
            (root / "enxiphone" / "device" / "driver").symlink_to(root / "drivers" / "ipheth")
            module.SYS_CLASS_NET = root

            result = module.phone_tether_guard_plan("enxiphone", "iPhone USB")

        self.assertTrue(result["matched"])
        self.assertEqual(result["driver"], "ipheth")

    def test_ignores_normal_wifi_driver(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "drivers" / "iwlwifi").mkdir(parents=True)
            (root / "wlp0s20f3" / "device").mkdir(parents=True)
            (root / "wlp0s20f3" / "device" / "driver").symlink_to(root / "drivers" / "iwlwifi")
            module.SYS_CLASS_NET = root

            result = module.phone_tether_guard_plan("wlp0s20f3", "CMCC-NHE9")

        self.assertFalse(result["matched"])
        self.assertEqual(result["driver"], "iwlwifi")

    def test_apply_demotes_phone_tether_default_routes(self):
        module = load_module()
        calls = []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.NETWORK_EVENTS_FILE = root / "network-events.json"
            module.UPSTREAM_POLICY_FILE = root / "upstream-policy.json"
            (root / "drivers" / "rndis_host").mkdir(parents=True)
            (root / "usb0" / "device").mkdir(parents=True)
            (root / "usb0" / "device" / "driver").symlink_to(root / "drivers" / "rndis_host")
            module.SYS_CLASS_NET = root

            def fake_run(args, timeout=20, env=None):
                calls.append(args)
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}

            module.run = fake_run

            result = module.phone_tether_guard_apply("usb0", "Android USB")

        self.assertTrue(result["ok"])
        self.assertIn(
            [
                "nmcli",
                "connection",
                "modify",
                "Android USB",
                "ipv4.never-default",
                "yes",
                "ipv6.never-default",
                "yes",
                "ipv4.route-metric",
                "9000",
                "ipv6.route-metric",
                "9000",
            ],
            calls,
        )

    def test_apply_records_pending_prompt_event_for_phone_tether(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.NETWORK_EVENTS_FILE = root / "network-events.json"
            module.UPSTREAM_POLICY_FILE = root / "upstream-policy.json"
            (root / "drivers" / "ipheth").mkdir(parents=True)
            (root / "enxiphone" / "device").mkdir(parents=True)
            (root / "enxiphone" / "device" / "driver").symlink_to(root / "drivers" / "ipheth")
            module.SYS_CLASS_NET = root

            def fake_run(args, timeout=20, env=None):
                if args[:3] == ["ip", "route", "get"]:
                    return {"ok": True, "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3", "stderr": "", "code": 0}
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}

            module.run = fake_run

            result = module.phone_tether_guard_apply("enxiphone", "iPhone USB")
            events = module.network_events_json()["events"]

        self.assertTrue(result["ok"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "phone_tether_detected")
        self.assertEqual(events[0]["status"], "pending")
        self.assertEqual(events[0]["interface"], "enxiphone")
        self.assertEqual(events[0]["connection"], "iPhone USB")

    def test_upstream_select_use_phone_once_keeps_host_default_route_demoted_and_returns_egress_plan(self):
        module = load_module()
        calls = []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.NETWORK_EVENTS_FILE = root / "network-events.json"
            module.UPSTREAM_POLICY_FILE = root / "upstream-policy.json"
            (root / "drivers" / "ipheth").mkdir(parents=True)
            (root / "enxiphone" / "device").mkdir(parents=True)
            (root / "enxiphone" / "device" / "driver").symlink_to(root / "drivers" / "ipheth")
            module.SYS_CLASS_NET = root

            def fake_run(args, timeout=20, env=None):
                calls.append(args)
                if args[:3] == ["ip", "route", "get"]:
                    return {"ok": True, "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3", "stderr": "", "code": 0}
                if args[:4] == ["nmcli", "-f", "IP4", "device"]:
                    return {
                        "ok": True,
                        "stdout": "\n".join([
                            "IP4.ADDRESS[1]:                         172.20.10.2/28",
                            "IP4.GATEWAY:                            --",
                            "IP4.DNS[1]:                             172.20.10.1",
                        ]),
                        "stderr": "",
                        "code": 0,
                    }
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}

            module.run = fake_run

            event_result = module.phone_tether_guard_apply("enxiphone", "iPhone USB")
            event_id = event_result["event"]["id"]
            result = module.upstream_select(event_id, "use-phone-once")
            events = module.network_events_json()["events"]

        self.assertTrue(result["ok"])
        self.assertIn(
            [
                "nmcli",
                "connection",
                "modify",
                "iPhone USB",
                "ipv4.never-default",
                "yes",
                "ipv6.never-default",
                "yes",
                "ipv4.route-metric",
                "9000",
                "ipv6.route-metric",
                "9000",
            ],
            calls,
        )
        self.assertEqual(result["egress_plan"]["listen"], "127.0.0.1:18190")
        self.assertEqual(events[0]["status"], "resolved")
        self.assertEqual(events[0]["decision"], "use-phone-once")

    def test_network_events_detects_phone_interface_without_nm_connection(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.NETWORK_EVENTS_FILE = root / "network-events.json"
            module.UPSTREAM_POLICY_FILE = root / "upstream-policy.json"
            (root / "drivers" / "ipheth").mkdir(parents=True)
            (root / "enxipad" / "device").mkdir(parents=True)
            (root / "enxipad" / "device" / "driver").symlink_to(root / "drivers" / "ipheth")
            (root / "enxipad" / "carrier").write_text("0\n")
            (root / "enxipad" / "operstate").write_text("down\n")
            module.SYS_CLASS_NET = root

            def fake_run(args, timeout=20, env=None):
                if args[:3] == ["nmcli", "-g", "GENERAL.CONNECTION"]:
                    return {"ok": True, "stdout": "--", "stderr": "", "code": 0}
                if args[:3] == ["ip", "route", "get"]:
                    return {"ok": True, "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3", "stderr": "", "code": 0}
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}

            module.run = fake_run

            result = module.network_events_json()

        self.assertEqual(len(result["pending"]), 1)
        self.assertEqual(result["pending"][0]["interface"], "enxipad")
        self.assertEqual(result["pending"][0]["connection"], "")
        self.assertFalse(result["pending"][0]["connection_known"])
        self.assertFalse(result["pending"][0]["carrier"])

    def test_upstream_select_refuses_use_phone_when_connection_is_unknown(self):
        module = load_module()
        calls = []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.NETWORK_EVENTS_FILE = root / "network-events.json"
            module.UPSTREAM_POLICY_FILE = root / "upstream-policy.json"
            module.write_network_event_store({
                "events": [{
                    "id": "evt-ipad",
                    "type": "phone_tether_detected",
                    "status": "pending",
                    "interface": "enxipad",
                    "connection": "",
                    "driver": "ipheth",
                }]
            })

            def fake_run(args, timeout=20, env=None):
                calls.append(args)
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}

            module.run = fake_run

            result = module.upstream_select("evt-ipad", "use-phone-once")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "phone_link_not_ready")
        self.assertNotIn(["nmcli", "connection", "modify", ""], calls)

    def test_ignore_once_suppresses_repeat_prompt_until_device_is_absent(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.NETWORK_EVENTS_FILE = root / "network-events.json"
            module.UPSTREAM_POLICY_FILE = root / "upstream-policy.json"
            driver_root = root / "drivers" / "ipheth"
            iface_root = root / "enxphone"
            driver_root.mkdir(parents=True)
            (iface_root / "device").mkdir(parents=True)
            (iface_root / "device" / "driver").symlink_to(driver_root)
            (iface_root / "carrier").write_text("1\n")
            (iface_root / "operstate").write_text("up\n")
            module.SYS_CLASS_NET = root

            def fake_run(args, timeout=20, env=None):
                if args[:3] == ["nmcli", "-g", "GENERAL.CONNECTION"]:
                    return {"ok": True, "stdout": "Phone USB", "stderr": "", "code": 0}
                if args[:3] == ["ip", "route", "get"]:
                    return {"ok": True, "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3", "stderr": "", "code": 0}
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}

            module.run = fake_run

            first = module.network_events_json()
            event_id = first["pending"][0]["id"]
            module.upstream_select(event_id, "ignore-once")
            second = module.network_events_json()

        self.assertEqual(second["pending"], [])
        self.assertEqual(len(second["events"]), 1)
        self.assertEqual(second["events"][0]["status"], "resolved")
        self.assertTrue(second["events"][0]["present"])


class PhoneEgressPortTests(unittest.TestCase):
    def test_phone_egress_plan_uses_phone_ip_and_dns_gateway_without_default_route(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            if args[:4] == ["nmcli", "-f", "IP4", "device"]:
                return {
                    "ok": True,
                    "stdout": "\n".join([
                        "IP4.ADDRESS[1]:                         172.20.10.2/28",
                        "IP4.GATEWAY:                            --",
                        "IP4.DNS[1]:                             172.20.10.1",
                    ]),
                    "stderr": "",
                    "code": 0,
                }
            return {"ok": False, "stdout": "", "stderr": "unexpected", "code": 1}

        module.run = fake_run

        result = module.phone_egress_plan("enxphone", "有线连接 1")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source_ip"], "172.20.10.2")
        self.assertEqual(result["gateway"], "172.20.10.1")
        self.assertEqual(result["network"], str(ip_interface("172.20.10.2/28").network))

    def test_current_phone_egress_plan_uses_ready_present_phone_without_pending_event(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.NETWORK_EVENTS_FILE = root / "network-events.json"
            module.UPSTREAM_POLICY_FILE = root / "upstream-policy.json"
            driver_root = root / "drivers" / "ipheth"
            iface_root = root / "enxphone"
            driver_root.mkdir(parents=True)
            (iface_root / "device").mkdir(parents=True)
            (iface_root / "device" / "driver").symlink_to(driver_root)
            (iface_root / "carrier").write_text("1\n")
            (iface_root / "operstate").write_text("up\n")
            module.SYS_CLASS_NET = root

            def fake_run(args, timeout=20, env=None):
                if args[:3] == ["nmcli", "-g", "GENERAL.CONNECTION"]:
                    return {"ok": True, "stdout": "Phone USB", "stderr": "", "code": 0}
                if args[:4] == ["nmcli", "-f", "IP4", "device"]:
                    return {
                        "ok": True,
                        "stdout": "\n".join([
                            "IP4.ADDRESS[1]:                         172.20.10.2/28",
                            "IP4.GATEWAY:                            --",
                            "IP4.DNS[1]:                             172.20.10.1",
                        ]),
                        "stderr": "",
                        "code": 0,
                    }
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}

            module.run = fake_run

            result = module.current_phone_egress_plan()

        self.assertTrue(result["ok"])
        self.assertEqual(result["interface"], "enxphone")
        self.assertEqual(result["connection"], "Phone USB")

    def test_phone_egress_route_commands_do_not_change_main_default_route(self):
        module = load_module()
        calls = []

        plan = {
            "ok": True,
            "interface": "enxphone",
            "source_ip": "172.20.10.2",
            "gateway": "172.20.10.1",
            "network": "172.20.10.0/28",
            "table": 18190,
            "priority": 18190,
        }

        def fake_run(args, timeout=20, env=None):
            calls.append(args)
            if args[:3] == ["ip", "rule", "show"]:
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}
            return {"ok": True, "stdout": "", "stderr": "", "code": 0}

        module.run = fake_run

        result = module.phone_egress_root_apply_from_plan(plan)

        self.assertTrue(result["ok"])
        self.assertIn(
            ["ip", "route", "replace", "default", "via", "172.20.10.1", "dev", "enxphone", "table", "18190"],
            calls,
        )
        self.assertIn(
            ["ip", "rule", "add", "from", "172.20.10.2/32", "table", "18190", "priority", "18190"],
            calls,
        )
        self.assertNotIn(["ip", "route", "replace", "default", "via", "172.20.10.1", "dev", "enxphone"], calls)


class SelfCheckTests(unittest.TestCase):
    def base_status(self):
        return {
            "generated_at": "2026-05-03 19:00:00 +0800",
            "services": [
                {"name": "proxy-failover.service", "scope": "user", "state": "active", "enabled": "enabled"},
                {"name": "privoxy.service", "scope": "system", "state": "active", "enabled": "enabled"},
            ],
            "ports": [
                {"id": "old-http", "host": "127.0.0.1", "port": 8118, "open": True},
                {"id": "failover", "host": "127.0.0.1", "port": 18180, "open": True},
                {"id": "iphone-lan", "host": "LAN", "port": 18181, "open": True},
            ],
            "iphone_lan_proxy": {
                "server": "10.10.0.10",
                "port": 18181,
                "setting": "10.10.0.10:18181",
                "target": "CN/private direct, foreign -> 127.0.0.1:18122",
                "firewall": {"status": "effective_open", "summary": "recent LAN client reached the bridge"},
                "recent_clients": [{"ip": "10.10.0.20", "port": 62791, "local": False}],
                "recent_upstreams": [{"target": "captive.apple.com:443", "route": "new"}],
            },
            "nft": {"state": "loaded", "detail": "table inet hotspot_split"},
            "hotspot_preflight": {
                "allowed": True,
                "risk": "ok",
                "message": "safe",
                "default_route_interface": "enx001122334455",
            },
            "network_events": {"pending": [], "events": []},
            "dns_decisions": {
                "domestic": "direct DNS www.baidu.com",
                "foreign": "remote DNS retry www.google.com",
            },
        }

    def prepare_self_check(self, module, status=None):
        module.status_json = lambda: status or self.base_status()
        module.service_state = lambda name, user: "active"
        module.discover_phone_tether_plans = lambda: []
        module.port_listening = lambda port: False
        module.current_phone_egress_plan = lambda: {"ok": False}
        module.run = lambda args, timeout=20, env=None: {"ok": True, "stdout": "", "stderr": "", "code": 0}

    def test_self_check_passes_when_quick_checks_are_healthy(self):
        module = load_module()
        self.prepare_self_check(module)

        result = module.self_check()

        self.assertTrue(result["ok"])
        self.assertEqual(result["overall"], "pass")
        self.assertEqual(result["mode"], "quick")

    def test_self_check_includes_iphone_lan_proxy_state(self):
        module = load_module()
        self.prepare_self_check(module)

        result = module.self_check()

        iphone_check = next(item for item in result["checks"] if item["id"] == "iphone-lan-proxy")
        self.assertEqual(iphone_check["status"], "pass")
        self.assertEqual(iphone_check["evidence"]["setting"], "10.10.0.10:18181")
        self.assertEqual(iphone_check["evidence"]["target"], "CN/private direct, foreign -> 127.0.0.1:18122")
        self.assertEqual(iphone_check["evidence"]["firewall"]["status"], "effective_open")
        self.assertEqual(iphone_check["evidence"]["recent_clients"][0]["ip"], "10.10.0.20")

    def test_self_check_warns_for_pending_upstream_decision(self):
        module = load_module()
        status = self.base_status()
        status["network_events"] = {"pending": [{"id": "evt-phone"}], "events": [{"id": "evt-phone"}]}
        self.prepare_self_check(module, status)

        result = module.self_check()

        self.assertTrue(result["ok"])
        self.assertEqual(result["overall"], "warn")
        network_check = next(item for item in result["checks"] if item["id"] == "network-events")
        self.assertEqual(network_check["status"], "warn")

    def test_deep_self_check_fails_when_connectivity_test_fails(self):
        module = load_module()
        self.prepare_self_check(module)
        module.test_all = lambda: {
            "dns_baidu": {"ok": True},
            "dns_google": {"ok": False, "stderr": "timeout"},
            "failover": {"ok": True},
            "old_proxy": {"ok": True},
        }

        result = module.self_check(deep=True)

        self.assertFalse(result["ok"])
        self.assertEqual(result["overall"], "fail")
        deep_check = next(item for item in result["checks"] if item["id"] == "deep-connectivity")
        self.assertEqual(deep_check["status"], "fail")

    def test_deep_self_check_includes_lan_gateway_coverage_report(self):
        module = load_module()
        status = self.base_status()
        status["ports"].extend([
            {"id": "split-dns", "host": "127.0.0.1", "port": 1053, "open": True},
            {"id": "split-tcp", "host": "127.0.0.1", "port": 12345, "open": True},
        ])
        status["lan_gateway"] = {
            "ok": True,
            "enabled": True,
            "client_ip": "10.10.0.25",
            "server": "10.10.0.10",
            "interface": "wlp0s20f3",
            "gateway": "10.10.0.1",
            "ip_forward": True,
            "marker_stale": False,
            "marker_stale_reasons": [],
            "nft": {
                "state": "loaded",
                "detail": "\n".join([
                    'iifname "wlp0s20f3" ip saddr 10.10.0.25 udp dport 53 redirect to :1053',
                    'iifname "wlp0s20f3" ip saddr 10.10.0.25 tcp dport 53 redirect to :1053',
                    'iifname "wlp0s20f3" ip saddr 10.10.0.25 meta l4proto tcp redirect to :12345',
                    'iifname "wlp0s20f3" ip saddr 10.10.0.25 udp dport 443 reject',
                ]),
            },
        }
        self.prepare_self_check(module, status)
        module.test_all = lambda: {
            "dns_baidu": {"ok": True},
            "dns_google": {"ok": True},
            "failover": {"ok": True},
            "old_proxy": {"ok": True},
        }

        result = module.self_check(deep=True)

        coverage_check = next(item for item in result["checks"] if item["id"] == "lan-gateway-coverage")
        self.assertEqual(coverage_check["status"], "warn")
        self.assertEqual(result["lan_gateway_coverage"]["status"], "warn")
        coverage_items = {item["id"]: item for item in coverage_check["evidence"]["checks"]}
        self.assertEqual(coverage_items["selected-client"]["status"], "pass")
        self.assertEqual(coverage_items["dns-redirect"]["status"], "pass")
        self.assertEqual(coverage_items["tcp-redirect"]["status"], "pass")
        self.assertEqual(coverage_items["udp-quic-policy"]["status"], "pass")
        self.assertEqual(coverage_items["ipv6-policy"]["status"], "warn")
        self.assertEqual(coverage_items["recent-client-evidence"]["status"], "warn")


class LanGatewayTests(unittest.TestCase):
    def test_lan_gateway_plan_infers_single_iphone_client(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            if args[:3] == ["ip", "route", "get"]:
                return {
                    "ok": True,
                    "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3 src 10.10.0.10 uid 1000",
                    "stderr": "",
                    "code": 0,
                }
            if args[:5] == ["ip", "-4", "-o", "addr", "show"]:
                return {
                    "ok": True,
                    "stdout": "2: wlp0s20f3    inet 10.10.0.10/24 brd 10.10.0.255 scope global dynamic wlp0s20f3",
                    "stderr": "",
                    "code": 0,
                }
            if args[:4] == ["nft", "list", "table", "inet"]:
                return {"ok": False, "stdout": "", "stderr": "No such file or directory", "code": 1}
            if args[:3] == ["ip", "neigh", "show"]:
                return {
                    "ok": True,
                    "stdout": "10.10.0.20 lladdr 02:00:00:00:00:20 REACHABLE",
                    "stderr": "",
                    "code": 0,
                }
            return {"ok": True, "stdout": "", "stderr": "", "code": 0}

        module.run = fake_run
        module.port_listening = lambda port: True
        module.tail = lambda path, lines=80: "2026-05-03 19:40:36,553 INFO accepted client 10.10.0.20:63209"

        with tempfile.TemporaryDirectory() as tmpdir:
            module.LAN_GATEWAY_STATE_FILE = Path(tmpdir) / "lan_gateway_state.json"
            result = module.lan_gateway_plan()

        self.assertTrue(result["ok"])
        self.assertFalse(result["enabled"])
        self.assertEqual(result["server"], "10.10.0.10")
        self.assertEqual(result["interface"], "wlp0s20f3")
        self.assertEqual(result["gateway"], "10.10.0.1")
        self.assertEqual(result["client_ip"], "10.10.0.20")
        self.assertEqual(result["client_mac"], "02:00:00:00:00:20")
        self.assertEqual(result["manual_iphone"]["router"], "10.10.0.10")
        self.assertEqual(result["manual_iphone"]["dns"], "10.10.0.10")
        self.assertIn("--client-ip 10.10.0.20", result["commands"]["root_apply"])
        self.assertFalse(result["marker_stale"])

    def test_lan_gateway_plan_warns_when_marker_targets_previous_client(self):
        module = load_module()

        def fake_run(args, timeout=20, env=None):
            if args[:3] == ["ip", "route", "get"]:
                return {
                    "ok": True,
                    "stdout": "8.8.8.8 via 10.10.0.1 dev wlp0s20f3 src 10.10.0.10 uid 1000",
                    "stderr": "",
                    "code": 0,
                }
            if args[:5] == ["ip", "-4", "-o", "addr", "show"]:
                return {
                    "ok": True,
                    "stdout": "2: wlp0s20f3    inet 10.10.0.10/24 brd 10.10.0.255 scope global dynamic wlp0s20f3",
                    "stderr": "",
                    "code": 0,
                }
            if args[:4] == ["nft", "list", "table", "inet"]:
                return {"ok": False, "stdout": "", "stderr": "Operation not permitted", "code": 1}
            if args[:3] == ["ip", "neigh", "show"]:
                return {
                    "ok": True,
                    "stdout": "10.10.0.25 lladdr 02:00:00:00:00:25 STALE",
                    "stderr": "",
                    "code": 0,
                }
            return {"ok": True, "stdout": "", "stderr": "", "code": 0}

        module.run = fake_run
        module.port_listening = lambda port: True
        module.tail = lambda path, lines=80: "2026-05-08 15:36:05,777 INFO accepted client 10.10.0.25:56931"

        with tempfile.TemporaryDirectory() as tmpdir:
            module.LAN_GATEWAY_STATE_FILE = Path(tmpdir) / "lan_gateway_state.json"
            module.LAN_GATEWAY_STATE_FILE.write_text(json.dumps({
                "enabled": True,
                "client_ip": "10.10.0.30",
                "server": "10.10.0.10",
                "interface": "wlp0s20f3",
            }))
            result = module.lan_gateway_plan()

        self.assertTrue(result["enabled"])
        self.assertEqual(result["client_ip"], "10.10.0.25")
        self.assertEqual(result["client_mac"], "02:00:00:00:00:25")
        self.assertTrue(result["marker_stale"])
        self.assertIn("client_ip:10.10.0.30->10.10.0.25", result["marker_stale_reasons"])
        self.assertIn("--client-ip 10.10.0.25", result["commands"]["root_apply"])

    def test_lan_gateway_nft_rules_match_only_selected_client(self):
        module = load_module()
        plan = {
            "client_ip": "10.10.0.20",
            "client_mac": "02:00:00:00:00:20",
            "interface": "wlp0s20f3",
        }

        text = module.render_lan_gateway_nft(plan)

        self.assertIn("table inet lan_gateway", text)
        self.assertIn('iifname "wlp0s20f3" ip saddr 10.10.0.20 udp dport 53 redirect to :1053', text)
        self.assertIn('iifname "wlp0s20f3" ip saddr 10.10.0.20 meta l4proto tcp redirect to :12345', text)
        self.assertIn('ip saddr 10.10.0.20 oifname "wlp0s20f3" masquerade', text)
        self.assertIn('iifname "wlp0s20f3" ether saddr 02:00:00:00:00:20 meta nfproto ipv6 reject', text)
        self.assertNotIn("10.10.0.0/24 meta l4proto tcp redirect", text)

    def test_lan_gateway_root_apply_checks_new_nft_before_replacing_table(self):
        module = load_module()
        calls = []

        module.os.geteuid = lambda: 0
        module.lan_gateway_plan = lambda client_ip: {
            "ok": True,
            "client_ip": client_ip,
            "client_mac": "02:00:00:00:00:20",
            "server": "10.10.0.10",
            "interface": "wlp0s20f3",
            "gateway": "10.10.0.1",
        }
        module.render_lan_gateway_nft = lambda plan: "table inet lan_gateway { broken }"

        with tempfile.TemporaryDirectory() as tmpdir:
            module.LAN_GATEWAY_NFT_FILE = Path(tmpdir) / "lan_gateway.nft"
            module.LAN_GATEWAY_STATE_FILE = Path(tmpdir) / "lan_gateway_state.json"

            def fake_run(args, timeout=20, env=None):
                calls.append(args)
                if args[:3] == ["nft", "-c", "-f"]:
                    return {"ok": False, "stdout": "", "stderr": "syntax error", "code": 1}
                return {"ok": True, "stdout": "", "stderr": "", "code": 0}

            module.run = fake_run

            result = module.lan_gateway_root_apply("10.10.0.20")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "nft_check_failed")
        self.assertIn(["nft", "-c", "-f", str(module.LAN_GATEWAY_NFT_FILE)], calls)
        self.assertNotIn(["nft", "delete", "table", "inet", "lan_gateway"], calls)

    def test_lan_gateway_coverage_uses_generated_nft_file_when_root_proof_needs_root(self):
        module = load_module()

        status = {
            "ports": [
                {"id": "split-dns", "host": "127.0.0.1", "port": 1053, "open": True},
                {"id": "split-tcp", "host": "127.0.0.1", "port": 12345, "open": True},
            ],
            "iphone_lan_proxy": {
                "recent_clients": [{"ip": "10.10.0.25", "port": 56947, "local": False}],
            },
            "dns_decisions": {
                "domestic": "direct DNS www.baidu.com",
                "foreign": "remote DNS retry www.google.com",
            },
            "lan_gateway": {
                "enabled": True,
                "client_ip": "10.10.0.25",
                "ip_forward": True,
                "marker_stale": False,
                "marker_stale_reasons": [],
                "nft": {"state": "needs_root_check", "detail": "run: sudo nft list table inet lan_gateway"},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            module.LAN_GATEWAY_NFT_FILE = Path(tmpdir) / "lan_gateway.nft"
            module.LAN_GATEWAY_NFT_FILE.write_text("\n".join([
                'iifname "wlp0s20f3" ip saddr 10.10.0.25 udp dport 53 redirect to :1053',
                'iifname "wlp0s20f3" ip saddr 10.10.0.25 tcp dport 53 redirect to :1053',
                'iifname "wlp0s20f3" ip saddr 10.10.0.25 meta l4proto tcp redirect to :12345',
                'iifname "wlp0s20f3" ip saddr 10.10.0.25 udp dport 443 reject',
            ]))
            module.port_listening = lambda port: False
            module.run = lambda args, timeout=20, env=None: {"ok": True, "stdout": "", "stderr": "", "code": 0}

            result = module.lan_gateway_coverage_report(status)

        checks = {item["id"]: item for item in result["checks"]}
        self.assertEqual(result["status"], "warn")
        self.assertEqual(checks["nft-client-target"]["evidence"]["rule_source"], "generated_file_unverified")
        self.assertTrue(checks["dns-redirect"]["evidence"]["rules_present"])
        self.assertEqual(checks["dns-redirect"]["status"], "warn")
        self.assertTrue(checks["tcp-redirect"]["evidence"]["rules_present"])
        self.assertEqual(checks["tcp-redirect"]["status"], "warn")
        self.assertTrue(checks["udp-quic-policy"]["evidence"]["rules_present"])
        self.assertEqual(checks["udp-quic-policy"]["status"], "warn")

    def test_lan_gateway_coverage_accepts_normalized_ipv6_reject_rule_from_nft(self):
        module = load_module()

        status = {
            "ports": [
                {"id": "split-dns", "host": "127.0.0.1", "port": 1053, "open": True},
                {"id": "split-tcp", "host": "127.0.0.1", "port": 12345, "open": True},
            ],
            "iphone_lan_proxy": {
                "recent_clients": [{"ip": "10.10.0.25", "port": 56947, "local": False}],
            },
            "dns_decisions": {
                "domestic": "direct DNS www.baidu.com",
                "foreign": "remote DNS retry www.google.com",
            },
            "lan_gateway": {
                "enabled": True,
                "client_ip": "10.10.0.25",
                "client_mac": "02:00:00:00:00:25",
                "ip_forward": True,
                "marker_stale": False,
                "marker_stale_reasons": [],
                "nft": {
                    "state": "loaded",
                    "detail": "\n".join([
                        'iifname "wlp0s20f3" ip saddr 10.10.0.25 udp dport 53 redirect to :1053',
                        'iifname "wlp0s20f3" ip saddr 10.10.0.25 tcp dport 53 redirect to :1053',
                        'iifname "wlp0s20f3" ip saddr 10.10.0.25 meta l4proto tcp redirect to :12345',
                        'iifname "wlp0s20f3" ip saddr 10.10.0.25 udp dport 443 reject with icmp port-unreachable',
                        'iifname "wlp0s20f3" ether saddr 02:00:00:00:00:25 reject with icmpv6 port-unreachable',
                    ]),
                },
            },
        }

        module.port_listening = lambda port: False
        module.run = lambda args, timeout=20, env=None: {"ok": True, "stdout": "", "stderr": "", "code": 0}

        result = module.lan_gateway_coverage_report(status)

        checks = {item["id"]: item for item in result["checks"]}
        self.assertEqual(checks["ipv6-policy"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
