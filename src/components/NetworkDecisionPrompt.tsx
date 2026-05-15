import { BellOff, Loader2, Save, Smartphone, Wifi } from "lucide-react";
import { useMemo, useState } from "react";
import type { NetworkDecision, NetworkEvent, NetworkDecisionResult } from "../lib/types";

const options: Array<{
  id: NetworkDecision;
  label: string;
  detail: string;
  Icon: typeof Wifi;
  requiresReady?: boolean;
}> = [
  {
    id: "keep-current",
    label: "Keep current",
    detail: "Phone stays connected but cannot take the default route.",
    Icon: Wifi
  },
  {
    id: "use-phone-once",
    label: "Use mobile port",
    detail: "Use only the explicit local port without changing host default route.",
    Icon: Smartphone,
    requiresReady: true
  },
  {
    id: "ignore-once",
    label: "Ignore once",
    detail: "Leave the current policy unchanged for this event.",
    Icon: BellOff
  },
  {
    id: "always-keep-current",
    label: "Always keep",
    detail: "Remember the safe default for this phone profile.",
    Icon: Save
  },
  {
    id: "always-use-phone",
    label: "Always use port",
    detail: "Remember this device for the explicit mobile egress port.",
    Icon: Save,
    requiresReady: true
  }
];

export default function NetworkDecisionPrompt({
  events,
  onDecision
}: {
  events: NetworkEvent[];
  onDecision: (eventId: string, decision: NetworkDecision) => Promise<NetworkDecisionResult>;
}) {
  const event = useMemo(() => events.find((item) => item.status === "pending"), [events]);
  const [busy, setBusy] = useState<NetworkDecision | "">("");
  const [error, setError] = useState("");

  if (!event) {
    return null;
  }
  const ready = Boolean(event.connection_known && event.carrier);
  const connectionLabel = event.connection || "No active network profile";

  async function choose(decision: NetworkDecision) {
    if (!event) {
      return;
    }
    setBusy(decision);
    setError("");
    try {
      const result = await onDecision(event.id, decision);
      if (!result.ok) {
        throw new Error(result.stderr || "Network decision failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="decision-modal" role="dialog" aria-modal="true" aria-labelledby="network-decision-title">
        <div className="decision-heading">
          <div className="link-icon">
            <Smartphone size={21} />
          </div>
          <div>
            <h2 id="network-decision-title">USB Mobile Network</h2>
            <p>{connectionLabel} on {event.interface}</p>
          </div>
        </div>

        <dl className="decision-meta">
          <div>
            <dt>Driver</dt>
            <dd>{event.driver || "unknown"}</dd>
          </div>
          <div>
            <dt>Link</dt>
            <dd>{ready ? "ready" : `not ready${event.operstate ? `: ${event.operstate}` : ""}`}</dd>
          </div>
          <div>
            <dt>Current route</dt>
            <dd>{event.default_route || "unknown"}</dd>
          </div>
          <div>
            <dt>Connection</dt>
            <dd>{connectionLabel}</dd>
          </div>
        </dl>

        {!ready ? (
          <div className="banner warn">
            USB device is visible, but Personal Hotspot is not active yet. Trust this computer and enable hotspot before using it as upstream.
          </div>
        ) : null}

        {error ? <div className="banner danger">{error}</div> : null}

        <div className="decision-actions">
          {options.map(({ id, label, detail, Icon, requiresReady }) => (
            <button
              className="decision-button"
              key={id}
              onClick={() => void choose(id)}
              disabled={Boolean(busy) || Boolean(requiresReady && !ready)}
            >
              {busy === id ? <Loader2 className="spin" size={17} /> : <Icon size={17} />}
              <span>
                <strong>{label}</strong>
                <small>{requiresReady && !ready ? "Enable Personal Hotspot before this option is available." : detail}</small>
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
