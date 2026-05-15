import { Loader2 } from "lucide-react";
import type { StatusResponse } from "../lib/types";
import { actionLabels, buildFeatureStates } from "./linuxWorkbenchModel";

const switchFeatureIds = new Set([
  "phone",
  "main",
  "failover",
  "split",
  "linux-v3-lifecycle",
  "linux-v3-config",
  "gateway-agent-v2",
  "gateway-agent-profile-source",
  "gateway-agent-unlock",
  "gateway-agent-session",
  "gateway-agent-lan"
]);

function checkedText(state: string) {
  if (state === "ok") {
    return "开启";
  }
  if (state === "warn") {
    return "关注";
  }
  return "关闭";
}

export default function FeatureStateList({
  status,
  mode = "readOnly",
  availableActionIds = new Set(),
  busy = "",
  onAction
}: {
  status: StatusResponse | null;
  mode?: "actionable" | "readOnly";
  availableActionIds?: Set<string>;
  busy?: string;
  onAction?: (actionId: string) => void;
}) {
  const switchFeatures = buildFeatureStates(status).filter((feature) => switchFeatureIds.has(feature.id));

  return (
    <div className={`feature-switch-list ${mode}`} aria-label="Feature switch states">
      {switchFeatures.map((feature) => {
        const Icon = feature.Icon;
        const checked = feature.state === "ok";
        const featureAction = feature.control.actionId && availableActionIds.has(feature.control.actionId)
          ? feature.control.actionId
          : "";
        const actionable = mode === "actionable" && Boolean(featureAction) && feature.control.kind !== "status";
        const showToggle = actionable && feature.control.kind === "toggle";
        const showCommand = actionable && feature.control.kind === "action";
        const content = (
          <>
            <span className="feature-switch-icon">
              <Icon size={18} />
            </span>
            <span className="feature-switch-copy">
              <strong>{feature.label}</strong>
              <small>{feature.summary}</small>
              <small className="feature-switch-value">{feature.value}</small>
            </span>
            <span className={`feature-switch-state ${feature.state}`}>{checkedText(feature.state)}</span>
            {showToggle ? (
              <span className={`toggle-track ${checked ? "checked" : ""}`} aria-hidden="true">
                <span />
              </span>
            ) : showCommand ? (
              <span className="action-track" aria-hidden="true">
                {actionLabels[featureAction]}
              </span>
            ) : (
              <span className="status-only-track" aria-hidden="true">状态</span>
            )}
          </>
        );

        if (actionable) {
          return (
            <button
              type="button"
              className={`feature-switch ${feature.state} actionable ${showToggle ? "toggle-control" : "command-control"}`}
              key={feature.id}
              onClick={() => onAction?.(featureAction)}
              disabled={Boolean(busy)}
              aria-pressed={showToggle ? checked : undefined}
              aria-label={`${feature.label}：${actionLabels[featureAction] || featureAction}`}
            >
              {busy === featureAction ? <Loader2 className="feature-switch-busy spin" size={16} /> : null}
              {content}
            </button>
          );
        }

        return (
          <article className={`feature-switch ${feature.state} read-only`} key={feature.id}>
            {content}
          </article>
        );
      })}
    </div>
  );
}
