import { CheckCircle2, CircleAlert, FileLock2, PackageCheck, Route, Server } from "lucide-react";
import type { LinuxDesktopPackageStatus, LinuxProxyUnificationStatus, StatusResponse } from "../lib/types";

function stateClass(ok: boolean | undefined) {
  if (ok === undefined) {
    return "off";
  }
  return ok ? "ok" : "warn";
}

function endpointText(endpoint?: { host: string; port: number; open: boolean }) {
  if (!endpoint) {
    return "等待状态";
  }
  return endpoint.port ? `${endpoint.host}:${endpoint.port}` : endpoint.host;
}

function upstreamReady(proxyUnification: LinuxProxyUnificationStatus | null, id: string) {
  return proxyUnification?.upstreams.find((item) => item.id === id)?.ready;
}

export default function LinuxRuntimeStatePanel({
  status,
  packageStatus,
  proxyUnification
}: {
  status: StatusResponse | null;
  packageStatus: LinuxDesktopPackageStatus | null;
  proxyUnification: LinuxProxyUnificationStatus | null;
}) {
  const profilePresent = status?.linuxLifecycle?.config.profilePresent;
  const packageOk = packageStatus?.ok;
  const newReady = upstreamReady(proxyUnification, "new");
  const oldReady = upstreamReady(proxyUnification, "old");
  const currentHttp = proxyUnification?.unifiedEntry.currentHttp;

  return (
    <section className="workbench-panel runtime-state-panel" aria-label="Runtime state">
      <div className="workbench-panel-head">
        <div>
          <h2>运行状态</h2>
          <p>对应左侧开关的配置、出口和代理状态。</p>
        </div>
      </div>

      <div className="runtime-state-grid">
        <article className={`runtime-state-card ${stateClass(profilePresent)}`}>
          <FileLock2 size={18} />
          <span>
            <strong>配置</strong>
            <small>{profilePresent ? "已导入" : "未导入"}</small>
          </span>
        </article>
        <article className={`runtime-state-card ${stateClass(packageOk)}`}>
          <PackageCheck size={18} />
          <span>
            <strong>桌面包</strong>
            <small>{packageStatus?.launcherMode || "unknown"}</small>
          </span>
        </article>
        <article className={`runtime-state-card ${stateClass(currentHttp?.open)}`}>
          <Route size={18} />
          <span>
            <strong>统一出口</strong>
            <small>{endpointText(currentHttp)}</small>
          </span>
        </article>
        <article className={`runtime-state-card ${stateClass(newReady)}`}>
          {newReady ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}
          <span>
            <strong>新代理</strong>
            <small>{newReady ? "可用" : "需关注"}</small>
          </span>
        </article>
        <article className={`runtime-state-card ${stateClass(oldReady)}`}>
          <Server size={18} />
          <span>
            <strong>旧代理</strong>
            <small>{oldReady ? "备用可用" : "需关注"}</small>
          </span>
        </article>
      </div>

      <div className="workbench-route compact">
        <strong>当前网络</strong>
        <small>{status?.environment.defaultRoute || "等待状态刷新"}</small>
      </div>
    </section>
  );
}
