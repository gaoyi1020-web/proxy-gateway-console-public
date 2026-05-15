import { Activity, FileText, Gauge, ListChecks, RefreshCw, Settings, ShieldAlert, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import type { NetworkEventsResponse, StatusResponse } from "../lib/types";
import type { WebWorkbenchView } from "./webWorkbenchTypes";

const navItems: Array<{ id: WebWorkbenchView; label: string; Icon: LucideIcon }> = [
  { id: "operations", label: "操作", Icon: ListChecks },
  { id: "config", label: "配置", Icon: Settings },
  { id: "status", label: "状态", Icon: Gauge },
  { id: "logs", label: "日志", Icon: FileText }
];

export default function WebWorkbenchLayout({
  activeView,
  onViewChange,
  status,
  networkEvents,
  loading,
  error,
  onRefresh,
  children
}: {
  activeView: WebWorkbenchView;
  onViewChange: (view: WebWorkbenchView) => void;
  status: StatusResponse | null;
  networkEvents: NetworkEventsResponse | null;
  loading: boolean;
  error?: string;
  onRefresh: () => void;
  children: ReactNode;
}) {
  const guard = status?.hotspotPreflight;
  const iphone = status?.iphoneLanProxy;
  const pendingEvents = networkEvents?.pending.length ?? 0;
  const refreshedAt = status?.generatedAt ? new Date(status.generatedAt).toLocaleTimeString() : "等待刷新";

  function renderNav(className: string, label: string) {
    return (
      <nav className={className} aria-label={label}>
        {navItems.map(({ id, label: itemLabel, Icon }) => (
          <button
            type="button"
            key={id}
            className={activeView === id ? "active" : ""}
            onClick={() => onViewChange(id)}
          >
            <Icon size={17} />
            <span>{itemLabel}</span>
          </button>
        ))}
      </nav>
    );
  }

  return (
    <main className="app-shell web-workbench-shell">
      <aside className="web-workbench-sidebar" aria-label="Workbench navigation">
        <div className="web-workbench-brand">
          <ShieldCheck size={20} />
          <span>
            <strong>代理网关</strong>
            <small>本机工作台</small>
          </span>
        </div>
        {renderNav("web-workbench-nav", "Primary view")}
      </aside>

      <section className="web-workbench-main">
        <header className="web-workbench-header">
          <div>
            <h1>代理网关控制台</h1>
            <p>操作、配置、状态和日志分区管理。</p>
          </div>
          <button className="icon-button" onClick={onRefresh} disabled={loading} title="Refresh status">
            <RefreshCw className={loading ? "spin" : ""} size={18} />
            <span>{loading ? "刷新中" : "刷新"}</span>
          </button>
        </header>

        {renderNav("web-workbench-mobile-nav", "Mobile primary view")}

        {error ? <div className="banner danger">API error: {error}</div> : null}

        <section className="web-summary-strip" aria-label="System summary">
          <div>
            <ShieldCheck size={18} />
            <span>{iphone?.setting || "手机入口等待中"}</span>
          </div>
          <div>
            {guard?.allowed ? <ShieldCheck size={18} /> : <ShieldAlert size={18} />}
            <span>{guard ? `保护状态：${guard.risk}` : "保护状态等待中"}</span>
          </div>
          <div>
            <Activity size={18} />
            <span>{pendingEvents ? `待处理事件：${pendingEvents}` : "待处理事件：0"}</span>
          </div>
          <div>
            <Gauge size={18} />
            <span>{refreshedAt}</span>
          </div>
        </section>

        <section className="web-workbench-content">{children}</section>
      </section>
    </main>
  );
}
