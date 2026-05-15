import { FileLock2, Loader2, Power, PowerOff, RefreshCw, Settings, ShieldAlert, ShieldCheck, Smartphone } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import type { GatewayApi } from "../lib/gatewayApi";
import type { ActionDefinition, ActionResult, LinuxDesktopPackageStatus, LinuxProxyUnificationStatus, StatusResponse } from "../lib/types";
import { buildLinuxConsoleViewModel } from "./linuxConsoleViewModel";
import { actionDescriptions, actionLabels, dailyOperationActions, defaultDailyActions } from "./linuxWorkbenchModel";
import type { WorkbenchActionLogEntry } from "./webWorkbenchTypes";

function resultMessage(result: ActionResult | null, error: string) {
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

const consoleCardIcons: Record<string, LucideIcon> = {
  "shield-check": ShieldCheck,
  "shield-alert": ShieldAlert,
  smartphone: Smartphone,
  "file-lock": FileLock2
};

export default function OperationsPage({
  status,
  proxyUnification,
  gatewayApi,
  loading,
  onActionComplete,
  onActionEvent,
  onOpenConfig
}: {
  status: StatusResponse | null;
  packageStatus: LinuxDesktopPackageStatus | null;
  proxyUnification: LinuxProxyUnificationStatus | null;
  gatewayApi: GatewayApi;
  loading: boolean;
  onActionComplete: () => void;
  onActionEvent: (entry: WorkbenchActionLogEntry) => void;
  onOpenConfig: () => void;
}) {
  const [actions, setActions] = useState<ActionDefinition[]>(defaultDailyActions);
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState<ActionResult | null>(null);
  const [error, setError] = useState("");
  const message = resultMessage(result, error);
  const actionIds = new Set(actions.map((action) => action.id));
  const viewModel = buildLinuxConsoleViewModel(status, proxyUnification);
  const { sessionActive, sessionActionId } = viewModel;

  useEffect(() => {
    gatewayApi.actions()
      .then((items) => {
        const filtered = items.filter((item) => dailyOperationActions.has(item.id));
        setActions(filtered.length ? filtered : defaultDailyActions);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [gatewayApi]);

  async function handleAction(actionId: string) {
    setBusy(actionId);
    setResult(null);
    setError("");
    try {
      const next = await gatewayApi.runAction(actionId);
      const label = actionLabels[actionId] || actionId;
      setResult(next);
      onActionEvent({
        id: `${Date.now()}-${actionId}`,
        at: new Date().toISOString(),
        actionId,
        label,
        ok: Boolean(next.ok),
        message: next.ok ? "完成" : next.stderr || "未执行"
      });
      onActionComplete();
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
      onActionEvent({
        id: `${Date.now()}-${actionId}`,
        at: new Date().toISOString(),
        actionId,
        label: actionLabels[actionId] || actionId,
        ok: false,
        message: text
      });
    } finally {
      setBusy("");
    }
  }

  function renderQuickAction(actionId: string, fallbackIcon: LucideIcon, tone: "primary" | "default" = "default") {
    const Icon = actionId === "linux-v3-stop" ? PowerOff : actionId === "gateway-agent-start" ? Power : fallbackIcon;
    const disabled = Boolean(busy) || !actionIds.has(actionId);
    return (
      <button
        type="button"
        className={`simple-action-button ${tone}`}
        onClick={() => void handleAction(actionId)}
        disabled={disabled}
        title={actionDescriptions[actionId] || actionLabels[actionId] || actionId}
      >
        {busy === actionId ? <Loader2 className="spin" size={17} /> : <Icon size={17} />}
        <span>{actionLabels[actionId] || actionId}</span>
      </button>
    );
  }

  return (
    <section className="operations-page" aria-label="Operations">
      <div className="panel-heading">
        <div>
          <h2>操作</h2>
          <p>{loading ? "正在刷新状态" : "日常控制和安全入口。"}</p>
        </div>
      </div>

      <section className="desktop-simple-console" aria-label="Simple desktop console">
        <div className="simple-status-grid">
          {viewModel.cards.map((card) => {
            const Icon = consoleCardIcons[card.icon];
            return (
              <article className={`simple-status-card ${card.state}`} key={card.id}>
                <span className="simple-card-icon">
                  <Icon size={19} />
                </span>
                <span className="simple-card-copy">
                  <span className="simple-card-label">
                    <strong>{card.label}</strong>
                    <i>{card.stateLabel}</i>
                  </span>
                  <em>{card.value}</em>
                  <small>{card.summary}</small>
                </span>
              </article>
            );
          })}
        </div>

        <div className="simple-actions" aria-label="Quick actions">
          <div>
            <strong>快速操作</strong>
            <small>这里只保留日常安全动作。</small>
          </div>
          <div className="simple-action-row">
            {renderQuickAction("self-check", RefreshCw)}
            {renderQuickAction(sessionActionId, sessionActive ? PowerOff : Power, "primary")}
            <button type="button" className="simple-action-button" onClick={onOpenConfig}>
              <Settings size={17} />
              <span>打开配置</span>
            </button>
          </div>
        </div>

        {message ? <div className={`inline-result ${message.tone}`}>{message.text}</div> : null}
      </section>
    </section>
  );
}
