import {
  Activity,
  CheckCircle2,
  Power,
  PowerOff,
  Radar,
  RefreshCw,
  Router,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Wifi
} from "lucide-react";
import type { ActionDefinition, LinkId, LinkStatus, StatusResponse } from "../lib/types";

export type ControlState = "ok" | "warn" | "off";
export type FeatureControlKind = "toggle" | "action" | "status";

export interface FeatureControl {
  kind: FeatureControlKind;
  actionId?: string;
}

export interface FeatureState {
  id: string;
  label: string;
  summary: string;
  value: string;
  state: ControlState;
  Icon: typeof Shield;
  control: FeatureControl;
}

export const actionIcons: Record<string, typeof Shield> = {
  "self-check": ShieldCheck,
  "gateway-agent-start": Power,
  "linux-v3-stop": PowerOff,
  "linux-v3-uninstall-plan": ShieldAlert,
  "hotspot-preflight": Radar,
  "hotspot-start-safe": Power,
  "restart-user": PowerOff,
  "update-cn": RefreshCw
};

export const visibleActions = new Set([
  "self-check",
  "gateway-agent-start",
  "linux-v3-stop",
  "linux-v3-uninstall-plan",
  "restart-user",
  "hotspot-preflight",
  "hotspot-start-safe",
  "update-cn"
]);

export const primaryActions = new Set(["self-check", "gateway-agent-start", "linux-v3-stop", "linux-v3-uninstall-plan", "restart-user"]);
export const maintenanceActions = new Set(["hotspot-preflight", "hotspot-start-safe", "update-cn"]);

export const actionLabels: Record<string, string> = {
  "self-check": "自检",
  "gateway-agent-start": "启动桌面会话",
  "linux-v3-stop": "停止本机控制层",
  "linux-v3-uninstall-plan": "生成卸载命令",
  "restart-user": "重启代理服务",
  "hotspot-preflight": "热点预检",
  "hotspot-start-safe": "安全启动热点",
  "update-cn": "更新 CN 分流"
};

export const actionDescriptions: Record<string, string> = {
  "self-check": "刷新服务、端口、分流和手机入口状态。",
  "gateway-agent-start": "创建桌面端本机会话，不修改 root 网络规则。",
  "linux-v3-stop": "停止桌面会话和运行态，保留配置。",
  "linux-v3-uninstall-plan": "显示项目文件全清命令，必须在终端确认。",
  "restart-user": "重启用户态代理链路，不触碰系统 root 规则。",
  "hotspot-preflight": "检查热点启动是否会断开当前上游网络。",
  "hotspot-start-safe": "只在预检允许时启动热点。",
  "update-cn": "刷新国内 IPv4 分流表。"
};

export const defaultActions: ActionDefinition[] = [
  { id: "self-check", label: actionLabels["self-check"], description: actionDescriptions["self-check"], risk: "safe" },
  { id: "gateway-agent-start", label: actionLabels["gateway-agent-start"], description: actionDescriptions["gateway-agent-start"], risk: "safe" },
  { id: "linux-v3-stop", label: actionLabels["linux-v3-stop"], description: actionDescriptions["linux-v3-stop"], risk: "safe" },
  { id: "linux-v3-uninstall-plan", label: actionLabels["linux-v3-uninstall-plan"], description: actionDescriptions["linux-v3-uninstall-plan"], risk: "caution" },
  { id: "restart-user", label: actionLabels["restart-user"], description: actionDescriptions["restart-user"], risk: "caution" },
  { id: "hotspot-preflight", label: actionLabels["hotspot-preflight"], description: actionDescriptions["hotspot-preflight"], risk: "safe" },
  { id: "hotspot-start-safe", label: actionLabels["hotspot-start-safe"], description: actionDescriptions["hotspot-start-safe"], risk: "caution" },
  { id: "update-cn", label: actionLabels["update-cn"], description: actionDescriptions["update-cn"], risk: "safe" }
];

export const dailyOperationActions = new Set(["self-check", "gateway-agent-start", "linux-v3-stop"]);
export const defaultDailyActions = defaultActions.filter((action) => dailyOperationActions.has(action.id));

export function statusById(status: StatusResponse | null, id: LinkId) {
  return status?.statuses.find((item) => item.id === id);
}

export function stateFromLink(link?: LinkStatus): ControlState {
  if (!link) {
    return "off";
  }
  return link.active ? "ok" : "warn";
}

export function stateText(state: ControlState) {
  if (state === "ok") {
    return "运行中";
  }
  if (state === "warn") {
    return "需关注";
  }
  return "等待中";
}

export function stateFromProbe(ok?: boolean): ControlState {
  if (ok === undefined) {
    return "off";
  }
  return ok ? "ok" : "warn";
}

