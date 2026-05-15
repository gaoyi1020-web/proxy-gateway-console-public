import { invoke } from "@tauri-apps/api/core";
import { Loader2, Play, RotateCcw, Route, ShieldCheck, Square, TestTube2 } from "lucide-react";
import { useState } from "react";

interface Props {
  onActionComplete: () => void;
}

interface MacVpnCommandResult {
  ok: boolean;
  platform: string;
  command: string;
  stdout: string;
  stderr: string;
}

async function runCommand(name: string, args: Record<string, unknown> = {}) {
  return invoke<MacVpnCommandResult>(name, args);
}

export default function DesktopMacVpnPanel({ onActionComplete }: Props) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");

  async function run(label: string, command: string, args: Record<string, unknown> = {}) {
    setBusy(label);
    setMessage("");
    try {
      const result = await runCommand(command, args);
      const body = result.stdout || result.stderr || `${result.platform}: ${result.command}: ${result.ok ? "ok" : "failed"}`;
      setMessage(body);
      onActionComplete();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="panel desktop-panel">
      <div className="section-heading">
        <div>
          <h2><ShieldCheck size={18} /> Mac VPN</h2>
          <p>Controls the local root TUN kit at ~/ProxyGatewayMacVPN.</p>
        </div>
      </div>

      <div className="desktop-actions">
        <button className="action-button" disabled={Boolean(busy)} onClick={() => void run("status", "mac_vpn_status")}>
          {busy === "status" ? <Loader2 className="spin" size={17} /> : <ShieldCheck size={17} />}
          <span><strong>Status</strong><small>Read root service and redacted profile state.</small></span>
          <em className="text-ok">safe</em>
        </button>
        <button className="action-button" disabled={Boolean(busy)} onClick={() => void run("test", "mac_vpn_test")}>
          {busy === "test" ? <Loader2 className="spin" size={17} /> : <TestTube2 size={17} />}
          <span><strong>Test</strong><small>Validate config and connectivity.</small></span>
          <em className="text-ok">safe</em>
        </button>
        <button
          className="action-button"
          disabled={Boolean(busy)}
          onClick={() => void run("underlay", "mac_vpn_prepare_underlay", { confirm: "PREPARE_MAC_VPN_UNDERLAY" })}
        >
          {busy === "underlay" ? <Loader2 className="spin" size={17} /> : <Route size={17} />}
          <span><strong>Prepare Underlay</strong><small>Switch Wi-Fi underlay away from the Linux gateway.</small></span>
          <em className="text-warn">local</em>
        </button>
        <button
          className="action-button"
          disabled={Boolean(busy)}
          onClick={() => void run("start-root", "mac_vpn_start_root", { confirm: "START_MAC_VPN_ROOT" })}
        >
          {busy === "start-root" ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
          <span><strong>Start Root VPN</strong><small>macOS will request administrator approval.</small></span>
          <em className="text-warn">admin</em>
        </button>
        <button
          className="action-button"
          disabled={Boolean(busy)}
          onClick={() => void run("stop-root", "mac_vpn_stop_root", { confirm: "STOP_MAC_VPN_ROOT" })}
        >
          {busy === "stop-root" ? <Loader2 className="spin" size={17} /> : <Square size={17} />}
          <span><strong>Stop Root VPN</strong><small>Stop the LaunchDaemon without deleting the kit.</small></span>
          <em className="text-warn">admin</em>
        </button>
        <button
          className="action-button"
          disabled={Boolean(busy)}
          onClick={() => void run("restore", "mac_vpn_restore_lan_gateway", { confirm: "RESTORE_MAC_LAN_GATEWAY" })}
        >
          {busy === "restore" ? <Loader2 className="spin" size={17} /> : <RotateCcw size={17} />}
          <span><strong>Restore LAN Gateway</strong><small>Rollback Wi-Fi router, DNS, and HTTP proxy.</small></span>
          <em className="text-warn">local</em>
        </button>
      </div>

      {message ? <pre className="command-output">{message}</pre> : null}
    </section>
  );
}
