import { CheckCircle2, CircleAlert, Network, Router, Server, Smartphone, Wifi } from "lucide-react";
import type { LinkDefinition, LinkStatus, StatusResponse } from "../lib/types";

const icons = {
  "main-download": Server,
  "phone-canary": Smartphone,
  "app-failover": Network,
  "hotspot-split": Wifi,
  "lan-gateway": Router
};

function StatusPill({ active }: { active: boolean }) {
  const Icon = active ? CheckCircle2 : CircleAlert;
  return (
    <span className={active ? "pill ok" : "pill warn"}>
      <Icon size={14} />
      {active ? "Available" : "Attention"}
    </span>
  );
}

function LinkCard({ link, status }: { link: LinkDefinition; status?: LinkStatus }) {
  const Icon = icons[link.id];
  return (
    <article className="link-card">
      <div className="card-heading">
        <div className="link-icon">
          <Icon size={21} />
        </div>
        <div>
          <h2>{link.name}</h2>
          <p>{link.role}</p>
        </div>
        <StatusPill active={Boolean(status?.active)} />
      </div>

      <dl className="detail-list">
        <div>
          <dt>Mode</dt>
          <dd>{link.mode}</dd>
        </div>
        <div>
          <dt>Route</dt>
          <dd>{link.route}</dd>
        </div>
        <div>
          <dt>Ports</dt>
          <dd>{link.ports.join(", ")}</dd>
        </div>
      </dl>

      <div className="probe-list">
        {status
          ? Object.entries(status.probes).map(([key, probe]) => (
              <div className="probe-row" key={key}>
                <span>{key}</span>
                <strong className={probe.ok ? "text-ok" : "text-warn"}>{probe.value}</strong>
              </div>
            ))
          : <div className="probe-row"><span>status</span><strong>loading</strong></div>}
      </div>

      <p className="risk-note">{link.risk}</p>
    </article>
  );
}

export default function Dashboard({ status, loading }: { status: StatusResponse | null; loading: boolean }) {
  const links = status?.links ?? [];
  const statuses = new Map(status?.statuses.map((item) => [item.id, item]));

  if (loading && links.length === 0) {
    return <section className="dashboard-grid"><div className="skeleton">Loading link inventory</div></section>;
  }

  return (
    <section className="dashboard-grid" aria-label="Link dashboard">
      {links.map((link) => (
        <LinkCard key={link.id} link={link} status={statuses.get(link.id)} />
      ))}
    </section>
  );
}