function displaySummary(value: string | undefined, fallback: string) {
  if (!value) {
    return fallback;
  }
  return value
    .replace(/Linux v[2-5] control layer is installed/gi, "本机控制层已安装")
    .replace(/Gateway agent v[2-5] status is ready/gi, "桌面会话状态可用")
    .replace(/Gateway agent v[2-5] status is unavailable/gi, "桌面会话状态不可用")
    .replace(/v[2-5]\s+agent disabled; v1 fallback remains active/gi, "桌面会话未启用；当前备用通道保持可用")
    .replace(/v[2-5]\s+agent enabled but locked; no session manifest exists/gi, "桌面会话已启用但未解锁；尚无本机会话")
    .replace(/v[2-5]\s+LAN proxy child is running; v1 fallback remains active/gi, "局域网会话运行中；当前备用通道保持可用")
    .replace(/v[2-5]\s+LAN proxy child (?:failed to start|started); v1 fallback remains active/gi, "局域网会话状态已更新；当前备用通道保持可用")
    .replace(/v[2-5]\s+session manifest removed; v1 fallback remains active/gi, "桌面会话已停止；当前备用通道保持可用")
    .replace(/set GATEWAY_AGENT_V[2-5]=1 to create a v[2-5]\s+session manifest/gi, "桌面会话未启用")
    .replace(/stale v[2-5]\s+child state cleaned; session manifest preserved/gi, "过期会话状态已清理；本机会话保留")
    .replace(/v[2-5]\s+local profile source disappeared; session locked and child services stopped/gi, "本地配置来源不可用；会话已锁定并停止")
    .replace(/v[2-5]\s+session manifest is ready; no network child services are started in this slice/gi, "桌面会话清单已就绪；未启动网络子服务")
    .replace(/v[2-5]\s+session manifest is ready/gi, "桌面会话清单已就绪")
    .replace(/session manifest (?:exists|present)/gi, "本机会话清单已存在")
    .replace(/session manifest not present/gi, "本机会话清单不存在")
    .replace(/v[2-5]\s+session manifest/gi, "桌面会话清单")
    .replace(/v[2-5]\s+local profile/gi, "本地配置")
    .replace(/^local$/gi, "本地配置")
    .replace(/v[2-5]\s+unlock active/gi, "本机已解锁")
    .replace(/v[2-5]\s+LAN listener is open/gi, "局域网入口已打开")
    .replace(/LAN listener is bound to loopback and cannot be used by a phone; keep using v1 iPhone LAN proxy if needed/gi, "局域网入口仅绑定本机，手机请使用当前手机入口配置")
    .replace(/LAN listener is off; keep using v1 iPhone LAN proxy if needed/gi, "局域网入口未开启，手机请使用当前手机入口配置")
    .replace(/LAN listener settings are invalid; keep using v1 iPhone LAN proxy if needed/gi, "局域网入口配置异常，手机请使用当前手机入口配置")
    .replace(/LAN listener is recorded in the session but is not currently listening; keep using v1 iPhone LAN proxy if needed/gi, "局域网入口已记录但未监听，手机请使用当前手机入口配置")
    .replace(/LAN listener disabled/gi, "局域网入口未启用")
    .replace(/LAN listener ready/gi, "局域网入口可用")
    .replace(/LAN listener is open/gi, "局域网入口已打开")
    .replace(/v[1-5]/gi, "当前");
}

