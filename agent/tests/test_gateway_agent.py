import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from agent import gateway_agent
from agent.profile_crypto import read_encrypted_profile, write_encrypted_profile
from agent.profile_schema import redacted_profile_template


FAKE_MANIFEST = {
    "version": 2,
    "sessionId": "test-session",
    "createdAt": "2026-05-03T00:00:00Z",
    "listeners": {
        "dashboard": {"host": "127.0.0.1", "port": 40001},
        "unlock": {"host": "127.0.0.1", "port": 40002},
        "httpProxy": {"host": "127.0.0.1", "port": 40003},
        "socksProxy": {"host": "127.0.0.1", "port": 40004},
    },
    "privacy": {"state": "tmpfs", "logs": "redacted"},
}


class GatewayAgentTests(unittest.TestCase):
    def test_status_is_locked_or_disabled_without_feature_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GATEWAY_AGENT_RUNTIME_DIR": tmp}, clear=True):
                status = gateway_agent.build_status()

        self.assertTrue(status["ok"])
        self.assertFalse(status["enabled"])
        self.assertEqual(status["state"], "locked_or_disabled")
        self.assertIsNone(status["session"])

    def test_start_requires_feature_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GATEWAY_AGENT_RUNTIME_DIR": tmp}, clear=True):
                status = gateway_agent.start_session()

        self.assertFalse(status["ok"])
        self.assertEqual(status["state"], "locked_or_disabled")

    def test_start_writes_manifest_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GATEWAY_AGENT_RUNTIME_DIR": tmp, "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                with patch.object(gateway_agent, "build_session_manifest", return_value=FAKE_MANIFEST):
                    status = gateway_agent.start_session()
                session_file = gateway_agent.session_path()
                exists_after_start = session_file.exists()

        self.assertTrue(status["ok"])
        self.assertEqual(status["state"], "manifest_ready")
        self.assertTrue(exists_after_start)
        self.assertIn("httpProxy", status["session"]["listeners"])

    def test_start_reports_structured_error_when_port_allocation_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GATEWAY_AGENT_RUNTIME_DIR": tmp, "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                with patch.object(gateway_agent, "build_session_manifest", side_effect=PermissionError(1, "blocked")):
                    status = gateway_agent.start_session()

        self.assertFalse(status["ok"])
        self.assertEqual(status["state"], "runtime_blocked")
        self.assertEqual(status["error"]["type"], "PermissionError")
        self.assertIsNone(status["session"])

    def test_stop_removes_manifest_without_touching_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GATEWAY_AGENT_RUNTIME_DIR": tmp, "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                with patch.object(gateway_agent, "build_session_manifest", return_value=FAKE_MANIFEST):
                    gateway_agent.start_session()
                stopped = gateway_agent.stop_session()

        self.assertTrue(stopped["removedSession"])
        self.assertEqual(stopped["state"], "locked_or_disabled")
        self.assertIsNone(stopped["session"])

    def test_stop_session_stops_runtime_children_before_removing_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GATEWAY_AGENT_RUNTIME_DIR": tmp, "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                gateway_agent.SessionStore().write_session(FAKE_MANIFEST)
                with patch.object(gateway_agent, "stop_runtime") as stop_runtime:
                    stopped = gateway_agent.stop_session()

        stop_runtime.assert_called_once()
        self.assertTrue(stopped["removedSession"])

    def test_unlock_server_refuses_non_loopback_bind(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GATEWAY_AGENT_RUNTIME_DIR": tmp}, clear=True):
                with patch.object(gateway_agent, "print_json"):
                    code = gateway_agent.main(["unlock-server", "--host", "0.0.0.0"])

        self.assertEqual(code, 2)

    def test_watch_usb_once_locks_when_configured_usb_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GATEWAY_AGENT_RUNTIME_DIR": tmp, "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                with patch.object(gateway_agent, "build_session_manifest", return_value=FAKE_MANIFEST):
                    gateway_agent.start_session()
                result = gateway_agent.watch_usb_once("/tmp/proxy-gateway-v2-missing-usb")

        self.assertEqual(result["state"], "locked_removed")
        self.assertTrue(result["removedSession"])

    def test_watchdog_once_cleans_stale_runtime_child_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GATEWAY_AGENT_RUNTIME_DIR": tmp, "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                store = gateway_agent.SessionStore()
                store.write_session(FAKE_MANIFEST)
                store.write_json(
                    store.state_dir / "runtime-children.json",
                    {"children": [{"id": "lanProxy", "pid": 12345}]},
                )
                result = gateway_agent.watchdog_once(
                    process_checker=lambda _pid: False,
                    process_killer=lambda _pid: False,
                )
                status = gateway_agent.build_status()

        self.assertEqual(result["state"], "stale_runtime_cleaned")
        self.assertIsNotNone(status["session"])
        self.assertEqual(status["runtimeState"]["state"], "stopped")

    def test_watchdog_once_locks_when_running_runtime_loses_local_profile_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_profile = Path(tmp) / "missing-profile.json.enc"
            env = {"GATEWAY_AGENT_RUNTIME_DIR": tmp, "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                store = gateway_agent.SessionStore()
                store.write_session(FAKE_MANIFEST)
                store.write_json(
                    store.state_dir / "runtime-children.json",
                    {"children": [{"id": "lanProxy", "pid": 12345}]},
                )
                result = gateway_agent.watchdog_once(
                    profile_path=str(missing_profile),
                    process_checker=lambda _pid: True,
                    process_killer=lambda _pid: True,
                )
                status = gateway_agent.build_status(profile_path=str(missing_profile))

        self.assertEqual(result["state"], "profile_source_lost_locked")
        self.assertTrue(result["removedSession"])
        self.assertIsNone(status["session"])
        self.assertEqual(status["runtimeState"]["state"], "stopped")

    def test_daemon_once_runs_watch_without_starting_network_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GATEWAY_AGENT_RUNTIME_DIR": tmp}, clear=True):
                result = gateway_agent.daemon_loop(iterations=1)

        self.assertEqual(result["state"], "daemon_checked")
        self.assertEqual(result["iterations"], 1)

    def test_profile_import_copies_recovery_profile_to_local_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "PROXY_GATEWAY" / "profile" / "profile.json.enc"
            target = Path(tmp) / "config" / "profile.json.enc"
            write_encrypted_profile(redacted_profile_template(), source, "passphrase")

            result = gateway_agent.profile_import_command(str(source), str(target))
            decrypted = read_encrypted_profile(target, "passphrase")

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "imported")
        self.assertEqual(decrypted["version"], 2)

    def test_profile_from_upstream_writes_encrypted_profile_without_echoing_adapter_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            upstream = Path(tmp) / "upstream.json"
            output = Path(tmp) / "profile.json.enc"
            upstream.write_text(
                """
                {
                  "final": "us",
                  "outbounds": [
                    {
                      "type": "shadowsocks",
                      "tag": "us",
                      "server": "203.0.113.10",
                      "server_port": 443,
                      "method": "2022-blake3-aes-128-gcm",
                      "password": "private-password"
                    },
                    {
                      "type": "shadowsocks",
                      "tag": "jp",
                      "server": "203.0.113.11",
                      "server_port": 443,
                      "method": "2022-blake3-aes-128-gcm",
                      "password": "private-password-2"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            with patch.object(gateway_agent, "print_json") as print_json:
                code = gateway_agent.main([
                    "profile-from-upstream",
                    "--from",
                    str(upstream),
                    "--profile-output",
                    str(output),
                    "--passphrase",
                    "passphrase",
                ])
            payload = print_json.call_args.args[0]
            decrypted = read_encrypted_profile(output, "passphrase")

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "converted")
        self.assertEqual(payload["summary"]["routeCount"], 4)
        rendered_payload = repr(payload)
        rendered_profile = repr(decrypted)
        self.assertNotIn("203.0.113.10", rendered_payload)
        self.assertNotIn("private-password", rendered_payload)
        self.assertNotIn("203.0.113.10", rendered_profile)
        self.assertNotIn("private-password", rendered_profile)
        self.assertEqual(decrypted["routes"]["us"]["authRef"], "adapter:sing-box:us")

    def test_print_json_redacts_sensitive_fields(self):
        output = io.StringIO()

        with redirect_stdout(output):
            gateway_agent.print_json({"ok": True, "token": "runtime-token", "message": "password=runtime-pass"})

        rendered = output.getvalue()
        self.assertIn("[redacted]", rendered)
        self.assertNotIn("runtime-token", rendered)
        self.assertNotIn("runtime-pass", rendered)

    def test_profile_export_refuses_plaintext_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "config" / "profile.json.enc"
            target = Path(tmp) / "profile.json"
            write_encrypted_profile(redacted_profile_template(), source, "passphrase")

            result = gateway_agent.profile_export_command(str(source), str(target))

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")

    def test_unlock_uses_local_profile_without_usb(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json.enc"
            runtime_dir = Path(tmp) / "runtime"
            write_encrypted_profile(redacted_profile_template(), profile_path, "passphrase")
            with patch.dict(os.environ, {"GATEWAY_AGENT_RUNTIME_DIR": str(runtime_dir)}, clear=True):
                result = gateway_agent.unlock_local_profile(gateway_agent.SessionStore(), str(profile_path), "passphrase")
                status = gateway_agent.build_status(profile_path=str(profile_path))

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "unlocked")
        self.assertTrue(status["unlock"]["profileLoaded"])
        self.assertEqual(status["profileSource"]["mode"], "local")

    def test_self_check_validates_local_encrypted_profile_when_passphrase_supplied(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json.enc"
            runtime_dir = Path(tmp) / "runtime"
            write_encrypted_profile(redacted_profile_template(), profile_path, "passphrase")
            env = {"GATEWAY_AGENT_RUNTIME_DIR": str(runtime_dir)}
            with patch.dict(os.environ, env, clear=True):
                report = gateway_agent.self_check(profile_path=str(profile_path), passphrase="passphrase")

        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["profile-source"]["status"], "pass")
        self.assertEqual(checks["profile-schema"]["status"], "pass")

    def test_self_check_includes_linux_v3_lifecycle_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "HOME": str(root / "home"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "GATEWAY_AGENT_RUNTIME_DIR": str(root / "run"),
            }
            service = root / "config" / "systemd" / "user" / "gateway-agent.service"
            wrapper = root / "home" / ".local" / "bin" / "gateway-agent"
            service.parent.mkdir(parents=True)
            wrapper.parent.mkdir(parents=True)
            service.write_text("[Service]\n", encoding="utf-8")
            wrapper.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            with patch.dict(os.environ, env, clear=True):
                report = gateway_agent.self_check()

        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["linux-v3-lifecycle"]["status"], "pass")
        self.assertEqual(checks["linux-v3-lifecycle"]["evidence"]["contract"]["stop"], "preserve-config")

    def test_runtime_start_command_requires_explicit_child_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json.enc"
            runtime_dir = Path(tmp) / "runtime"
            write_encrypted_profile(redacted_profile_template(), profile_path, "passphrase")
            env = {"GATEWAY_AGENT_RUNTIME_DIR": str(runtime_dir), "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                gateway_agent.SessionStore().write_session({
                    "listeners": {"lanProxy": {"host": "127.0.0.1", "port": 40010}}
                })
                result = gateway_agent.runtime_start_command(str(profile_path), "passphrase", allow_child=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")

    def test_runtime_start_command_starts_child_when_profile_and_flag_are_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json.enc"
            runtime_dir = Path(tmp) / "runtime"
            write_encrypted_profile(redacted_profile_template(), profile_path, "passphrase")
            spawned = []

            class FakeProcess:
                pid = 23456

            def fake_spawn(command):
                spawned.append(command)
                return FakeProcess()

            env = {"GATEWAY_AGENT_RUNTIME_DIR": str(runtime_dir), "GATEWAY_AGENT_V2": "1"}
            with patch.dict(os.environ, env, clear=True):
                gateway_agent.SessionStore().write_session({
                    "listeners": {"lanProxy": {"host": "127.0.0.1", "port": 40010}}
                })
                result = gateway_agent.runtime_start_command(
                    str(profile_path),
                    "passphrase",
                    allow_child=True,
                    process_factory=fake_spawn,
                )

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "running")
        self.assertEqual(result["children"][0]["pid"], 23456)
        self.assertIn("lan_proxy_child.py", " ".join(spawned[0]))


if __name__ == "__main__":
    unittest.main()
