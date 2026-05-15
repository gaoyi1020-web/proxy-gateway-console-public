import { AlertTriangle, CheckCircle2, Clock, Network, TerminalSquare } from "lucide-react";
import type { NetworkEvent, NetworkEventsResponse, StatusResponse } from "../lib/types";
import type { WorkbenchActionLogEntry, WorkbenchApiErrorEntry } from "./webWorkbenchTypes";

function redact(value: string) {
  return value
    .replace(/(password|token|auth|secret)=\S+/gi, "$1=[redacted]")
    .replace(/profile\.json\.enc/gi, "[encrypted-profile]")
    .replace(/upstream\.json/gi, "[upstream-config]");
}

function eventText(event: NetworkEvent) {
  return redact(event.message || event.type || event.id);
}

export default function LogsPage({
  status,
  networkEvents,
  actionLog,
  apiErrorLog
}: {
  status: StatusResponse | null;
  networkEvents: NetworkEventsResponse | null;
  actionLog: WorkbenchActionLogEntry[];
  apiErrorLog: WorkbenchApiErrorEntry[];
}) {
  const latestAction = actionLog[0];
  const events = networkEvents?.events ?? [];
  const pending = networkEvents?.pending ?? [];
  const gatewayErrors = status?.gatewayAgent?.errors ?? [];
  const recentClients = status?.iphoneLanProxy?.recentClients ?? [];

  return (
    <section className="logs-page" aria-label="Logs">
      <div className="panel-heading">
        <div>
          <h2>日志</h2>
          <p>当前浏览器会话活动和脱敏状态摘要。</p>
        </div>
      </div>

      <div className="logs-grid">
        <article className="workbench-panel log-panel">
          <h2>
            <CheckCircle2 size={18} />
            最新动作
          </h2>
          {latestAction ? (
            <p>{latestAction.label}：{latestAction.ok ? "完成" : "失败"}，{redact(latestAction.message)}</p>
          ) : (
            <p>暂无记录</p>
          )}
        </article>

        <article className="workbench-panel log-panel">
          <h2>
            <AlertTriangle size={18} />
            API 错误
          </h2>
          {apiErrorLog.length ? (
            <ul>{apiErrorLog.slice(0, 6).map((item) => <li key={item.id}>{item.scope}：{redact(item.message)}</li>)}</ul>
          ) : (
            <p>暂无记录</p>
          )}
        </article>

        <article className="workbench-panel log-panel">
          <h2>
            <Network size={18} />
            网络事件
          </h2>
          {events.length || pending.length ? (
            <ul>
              {[...pending, ...events].slice(0, 8).map((event) => (
                <li key={event.id}>{event.status}：{eventText(event)}</li>
              ))}
            </ul>
          ) : (
            <p>等待刷新</p>
          )}
        </article>

        <article className="workbench-panel log-panel">
          <h2>
            <TerminalSquare size={18} />
            状态摘要
          </h2>
          <ul>
            <li>网关：{redact(status?.gatewayAgent?.summary || "等待刷新")}</li>
            <li>手机客户端：{recentClients.length} 个近期记录</li>
            <li>网关错误：{gatewayErrors.length} 条</li>
          </ul>
        </article>

        <article className="workbench-panel log-panel wide">
          <h2>
            <Clock size={18} />
            动作历史
          </h2>
          {actionLog.length ? (
            <ul>{actionLog.slice(0, 10).map((item) => <li key={item.id}>{item.at}：{item.label}：{redact(item.message)}</li>)}</ul>
          ) : (
            <p>暂无记录</p>
          )}
        </article>
      </div>
    </section>
  );
}
