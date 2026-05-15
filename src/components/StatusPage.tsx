import { Clock, Route } from "lucide-react";
import type { LinuxDesktopPackageStatus, LinuxProxyUnificationStatus, StatusResponse } from "../lib/types";
import FeatureStateList from "./FeatureStateList";
import LinuxProxyUnificationPanel from "./LinuxProxyUnificationPanel";
import LinuxRuntimeStatePanel from "./LinuxRuntimeStatePanel";

export default function StatusPage({
  status,
  packageStatus,
  proxyUnification
}: {
  status: StatusResponse | null;
  packageStatus: LinuxDesktopPackageStatus | null;
  proxyUnification: LinuxProxyUnificationStatus | null;
}) {
  const route = status?.environment.defaultRoute || "等待刷新";
  const generatedAt = status?.generatedAt ? new Date(status.generatedAt).toLocaleString() : "等待刷新";

  return (
    <section className="status-page" aria-label="Status">
      <div className="panel-heading">
        <div>
          <h2>状态</h2>
          <p>只读诊断，不执行服务动作。</p>
        </div>
      </div>

      <div className="status-overview-grid">
        <article className="workbench-panel route-summary">
          <h2>
            <Route size={18} />
            当前默认路由
          </h2>
          <p>{route}</p>
        </article>
        <article className="workbench-panel route-summary">
          <h2>
            <Clock size={18} />
            生成时间
          </h2>
          <p>{generatedAt}</p>
        </article>
      </div>

      <section className="workbench-panel status-feature-panel" aria-label="Feature states">
        <div className="workbench-panel-head">
          <div>
            <h2>功能状态</h2>
            <p>这里的条目均为只读状态。</p>
          </div>
        </div>
        <FeatureStateList status={status} mode="readOnly" />
      </section>

      <div className="status-diagnostics-grid">
        <LinuxRuntimeStatePanel status={status} packageStatus={packageStatus} proxyUnification={proxyUnification} />
        <LinuxProxyUnificationPanel proxyUnification={proxyUnification} />
      </div>
    </section>
  );
}
