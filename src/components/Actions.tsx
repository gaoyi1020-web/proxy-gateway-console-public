import { Loader2, Play, Power, PowerOff, Radar, Shield } from "lucide-react";
import { useEffect, useState } from "react";
import type { ActionDefinition, ActionResult } from "../lib/types";

const actionIcons: Record<string, typeof Power> = {
  "self-check": Shield,
  "hotspot-preflight": Radar,
  "hotspot-start-safe": Power,
  "test": Play,
  "restart-user": PowerOff,
  "update-cn": Radar
};

async function fetchActions() {
  const res = await fetch("/api/actions");
  if (!res.ok) {
    throw new Error(`actions ${res.status}`);
  }
  return (await res.json()).actions as ActionDefinition[];
}

async function runAction(actionId: string) {
  const res = await fetch("/api/actions/run", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ actionId })
  });
  if (!res.ok) {
    throw new Error(`action ${res.status}`);
  }
  return (await res.json()) as ActionResult;
}

export default function Actions({ onActionComplete }: { onActionComplete: () => void }) {
  const [actions, setActions] = useState<ActionDefinition[]>([]);
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState<ActionResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchActions().then(setActions).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  async function handleAction(actionId: string) {
    setBusy(actionId);
    setError("");
    try {
      const next = await runAction(actionId);
      setResult(next);
      onActionComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2><Shield size={18} /> Actions</h2>
          <p>Allowed operations only; root nftables actions remain terminal-gated.</p>
        </div>
      </div>

      {error ? <div className="banner danger">{error}</div> : null}

      <div className="action-list">
        {actions.map((action) => {
          const Icon = actionIcons[action.id] ?? Power;
          return (
            <button className="action-button" key={action.id} onClick={() => void handleAction(action.id)} disabled={Boolean(busy)}>
              {busy === action.id ? <Loader2 className="spin" size={17} /> : <Icon size={17} />}
              <span>
                <strong>{action.label}</strong>
                <small>{action.description}</small>
              </span>
              <em className={action.risk === "safe" ? "text-ok" : "text-warn"}>{action.risk}</em>
            </button>
          );
        })}
      </div>

      {result ? (
        <pre className={result.ok ? "command-output ok-border" : "command-output warn-border"}>
{JSON.stringify(result, null, 2)}
        </pre>
      ) : null}
    </section>
  );
}
