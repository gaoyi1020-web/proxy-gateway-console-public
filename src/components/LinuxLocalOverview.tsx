import { CheckCircle2, CircleAlert, Router, ShieldCheck, Smartphone } from "lucide-react";
import type { StatusResponse } from "../lib/types";

function tone(ok: boolean | undefined) {
  if (ok === undefined) {
    return "off";
  }
  return ok ? "ok" : "warn";
}

export default function LinuxLocalOverview({ status }: { status: StatusResponse | null }) {
  const iphone = status?.iphoneLanProxy;
  const lifecycle = status?.linuxLifecycle;
  const packageReady = lifecycle?.service.present || lifecycle?.wrapper.present;
  const pendingEvents = status?.networkEvents.pending.length ?? 0;

  return (
    <section className="linux-v4-overview" aria-label="Linux local overview">
      <article className={`linux-v4-tile ${tone(packageReady)}`}>
        <ShieldCheck size={20} />
        <span>
          <strong>本机控制</strong>
          <small>{packageReady ? "已接管本机控制层" : "等待安装控制层"}</small>
        </span>
      </article>
      <article className={`linux-v4-tile ${tone(iphone?.portOpen)}`}>
        <Smartphone size={20} />
        <span>
          <strong>手机入口</strong>
          <small>{iphone?.setting || "等待 LAN 代理"}</small>
        </span>
      </article>
      <article className={`linux-v4-tile ${pendingEvents ? "warn" : "ok"}`}>
        {pendingEvents ? <CircleAlert size={20} /> : <CheckCircle2 size={20} />}
        <span>
          <strong>网络事件</strong>
          <small>{pendingEvents ? `${pendingEvents} 个待选择` : "无待处理事件"}</small>
        </span>
      </article>
      <article className="linux-v4-tile off">
        <Router size={20} />
        <span>
          <strong>当前网络</strong>
          <small>{status?.environment.defaultRoute || "等待状态刷新"}</small>
        </span>
      </article>
    </section>
  );
}
