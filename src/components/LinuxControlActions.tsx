import { Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import type { GatewayApi } from "../lib/gatewayApi";
import type { ActionDefinition, ActionResult, StatusResponse } from "../lib/types";
import FeatureStateList from "./FeatureStateList";
import {
  actionDescriptions,
  actionIcons,
  actionLabels,
  defaultActions,
  maintenanceActions,
  primaryActions,
  visibleActions
} from "./linuxWorkbenchModel";

function actionMessage(result: ActionResult | null, error: string) {
  if (error) {
    return { tone: "danger", text: error };
  }
  if (!result) {
    return null;
  }
  if (result.ok) {
    return { tone: "ok", text: `${actionLabels[result.actionId] || result.actionId} 完成` };
  }
  return { tone: "warn", text: result.stderr || `${actionLabels[result.actionId] || result.actionId} 未执行` };
}

export default function LinuxControlActions({
  status,
  gatewayApi,
  onActionComplete
}: {
  status: StatusResponse | null;
  gatewayApi: GatewayApi;
  onActionComplete: () => void;
}) {
  const [actions, setActions] = useState<ActionDefinition[]>(defaultActions);
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState<ActionResult | null>(null);
  const [error, setError] = useState("");
  const message = actionMessage(result, error);
  const primary = actions.filter((action) => primaryActions.has(action.id));
  const maintenance = actions.filter((action) => maintenanceActions.has(action.id));
  const availableActionIds = new Set(actions.map((action) => action.id));

  useEffect(() => {
    gatewayApi.actions()
      .then((items) => {
        const filtered = items.filter((item) => visibleActions.has(item.id));
        setActions(filtered.length ? filtered : defaultActions);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [gatewayApi]);

  async function handleAction(actionId: string) {
    setBusy(actionId);
    setResult(null);
    setError("");
    try {
      const next = await gatewayApi.runAction(actionId);
      setResult(next);
      onActionComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  function renderActionButton(action: ActionDefinition) {
    const Icon = actionIcons[action.id] ?? Play;
    return (
      <button
        className={`switch-button ${action.risk}`}
        key={action.id}
        onClick={() => void handleAction(action.id)}
        disabled={Boolean(busy)}
        title={actionDescriptions[action.id] || action.description}
      >
        {busy === action.id ? <Loader2 className="spin" size={18} /> : <Icon size={18} />}
        <span>
          <strong>{actionLabels[action.id] || action.label}</strong>
          <small>{actionDescriptions[action.id] || action.description}</small>
        </span>
      </button>
    );
  }

  return (
    <section className="workbench-panel switch-panel">
      <div className="panel-heading compact">
        <div>
          <h2>功能与状态</h2>
          <p>启停项、检测动作和只读状态分开显示。</p>
        </div>
      </div>

      <FeatureStateList
        status={status}
        mode="actionable"
        availableActionIds={availableActionIds}
        busy={busy}
        onAction={(actionId) => void handleAction(actionId)}
      />

      <details className="maintenance-actions">
        <summary>执行动作</summary>
        <div className="switch-grid primary">{primary.map(renderActionButton)}</div>
      </details>

      {maintenance.length ? (
        <details className="maintenance-actions">
          <summary>维护动作</summary>
          <div className="switch-grid maintenance">{maintenance.map(renderActionButton)}</div>
        </details>
      ) : null}

      {message ? <div className={`inline-result ${message.tone}`}>{message.text}</div> : null}
    </section>
  );
}