export function buildFeatureStates(status: StatusResponse | null): FeatureState[] {
  const phone = statusById(status, "phone-canary");
  const main = statusById(status, "main-download");
  const failover = statusById(status, "app-failover");
  const split = statusById(status, "hotspot-split");
  const lan = status?.lanGateway;
  const guard = status?.hotspotPreflight;
  const phoneProxy = status?.iphoneLanProxy;
  const linuxLifecycle = status?.linuxLifecycle;
  const gatewayAgent = status?.gatewayAgent;
  const pendingEvents = status?.networkEvents.pending.length ?? 0;
  const gatewaySessionActive = Boolean(gatewayAgent?.probes.session?.ok) || gatewayAgent?.state === "manifest_ready";

  const features: FeatureState[] = [
    {
      id: "phone",
      label: "手机智能代理",
      summary: "国内/私网直连，国外走新代理",
      value: phoneProxy?.setting || "LAN-IP:18181",
      state: phoneProxy?.portOpen && phoneProxy.firewall.status === "effective_open" ? "ok" : stateFromLink(phone),
      Icon: Smartphone,
      control: { kind: "action", actionId: "self-check" }
    },
    {
      id: "main",
      label: "本机主代理",
      summary: "本机下载和当前项目默认路线",
      value: stateText(stateFromLink(main)),
      state: stateFromLink(main),
      Icon: Router,
      control: { kind: "status" }
    },
    {
      id: "failover",
      label: "应用 Failover",
      summary: "本机应用可选用的旧优先后备路线",
      value: stateText(stateFromLink(failover)),
      state: stateFromLink(failover),
      Icon: Activity,
      control: { kind: "status" }
    },
    {
      id: "split",
      label: "透明分流网关",
      summary: "热点和 LAN gateway 的 DNS/TCP 分流",
      value: stateText(stateFromLink(split)),
      state: stateFromLink(split),
      Icon: Wifi,
      control: { kind: "status" }
    },
    {
      id: "lan-gateway",
      label: "LAN 网关测试",
      summary: lan?.enabled ? `已绑定 ${lan.clientIp || "单台设备"}` : "保留为后续测试入口",
      value: lan?.enabled ? "已启用" : "未启用",
      state: lan?.enabled ? "ok" : "off",
      Icon: Router,
      control: { kind: "status" }
    },
    {
      id: "guard",
      label: "热点保护",
      summary: guard?.allowed ? "当前上游满足安全启动条件" : "阻止可能断开当前 Wi-Fi 的热点启动",
      value: guard ? guard.risk : "等待检测",
      state: guard ? (guard.allowed ? "ok" : "warn") : "off",
      Icon: guard?.allowed ? ShieldCheck : ShieldAlert,
      control: { kind: "status" }
    },
    {
      id: "events",
      label: "USB 网络事件",
      summary: pendingEvents > 0 ? "有待处理的手机网络选择" : "没有待处理事件",
      value: pendingEvents > 0 ? `${pendingEvents} pending` : "清空",
      state: pendingEvents > 0 ? "warn" : "ok",
      Icon: Smartphone,
      control: { kind: "status" }
    }
  ];

  if (linuxLifecycle) {
    features.push({
      id: "linux-v3-lifecycle",
      label: "本机控制层",
      summary: `${displaySummary(linuxLifecycle.summary, "本机控制层状态")}；停止保留配置`,
      value: linuxLifecycle.state || "unknown",
      state: linuxLifecycle.ok ? (linuxLifecycle.service.present || linuxLifecycle.wrapper.present ? "ok" : "off") : "warn",
      Icon: Shield,
      control: { kind: "status" }
    });
    features.push({
      id: "linux-v3-config",
      label: "控制层配置",
      summary: "停止保留配置；卸载终端确认",
      value: linuxLifecycle.config.profilePresent ? "配置已导入" : linuxLifecycle.config.present ? "配置目录存在" : "未配置",
      state: linuxLifecycle.config.profilePresent ? "ok" : linuxLifecycle.config.present ? "warn" : "off",
      Icon: CheckCircle2,
      control: { kind: "status" }
    });
  }

  if (gatewayAgent) {
    const probes = gatewayAgent.probes;
    features.push({
      id: "gateway-agent-v2",
      label: "局域网网关",
      summary: displaySummary(gatewayAgent.summary, "桌面会话状态"),
      value: gatewayAgent.enabled ? gatewayAgent.state : "未启用",
      state: gatewaySessionActive ? "ok" : gatewayAgent.enabled ? "off" : "off",
      Icon: Shield,
      control: { kind: "toggle", actionId: gatewaySessionActive ? "linux-v3-stop" : "gateway-agent-start" }
    });
    features.push({
      id: "gateway-agent-profile-source",
      label: "配置来源",
      summary: displaySummary(probes.profileSource?.detail, "本地配置优先，USB 仅作恢复介质"),
      value: probes.profileSource?.value || "未配置",
      state: stateFromProbe(probes.profileSource?.ok),
      Icon: ShieldCheck,
      control: { kind: "status" }
    });
    features.push({
      id: "gateway-agent-unlock",
      label: "解锁状态",
      summary: displaySummary(probes.unlock?.detail, "本机回环解锁状态"),
      value: probes.unlock?.value || "locked",
      state: stateFromProbe(probes.unlock?.ok),
      Icon: Shield,
      control: { kind: "status" }
    });
    features.push({
      id: "gateway-agent-session",
      label: "动态会话",
      summary: "动态端口只在本机会话清单内部记录",
      value: probes.session?.value || "missing",
      state: stateFromProbe(probes.session?.ok),
      Icon: Activity,
      control: { kind: "status" }
    });
    features.push({
      id: "gateway-agent-lan",
      label: "局域网服务",
      summary: displaySummary(probes.lanExposure?.detail, "默认不暴露局域网入口"),
      value: probes.lanExposure?.value || "关闭",
      state: probes.lanExposure?.ok ? "warn" : "off",
      Icon: Wifi,
      control: { kind: "status" }
    });
  }

  return features;
}
