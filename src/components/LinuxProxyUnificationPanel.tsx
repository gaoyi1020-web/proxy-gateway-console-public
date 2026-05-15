import { CircleAlert, GitMerge, Network, ShieldCheck } from "lucide-react";
import type { LinuxProxyUnificationStatus, ProxyUnifiedEndpoint } from "../lib/types";

const PHASE_LABELS: Record<LinuxProxyUnificationStatus["optimizationReadiness"]["phase"], string> = {
  "observe-only": "观察模式",
  "dispatcher-candidate": "候选切换",
  "dispatcher-active": "已接管"
};

function endpointText(endpoint: ProxyUnifiedEndpoint) {
  if (!endpoint.port) {
    return endpoint.open ? endpoint.host : "root-gated";
  }
  return `${endpoint.host}:${endpoint.port}`;
}

export default function LinuxProxyUnificationPanel({
  proxyUnification
}: {
  proxyUnification: LinuxProxyUnificationStatus | null;
}) {
  if (!proxyUnification) {
    return null;
  }

  return (
    <section className="workbench-panel linux-v5-unification compact" aria-label="Linux proxy unification">
      <div className="linux-v5-head">
        <GitMerge size={20} />
        <span>
          <strong>代理状态</strong>
          <small>{proxyUnification.mode === "read-only" ? "只读状态" : proxyUnification.mode}</small>
        </span>
        <span className="linux-v5-count">{proxyUnification.versionCount} 个上游配置</span>
      </div>

      <div className="linux-v5-adapters primary">
        {proxyUnification.adapters.slice(0, 3).map((item) => (
          <span key={item.id} className={item.ready ? "ok" : "warn"}>
            <Network size={14} />
            {item.label}: {endpointText(item.endpoint)}
          </span>
        ))}
      </div>

      <details className="linux-v5-external">
        <summary>代理详情</summary>
        <div className="linux-v5-readiness">
          <div>
            <strong>优化阶段：{PHASE_LABELS[proxyUnification.optimizationReadiness.phase]}</strong>
            <small>
              Dispatcher {proxyUnification.optimizationReadiness.dispatcherActive ? "已接管" : "未接管"}
            </small>
          </div>
          <div className="linux-v5-readiness-grid">
            <div>
              <small>阻塞项</small>
              <ul>
                {proxyUnification.optimizationReadiness.blockers.map((blocker) => (
                  <li key={blocker}>{blocker}</li>
                ))}
              </ul>
            </div>
            <div>
              <small>安全下一步</small>
              <ul>
                {proxyUnification.optimizationReadiness.safeNextSteps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
        <div className="linux-v5-grid">
          {proxyUnification.upstreams.map((item) => (
            <article key={item.id} className={`linux-v5-card ${item.ready ? "ok" : "warn"}`}>
              <ShieldCheck size={18} />
              <div>
                <strong>{item.label}</strong>
                <small>
                  HTTP {endpointText(item.http)} / SOCKS {endpointText(item.socks)}
                </small>
              </div>
            </article>
          ))}
        </div>
        <div className="linux-v5-adapters">
          {proxyUnification.adapters.slice(3).map((item) => (
            <span key={item.id} className={item.ready ? "ok" : "warn"}>
              <Network size={14} />
              {item.label}: {endpointText(item.endpoint)}
            </span>
          ))}
        </div>
        {proxyUnification.externalServices.length ? (
          proxyUnification.externalServices.map((item) => (
            <p key={item.name}>
              <CircleAlert size={14} />
              <span>
                {item.name} · {item.classification} · {item.risk}
              </span>
            </p>
          ))
        ) : null}
      </details>
    </section>
  );
}
