import { Activity, CheckCircle2, CircleAlert, Router, ShieldAlert, Smartphone } from "lucide-react";
import type { StatusResponse } from "../lib/types";
import { buildFeatureStates, type ControlState, stateFromLink, statusById } from "./linuxWorkbenchModel";

function toneClass(state: ControlState) {
  return state;
}

function statusTone(status: StatusResponse | null): ControlState {
  const phoneOk = Boolean(status?.iphoneLanProxy?.portOpen);
  const failoverOk = stateFromLink(statusById(status, "app-failover")) === "ok";
  const pendingEvents = status?.networkEvents.pending.length ?? 0;
  if (!status) {
    return "off";
  }
  if (pendingEvents > 0 || status.hotspotPreflight?.allowed === false) {
    return phoneOk || failoverOk ? "warn" : "off";
  }
  return phoneOk || failoverOk ? "ok" : "warn";
}

function statusText(state: ControlState) {
  if (state === "ok") {
    return "可用";
  }
  if (state === "warn") {
    return "需关注";
  }
  return "等待状态";
}

export default function LinuxStatusSummary({ status, loading }: { status: StatusResponse | null; loading: boolean }) {
  const tone = statusTone(status);
  const phone = status?.iphoneLanProxy;
  const failover = statusById(status, "app-failover");
  const guard = status?.hotspotPreflight;
  const pendingEvents = status?.networkEvents.pending.length ?? 0;
  const features = buildFeatureStates(status);

  return (
    <section className="workbench-panel linux-status-summary" aria-label="Linux status summary">
      <div className="workbench-panel-head">
        <div>
          <h2>运行状态</h2>
          <p>{loading ? "正在刷新状态" : "本机网络、手机入口和当前事件"}</p>
        </div>
        <span className={`state-pill ${tone}`}>{statusText(tone)}</span>
      </div>

      <div className="linux-status-tiles">
        <article className={`linux-status-tile ${phone?.portOpen ? "ok" : "off"}`}>
          <Smartphone size={18} />
          <span>
            <strong>手机入口</strong>
            <small>{phone?.setting || "等待 LAN 代理"}</small>
          </span>
        </article>
        <article className={`linux-status-tile ${failover?.active ? "ok" : "off"}`}>
          <Router size={18} />
          <span>
            <strong>本机代理</strong>
            <small>{failover?.summary || "等待 failover 状态"}</small>
          </span>
        </article>
        <article className={`linux-status-tile ${guard?.allowed ? "ok" : guard ? "warn" : "off"}`}>
          {guard?.allowed ? <CheckCircle2 size={18} /> : <ShieldAlert size={18} />}
          <span>
            <strong>热点保护</strong>
            <small>{guard ? guard.risk : "等待预检"}</small>
          </span>
        </article>
        <article className={`linux-status-tile ${pendingEvents ? "warn" : "ok"}`}>
          {pendingEvents ? <CircleAlert size={18} /> : <Activity size={18} />}
          <span>
            <strong>网络事件</strong>
            <small>{pendingEvents ? `${pendingEvents} 个待选择` : "无待处理事件"}</small>
          </span>
        </article>
      </div>

      <div className="workbench-route">
        <strong>当前网络</strong>
        <small>{status?.environment.defaultRoute || "等待状态刷新"}</small>
      </div>

      <details className="workbench-diagnostics">
        <summary>诊断状态</summary>
        <div className="control-grid compact">
          {features.map((feature) => {
            const Icon = feature.Icon;
            return (
              <article className={`control-card compact ${toneClass(feature.state)}`} key={feature.id}>
                <div className="control-icon">
                  <Icon size={18} />
                </div>
                <div>
                  <h2>{feature.label}</h2>
                  <p>{feature.summary}</p>
                </div>
                <span className={`state-pill ${feature.state}`}>{feature.value}</span>
              </article>
            );
          })}
        </div>
      </details>
    </section>
  );
}
