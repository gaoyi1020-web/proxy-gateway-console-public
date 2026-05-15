import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import gateway_agent
from agent.linux_lifecycle import lifecycle_status, stop_control_layer, uninstall_control_layer
from agent.session_store import SessionStore


class LinuxLifecycleTests(unittest.TestCase):
    def test_stop_preserves_local_config_but_removes_session_and_unlock_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "HOME": str(root / "home"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "GATEWAY_AGENT_RUNTIME_DIR": str(root / "run"),
            }
            with patch.dict(os.environ, env, clear=True):
                config_dir = root / "config" / "proxy-gateway"
                config_dir.mkdir(parents=True)
                profile = config_dir / "profile.json.enc"
                profile.write_text('{"product":"proxy-gateway"}\n', encoding="utf-8")
                store = SessionStore()
                store.write_session({"version": 2, "sessionId": "local-test"})
                store.write_token({"token": "secret"})

                result = stop_control_layer(process_killer=lambda _pid: True)

                self.assertTrue(result["ok"])
                self.assertEqual(result["state"], "stopped")
                self.assertTrue(profile.exists())
                self.assertFalse(store.session_path.exists())
                self.assertFalse(store.token_path.exists())

    def test_uninstall_apply_removes_project_owned_linux_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "HOME": str(root / "home"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "GATEWAY_AGENT_RUNTIME_DIR": str(root / "run"),
            }
            with patch.dict(os.environ, env, clear=True):
                config_dir = root / "config" / "proxy-gateway"
                wrapper = root / "home" / ".local" / "bin" / "gateway-agent"
                service = root / "config" / "systemd" / "user" / "gateway-agent.service"
                for path in (config_dir, wrapper.parent, service.parent):
                    path.mkdir(parents=True, exist_ok=True)
                (config_dir / "profile.json.enc").write_text("encrypted\n", encoding="utf-8")
                wrapper.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
                service.write_text("[Service]\n", encoding="utf-8")
                store = SessionStore()
                store.write_session({"version": 2, "sessionId": "local-test"})

                result = uninstall_control_layer(apply=True, process_killer=lambda _pid: True)

                self.assertTrue(result["ok"])
                self.assertTrue(result["applied"])
                self.assertFalse(config_dir.exists())
                self.assertFalse(wrapper.exists())
                self.assertFalse(service.exists())
                self.assertFalse(store.runtime_dir.exists())

    def test_uninstall_dry_run_reports_paths_without_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "HOME": str(root / "home"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "GATEWAY_AGENT_RUNTIME_DIR": str(root / "run"),
            }
            with patch.dict(os.environ, env, clear=True):
                config_dir = root / "config" / "proxy-gateway"
                config_dir.mkdir(parents=True)

                result = uninstall_control_layer(apply=False)
                status = lifecycle_status()

                self.assertTrue(result["ok"])
                self.assertFalse(result["applied"])
                self.assertTrue(config_dir.exists())
                self.assertEqual(status["config"]["path"], str(config_dir))
                self.assertEqual(result["contract"]["stop"], "preserve-config")
                self.assertEqual(result["contract"]["uninstall"], "purge-project-owned")

    def test_gateway_agent_exposes_lifecycle_and_safe_uninstall_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "HOME": str(root / "home"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "GATEWAY_AGENT_RUNTIME_DIR": str(root / "run"),
            }
            with patch.dict(os.environ, env, clear=True):
                with patch.object(gateway_agent, "print_json") as print_json:
                    lifecycle_code = gateway_agent.main(["lifecycle-status"])
                    dry_run_code = gateway_agent.main(["uninstall"])

        self.assertEqual(lifecycle_code, 0)
        self.assertEqual(dry_run_code, 0)
        self.assertEqual(print_json.call_args_list[0].args[0]["contract"]["stop"], "preserve-config")
        self.assertFalse(print_json.call_args_list[1].args[0]["applied"])


if __name__ == "__main__":
    unittest.main()
