import { invoke } from "@tauri-apps/api/core";
import { Loader2, Network, ShieldAlert, XCircle } from "lucide-react";
import { useState } from "react";

interface ProxyCommandResult {
  ok: boolean;
  platform: string;
  stdout: string;
  stderr: string;
}

export default function DesktopProxyPanel() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [port, setPort] = useState(18180);

  async function run(label: string, command: string, args: Record<string, unknown> = {}) {
    setBusy(label);
    setMessage("");
    try {
      const result = await invoke<ProxyCommandResult>(command, args);
      setMessage(result.stdout || result.stderr || `${result.platform}: ${result.ok ? "ok" : "failed"}`);
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
          <h2><Network size={18} /> System Proxy</h2>
          <p>Loopback proxy settings are applied only after an explicit click.</p>
        </div>
      </div>

      <div className="desktop-form">
        <label>
          <Network size={15} />
          <span>Loopback HTTP proxy port</span>
          <input
            type="number"
            min={1}
            max={65535}
            value={port}
            onChange={(event) => setPort(Number(event.target.value))}
          />
        </label>
      </div>

      <div className="desktop-actions">
        <button className="action-button" disabled={Boolean(busy)} onClick={() => void run("status", "system_proxy_status")}>
          {busy === "status" ? <Loader2 className="spin" size={17} /> : <ShieldAlert size={17} />}
          <span><strong>Status</strong><small>Inspect platform proxy state.</small></span>
          <em className="text-ok">safe</em>
        </button>
        <button
          className="action-button"
          disabled={Boolean(busy) || port < 1 || port > 65535}
          onClick={() => void run("apply", "system_proxy_apply", { host: "127.0.0.1", port, confirm: "APPLY_SYSTEM_PROXY" })}
        >
          {busy === "apply" ? <Loader2 className="spin" size={17} /> : <Network size={17} />}
          <span><strong>Apply</strong><small>Set HTTP/HTTPS proxy to 127.0.0.1:{port}.</small></span>
          <em className="text-warn">local</em>
        </button>
        <button className="action-button" disabled={Boolean(busy)} onClick={() => void run("clear", "system_proxy_clear", { confirm: "CLEAR_SYSTEM_PROXY" })}>
          {busy === "clear" ? <Loader2 className="spin" size={17} /> : <XCircle size={17} />}
          <span><strong>Clear</strong><small>Remove the system proxy setting for this user.</small></span>
          <em className="text-ok">safe</em>
        </button>
      </div>

      {message ? <pre className="command-output">{message}</pre> : null}
    </section>
  );
}
