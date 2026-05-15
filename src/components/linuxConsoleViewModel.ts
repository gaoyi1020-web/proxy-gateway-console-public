import type { LinuxProxyUnificationStatus, StatusResponse } from "../lib/types";

export type LinuxConsoleState = "ok" | "warn" | "off";
export type LinuxConsoleCardId = "service" | "phone" | "config" | "guard";
export type LinuxConsoleIconId = "shield-check" | "shield-alert" | "smartphone" | "file-lock";

export interface LinuxConsoleCard {
  id: LinuxConsoleCardId;
  label: string;
  state: LinuxConsoleState;
  stateLabel: string;
  value: string;
  summary: string;
  icon: LinuxConsoleIconId;
}

export interface LinuxConsoleViewModel {
  cards: LinuxConsoleCard[];
  sessionActive: boolean;
  sessionActionId: "linux-v3-stop" | "gateway-agent-start";
}

function endpointText(endpoint?: { host: string; port: number; open: boolean }) {
  if (!endpoint) {
    return "等待状态";
  }
  return endpoint.port ? `${endpoint.host}:${endpoint.port}` : endpoint.host;
}

function stateValue(state: LinuxConsoleState) {
  if (state === "ok") {
    return "正常";
  }
  if (state === "warn") {
    return "关注";
  }
  return "等待";
}

function stateLabel(state: LinuxConsoleState) {
  if (state === "ok") {
    return "在线";
  }
  if (state === "warn") {
    return "关注";
  }
  return "等待";
}

function gatewaySessionActive(status: StatusResponse | null) {
  const agent = status?.gatewayAgent;
  return Boolean(agent?.probes.session?.ok) || agent?.state === "manifest_ready";
}

function guardSummary(guard: StatusResponse["hotspotPreflight"] | undefined) {
  if (!guard) {
    return "热点和上游切换保护";
  }
  if (guard.allowed) {
    return "当前上游满足安全启动条件";
  }
  return "热点保护已启用；详情见状态页";
}

export function buildLinuxConsoleViewModel(
  status: StatusResponse | null,
  proxyUnification: LinuxProxyUnificationStatus | null
): LinuxConsoleViewModel {
  const sessionActive = gatewaySessionActive(status);
  const phone = status?.iphoneLanProxy;
  const currentHttp = proxyUnification?.unifiedEntry.currentHttp;
  const serviceState: LinuxConsoleState = currentHttp?.open || phone?.portOpen ? "ok" : status ? "warn" : "off";
  const phoneState: LinuxConsoleState = phone?.portOpen ? "ok" : status ? "warn" : "off";
  const profilePresent = status?.linuxLifecycle?.config.profilePresent;
  const configState: LinuxConsoleState = profilePresent ? "ok" : status?.linuxLifecycle?.config.present ? "warn" : "off";
  const guard = status?.hotspotPreflight;
  const guardState: LinuxConsoleState = guard ? (guard.allowed ? "ok" : "warn") : "off";

  return {
    sessionActive,
    sessionActionId: sessionActive ? "linux-v3-stop" : "gateway-agent-start",
    cards: [
      {
        id: "service",
        label: "服务状态",
        state: serviceState,
        stateLabel: stateLabel(serviceState),
        value: stateValue(serviceState),
        summary: currentHttp?.open ? `本机入口 ${endpointText(currentHttp)}` : phone?.portOpen ? "手机代理入口可用" : "等待服务状态",
        icon: serviceState === "ok" ? "shield-check" : "shield-alert"
      },
      {
        id: "phone",
        label: "手机入口",
        state: phoneState,
        stateLabel: stateLabel(phoneState),
        value: phone?.setting || "未就绪",
        summary: phone?.portOpen ? phone.firewall.summary || "局域网可访问" : "手机入口未就绪，请使用当前配置确认入口",
        icon: "smartphone"
      },
      {
        id: "config",
        label: "配置状态",
        state: configState,
        stateLabel: stateLabel(configState),
        value: profilePresent ? "已导入" : "未导入",
        summary: profilePresent ? "加密配置已存在" : "到配置页导入加密配置",
        icon: "file-lock"
      },
      {
        id: "guard",
        label: "保护状态",
        state: guardState,
        stateLabel: stateLabel(guardState),
        value: guard ? guard.risk : "等待检测",
        summary: guardSummary(guard),
        icon: guardState === "ok" ? "shield-check" : "shield-alert"
      }
    ]
  };
}
