import { Copy, Router } from "lucide-react";
import type { StatusResponse } from "../lib/types";

function rowText(label: string, value: string) {
  return `${label}: ${value}`;
}

export default function LanGateway({ status }: { status: StatusResponse | null }) {
  const gateway = status?.lanGateway;
  const rows = [
    { label: "Mode", value: gateway?.enabled ? "enabled" : "disabled" },
    { label: "iPhone IP", value: gateway?.manualIphone.ip || "unknown" },
    { label: "Subnet mask", value: gateway?.manualIphone.subnetMask || "255.255.255.0" },
    { label: "Router", value: gateway?.manualIphone.router || "unknown" },
    { label: "DNS", value: gateway?.manualIphone.dns || "unknown" },
    { label: "Host LAN", value: gateway ? `${gateway.server} on ${gateway.interface}` : "unknown" },
    { label: "Upstream", value: gateway?.gateway || "unknown" },
    { label: "nft", value: gateway?.nft.state || "unknown" }
  ];
  const commands = [
    gateway?.commands.check,
    gateway?.commands.rootApply,
    gateway?.commands.rootRemove
  ].filter(Boolean) as string[];
  const text = [...rows.map((row) => rowText(row.label, row.value)), ...commands].join("\n");

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2><Router size={18} /> LAN Gateway</h2>
          <p>Single-iPhone manual-router mode; root takeover stays terminal-gated.</p>
        </div>
        <button className="icon-button" onClick={() => void navigator.clipboard.writeText(text)} title="Copy LAN gateway settings">
          <Copy size={17} />
          <span>Copy</span>
        </button>
      </div>

      {gateway?.errors.length ? (
        <div className="banner warn">{gateway.errors.join(", ")}</div>
      ) : null}

      <dl className="settings-list">
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>

      <div className="command-list">
        <div>
          <strong>Check</strong>
          <span>{gateway?.commands.check || "~/.local/bin/proxy-stack lan-gateway-plan"}</span>
        </div>
        <div>
          <strong>Apply</strong>
          <span>{gateway?.commands.rootApply || "sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip <iphone-ip>"}</span>
        </div>
        <div>
          <strong>Rollback</strong>
          <span>{gateway?.commands.rootRemove || "sudo ~/.local/bin/proxy-stack lan-gateway-root-remove"}</span>
        </div>
      </div>
    </section>
  );
}
