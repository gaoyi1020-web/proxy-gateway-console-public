import { Copy, Smartphone } from "lucide-react";
import type { StatusResponse } from "../lib/types";

function defaultRouteSource(defaultRoute = "") {
  const parts = defaultRoute.split(/\s+/);
  const index = parts.indexOf("src");
  return index >= 0 ? parts[index + 1] ?? "" : "";
}

function settingRows(status: StatusResponse | null) {
  const gateway = "10.42.0.1 when GY-Hotspot is active";
  const lanIp = defaultRouteSource(status?.environment.defaultRoute);
  const iphoneLan = status?.iphoneLanProxy;
  const phone = status?.statuses.find((item) => item.id === "phone-canary");
  const old = status?.statuses.find((item) => item.id === "main-download");
  const app = status?.statuses.find((item) => item.id === "app-failover");
  const split = status?.statuses.find((item) => item.id === "hotspot-split");
  const guard = status?.hotspotPreflight;
  return [
    { label: "Hotspot gateway", value: gateway },
    { label: "Split DNS port", value: "1053" },
    { label: "Split TCP port", value: "12345" },
    { label: "App failover proxy", value: "127.0.0.1:18180" },
    { label: "iPhone Wi-Fi proxy", value: iphoneLan?.setting || (lanIp ? `${lanIp}:18181` : "LAN-IP:18181") },
    { label: "iPhone proxy target", value: iphoneLan?.target || "CN/private direct, foreign -> 127.0.0.1:18122" },
    { label: "iPhone auth", value: iphoneLan?.authentication ? "on" : "off" },
    { label: "iPhone firewall", value: iphoneLan?.firewall.summary || iphoneLan?.firewall.status || "unknown" },
    { label: "Hotspot guard", value: guard ? `${guard.risk}: ${guard.message}` : "unknown" },
    { label: "Phone route status", value: phone?.summary ?? "unknown" },
    { label: "Download route status", value: old?.summary ?? "unknown" },
    { label: "App failover status", value: app?.summary ?? "unknown" },
    { label: "Split gateway status", value: split?.summary ?? "unknown" }
  ];
}

export default function PhoneSetup({ status }: { status: StatusResponse | null }) {
  const rows = settingRows(status);
  const text = rows.map((row) => `${row.label}: ${row.value}`).join("\n");
  const iphoneLan = status?.iphoneLanProxy;
  const recentClients = iphoneLan?.recentClients.slice(-5).reverse() ?? [];
  const recentUpstreams = iphoneLan?.recentUpstreams.slice(-5).reverse() ?? [];

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2><Smartphone size={18} /> Hotspot Setup</h2>
          <p>iPhone Wi-Fi proxy uses LAN port 18181 with CN/private direct and foreign targets through the new 18122 route.</p>
        </div>
        <button className="icon-button" onClick={() => void navigator.clipboard.writeText(text)} title="Copy phone settings">
          <Copy size={17} />
          <span>Copy</span>
        </button>
      </div>
      <dl className="settings-list">
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      {iphoneLan ? (
        <div className="phone-lan-status">
          <div>
            <strong>LAN proxy</strong>
            <span>{iphoneLan.setting}{" -> "}{iphoneLan.target}</span>
          </div>
          <div>
            <strong>Firewall</strong>
            <span>{iphoneLan.firewall.status}</span>
          </div>
          <div>
            <strong>Clients</strong>
            {recentClients.length > 0 ? (
              recentClients.map((client) => (
                <span key={`${client.timestamp}-${client.ip}-${client.port}`}>
                  {client.ip}:{client.port} {client.local ? "(local)" : ""}
                </span>
              ))
            ) : (
              <span>none</span>
            )}
          </div>
          <div>
            <strong>Proxy targets</strong>
            {recentUpstreams.length > 0 ? (
              recentUpstreams.map((item) => (
                <span key={`${item.timestamp}-${item.target}-${item.route}`}>
                  {item.target} via {item.route}
                </span>
              ))
            ) : (
              <span>none</span>
            )}
          </div>
        </div>
      ) : null}
      <div className="route-split">
        <div>
          <strong>Domestic</strong>
          <span>{"CN/private -> direct"}</span>
        </div>
        <div>
          <strong>Foreign</strong>
          <span>{"foreign -> 18122"}</span>
        </div>
        <div>
          <strong>Guard</strong>
          <span>{status?.hotspotPreflight?.risk ?? "unknown"}</span>
        </div>
      </div>
    </section>
  );
}
