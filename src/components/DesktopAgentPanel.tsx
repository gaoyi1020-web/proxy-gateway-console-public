import { invoke } from "@tauri-apps/api/core";
import { FileLock2, KeyRound, Loader2, Power, RefreshCw, ShieldCheck, Square } from "lucide-react";
import { useState } from "react";

interface Props {
  onActionComplete: () => void;
}

interface CommandResult {
  ok: boolean;
  stdout: string;
  stderr: string;
}

async function runCommand(name: string, args: Record<string, unknown> = {}) {
  return invoke<CommandResult>(name, args);
}

export default function DesktopAgentPanel({ onActionComplete }: Props) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [profilePath, setProfilePath] = useState("");
  const [passphrase, setPassphrase] = useState("");

  async function run(label: string, command: string, args: Record<string, unknown> = {}) {
    setBusy(label);
    setMessage("");
    try {
      const result = await runCommand(command, args);
      setMessage(result.stdout || result.stderr || `${label}: ${result.ok ? "ok" : "failed"}`);
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
          <h2><ShieldCheck size={18} /> Desktop Agent</h2>
          <p>Self-use desktop controls. Actions are explicit and local.</p>
        </div>
      </div>

      <div className="desktop-actions">
        <button className="action-button" disabled={Boolean(busy)} onClick={() => void run("status", "agent_status")}>
          {busy === "status" ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />}
          <span><strong>Status</strong><small>Read current desktop state from the sidecar.</small></span>
          <em className="text-ok">safe</em>
        </button>
        <button className="action-button" disabled={Boolean(busy)} onClick={() => void run("start", "agent_start", { lanHost: "127.0.0.1" })}>
          {busy === "start" ? <Loader2 className="spin" size={17} /> : <Power size={17} />}
          <span><strong>Start Session</strong><small>Create a local desktop session.</small></span>
          <em className="text-ok">safe</em>
        </button>
        <button className="action-button" disabled={Boolean(busy)} onClick={() => void run("stop", "agent_stop")}>
          {busy === "stop" ? <Loader2 className="spin" size={17} /> : <Square size={17} />}
          <span><strong>Stop Session</strong><small>Stop the local desktop session.</small></span>
          <em className="text-ok">safe</em>
        </button>
      </div>

      <div className="desktop-form">
        <label>
          <FileLock2 size={15} />
          <span>Encrypted profile path</span>
          <input value={profilePath} onChange={(event) => setProfilePath(event.target.value)} placeholder="/path/to/profile.json.enc" />
        </label>
        <label>
          <KeyRound size={15} />
          <span>Passphrase</span>
          <input type="password" value={passphrase} onChange={(event) => setPassphrase(event.target.value)} placeholder="local only" />
        </label>
        <button
          className="action-button"
          disabled={Boolean(busy) || !profilePath || !passphrase}
          onClick={() => void run("runtime", "agent_runtime_start", { profilePath, passphrase })}
        >
          {busy === "runtime" ? <Loader2 className="spin" size={17} /> : <Power size={17} />}
          <span><strong>Start Runtime Child</strong><small>Requires profile, passphrase, and explicit child gate.</small></span>
          <em className="text-warn">local</em>
        </button>
      </div>

      {message ? <pre className="command-output">{message}</pre> : null}
    </section>
  );
}
