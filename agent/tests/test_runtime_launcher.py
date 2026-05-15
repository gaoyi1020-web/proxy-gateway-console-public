import tempfile
import unittest
from pathlib import Path

from agent.profile_schema import redacted_profile_template
from agent.runtime_launcher import build_runtime_plan, phone_setup_from_session, runtime_status, start_runtime, stop_runtime
from agent.session_store import SessionStore


class RuntimeLauncherTests(unittest.TestCase):
    def test_runtime_plan_is_dry_run_and_keeps_fallback(self):
        session = {"listeners": {"httpProxy": {"host": "127.0.0.1", "port": 40001}}}
        plan = build_runtime_plan(session, redacted_profile_template())

        self.assertTrue(plan["ok"])
        self.assertEqual(plan["mode"], "dry-run")
        self.assertTrue(plan["fallback"]["enabled"])
        self.assertEqual(plan["children"][0]["id"], "httpProxy")

    def test_non_dry_run_start_is_blocked(self):
        result = start_runtime({"children": []}, dry_run=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")

    def test_controlled_runtime_start_requires_explicit_child_flag(self):
        session = {"listeners": {"lanProxy": {"host": "127.0.0.1", "port": 40010}}}
        plan = build_runtime_plan(session, redacted_profile_template())

        result = start_runtime(plan, dry_run=False, allow_child=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertIn("explicit", result["summary"])

    def test_controlled_runtime_start_requires_profile_and_lan_listener(self):
        no_profile = build_runtime_plan({"listeners": {"lanProxy": {"host": "127.0.0.1", "port": 40010}}})
        no_lan = build_runtime_plan({"listeners": {"httpProxy": {"host": "127.0.0.1", "port": 40011}}}, redacted_profile_template())

        profile_result = start_runtime(no_profile, dry_run=False, allow_child=True)
        lan_result = start_runtime(no_lan, dry_run=False, allow_child=True)

        self.assertFalse(profile_result["ok"])
        self.assertIn("profile", profile_result["summary"])
        self.assertFalse(lan_result["ok"])
        self.assertIn("lanProxy", lan_result["summary"])

    def test_controlled_runtime_start_records_and_stops_lan_proxy_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(tmp)
            session = {"listeners": {"lanProxy": {"host": "127.0.0.1", "port": 40010}}}
            plan = build_runtime_plan(session, redacted_profile_template())
            spawned = []
            killed = []

            class FakeProcess:
                pid = 12345

            def fake_spawn(command):
                spawned.append(command)
                return FakeProcess()

            def fake_kill(pid):
                killed.append(pid)
                return True

            result = start_runtime(plan, dry_run=False, allow_child=True, store=store, process_factory=fake_spawn)
            status = runtime_status(store=store, process_checker=lambda _pid: True)
            child_state = store.read_json(store.state_dir / "runtime-children.json")
            stopped = stop_runtime(store=store, process_killer=fake_kill)

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "running")
        self.assertEqual(status["state"], "running")
        self.assertEqual(status["children"][0]["id"], "lanProxy")
        self.assertEqual(result["children"][0]["id"], "lanProxy")
        self.assertIn("lan_proxy_child.py", " ".join(spawned[0]))
        self.assertEqual(child_state["children"][0]["pid"], 12345)
        self.assertEqual(killed, [12345])
        self.assertEqual(stopped["stoppedChildProcesses"], 1)

    def test_invalid_listener_blocks_runtime_plan(self):
        plan = build_runtime_plan({"listeners": {"httpProxy": {"host": "127.0.0.1", "port": 70000}}})
        result = start_runtime(plan)

        self.assertFalse(plan["ok"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")

    def test_stop_runtime_is_noop_for_current_milestone(self):
        self.assertEqual(stop_runtime()["state"], "stopped")

    def test_phone_setup_uses_lan_proxy_only_when_present(self):
        off = phone_setup_from_session({"listeners": {}})
        on = phone_setup_from_session({
            "listeners": {
                "controllerApi": {"host": "127.0.0.1", "port": 4077},
                "httpProxy": {"host": "127.0.0.1", "port": 40011},
                "lanProxy": {"host": "10.10.0.10", "port": 40010},
            }
        }, listener_checker=lambda _host, _port: True)

        self.assertFalse(off["enabled"])
        self.assertEqual(on["setting"], "10.10.0.10:40010")
        self.assertEqual(on["manualProxy"]["server"], "10.10.0.10")
        self.assertEqual(on["manualProxy"]["port"], 40010)
        self.assertEqual(on["pac"]["mimeType"], "application/x-ns-proxy-autoconfig")
        self.assertIn("FindProxyForURL", on["pac"]["content"])
        self.assertNotIn("127.0.0.1:40011", on["pac"]["content"])
        self.assertEqual(on["observedClients"], [])

    def test_phone_setup_does_not_publish_stale_closed_lan_listener(self):
        setup = phone_setup_from_session({
            "listeners": {
                "lanProxy": {"host": "10.10.0.10", "port": 33581},
            }
        }, listener_checker=lambda _host, _port: False)

        self.assertFalse(setup["enabled"])
        self.assertEqual(setup["state"], "lan_listener_stale")
        self.assertEqual(setup["setting"], "10.10.0.10:33581")
        self.assertNotIn("manualProxy", setup)
        self.assertNotIn("pac", setup)

    def test_phone_setup_does_not_publish_loopback_listener_for_phone(self):
        setup = phone_setup_from_session({
            "listeners": {
                "lanProxy": {"host": "127.0.0.1", "port": 33581},
            }
        }, listener_checker=lambda _host, _port: True)

        self.assertFalse(setup["enabled"])
        self.assertEqual(setup["state"], "lan_listener_local_only")
        self.assertEqual(setup["setting"], "127.0.0.1:33581")
        self.assertNotIn("manualProxy", setup)
        self.assertNotIn("pac", setup)


if __name__ == "__main__":
    unittest.main()
