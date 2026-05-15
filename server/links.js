import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runCommand } from "./command.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, "..");
const manifestPath = resolve(rootDir, "config/links.json");
const homeDir = process.env.HOME || process.env.USERPROFILE || "";
const proxyStack = process.env.PROXY_STACK_BIN || resolve(homeDir || ".", ".local", "bin", "proxy-stack");
const gatewayAgentScript = resolve(rootDir, "agent/gateway_agent.py");

export function loadLinks() {
  return JSON.parse(readFileSync(manifestPath, "utf8")).links;
}

function commandDetail(result) {
  return result.stdout || result.stderr || "unknown";
}

function parseJsonResult(result, fallback = null) {
  if (!result.stdout) {
    return fallback;
  }
  try {
    return JSON.parse(result.stdout);
  } catch {
    return fallback;
  }
}

function serviceMap(runtime) {
  return new Map((runtime.services || []).map((item) => [item.name, item]));
}

function portMap(runtime) {
  return new Map((runtime.ports || []).map((item) => [item.id, item]));
}

function serviceProbe(services, name) {
  const item = services.get(name);
  const systemdState = item?.systemd_state || item?.state || "unknown";
  const portFallback = Boolean(item?.port_fallback);
  const ports = Array.isArray(item?.ports) ? item.ports.join(",") : "";
  const mode = portFallback ? `systemd=${systemdState}; endpoint listening` : `systemd=${systemdState}`;
  return {
    ok: item?.state === "active",
    value: item?.state || "unknown",
    detail: item ? `${item.scope || "service"} ${item.enabled || ""}; ${mode}${ports ? `; ports=${ports}` : ""}`.trim() : "missing"
  };
}

function portProbe(ports, id) {
  const item = ports.get(id);
  return {
    ok: Boolean(item?.open),
    value: item?.open ? "open" : "closed",
    detail: item ? `${item.host}:${item.port}` : "missing"
  };
}

function boolProbe(ok, value, detail = "") {
  return { ok, value, detail };
}

function iphoneLanProxyFromRuntime(runtime) {
  const source = runtime.iphone_lan_proxy || {};
  const firewall = source.firewall || {};
  return {
    server: source.server || "",
    port: Number(source.port || 18181),
    setting: source.setting || "LAN-IP:18181",
    authentication: Boolean(source.authentication),
    target: source.target || "CN/private direct, foreign -> 127.0.0.1:18122",
    allowCidr: source.allow_cidr || "",
    portOpen: Boolean(source.port_open),
    firewall: {
      status: firewall.status || "unknown",
      summary: firewall.summary || "",
      evidence: firewall.evidence || null,
      allowCommand: firewall.allow_command || ""
    },
    recentClients: Array.isArray(source.recent_clients) ? source.recent_clients : [],
    recentUpstreams: Array.isArray(source.recent_upstreams) ? source.recent_upstreams : []
  };
}

function lanGatewayFromRuntime(runtime) {
  const source = runtime.lan_gateway || {};
  const manual = source.manual_iphone || {};
  const commands = source.commands || {};
  const nft = source.nft || {};
  return {
    ok: Boolean(source.ok),
    enabled: Boolean(source.enabled),
    mode: source.mode || "single-client-manual-router",
    server: source.server || "",
    interface: source.interface || "",
    gateway: source.gateway || "",
    cidr: source.cidr || "",
    clientIp: source.client_ip || "",
    inferredClientIp: source.inferred_client_ip || "",
    ipForward: Boolean(source.ip_forward),
    manualIphone: {
      ip: manual.ip || "",
      subnetMask: manual.subnet_mask || "",
      router: manual.router || "",
      dns: manual.dns || ""
    },
    nft: {
      state: nft.state || "unknown",
      detail: nft.detail || ""
    },
    errors: Array.isArray(source.errors) ? source.errors : [],
    commands: {
      rootApply: commands.root_apply || "sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip <iphone-ip>",
      rootRemove: commands.root_remove || "sudo ~/.local/bin/proxy-stack lan-gateway-root-remove",
      check: commands.check || "~/.local/bin/proxy-stack lan-gateway-plan"
    },
    notes: Array.isArray(source.notes) ? source.notes : []
  };
}

export function gatewayAgentV2Enabled() {
  return process.env.GATEWAY_AGENT_V2 === "1";
}

function gatewayAgentActionEnv() {
  return { ...process.env, GATEWAY_AGENT_V2: "1" };
}

export function linuxLifecycleFromStatus(source = {}) {
  return {
    ok: Boolean(source.ok ?? true),
    state: source.state || "unknown",
    summary: source.summary || "",
    contract: {
      stop: source.contract?.stop || "preserve-config",
      uninstall: source.contract?.uninstall || "purge-project-owned"
    },
    config: {
      path: source.config?.path || "",
      present: Boolean(source.config?.present),
      profilePresent: Boolean(source.config?.profilePresent)
    },
    runtime: {
      path: source.runtime?.path || "",
      present: Boolean(source.runtime?.present)
    },
    service: {
      path: source.service?.path || "",
      present: Boolean(source.service?.present)
    },
    wrapper: {
      path: source.wrapper?.path || "",
      present: Boolean(source.wrapper?.present)
    },
    commands: {
      stop: source.commands?.stop || "~/.local/bin/gateway-agent stop",
      uninstallDryRun: source.commands?.uninstallDryRun || "~/.local/bin/gateway-agent uninstall --dry-run",
      uninstallApply: source.commands?.uninstallApply || "~/.local/bin/gateway-agent uninstall --apply"
    }
  };
}

export function linuxLifecycleSelfCheck(source = {}) {
  const lifecycle = linuxLifecycleFromStatus(source);
  return {
    id: "linux-v3-lifecycle",
    status: lifecycle.ok ? "pass" : "warn",
    summary: lifecycle.summary || "Local control layer status unavailable",
    evidence: lifecycle
  };
}

export function gatewayAgentFromStatus(source, errors = []) {
  const session = source?.session || null;
  const usb = source?.usb || {};
  const privateRuntime = source?.privateRuntime || {};
  const unlock = source?.unlock || {};
  const phoneSetup = source?.phoneSetup || {};
  const state = source?.state || "unknown";
  const sourceProbes = source?.probes && typeof source.probes === "object" ? source.probes : {};
  return {
    v2: true,
    enabled: Boolean(source?.enabled),
    ok: Boolean(source?.ok),
    state,
    summary: source?.summary || "Desktop session status is unavailable",
    mode: "read-only",
    updatedAt: source?.generatedAt || "",
    probes: {
      ...sourceProbes,
      runtimeDir: boolProbe(Boolean(source?.runtimeDir), source?.runtimeDir || "missing", "local runtime path"),
      session: boolProbe(Boolean(session), session ? "present" : "missing", source?.sessionPath || ""),
      profileSource: boolProbe(Boolean(source?.profileSource?.present), source?.profileSource?.state || "missing", source?.profileSource?.mode || "local"),
      usb: boolProbe(Boolean(usb.present && usb.trusted), usb.state || "not_implemented", "optional recovery media"),
      unlock: boolProbe(unlock.state === "unlocked", unlock.state || "locked", unlock.bind || "127.0.0.1"),
      privateRuntime: boolProbe(Boolean(privateRuntime.state), privateRuntime.state || "unknown", privateRuntime.logs || ""),
      lanExposure: boolProbe(Boolean(phoneSetup.enabled), phoneSetup.state || "lan_listener_off", phoneSetup.summary || "")
    },
    errors
  };
}

export function gatewayControllerFromStatus(source = {}) {
  const unlock = source?.unlock || {};
  const profileSource = source?.profileSource || {};
  const session = source?.session || null;
  const listeners = session?.listeners || {};
  const lanProxy = listeners.lanProxy || null;
  return {
    version: 2,
    ok: Boolean(source?.ok),
    enabled: Boolean(source?.enabled),
    state: source?.state || "unknown",
    summary: source?.summary || "",
    updatedAt: source?.generatedAt || "",
    profile: {
      loaded: Boolean(unlock.profileLoaded),
      digest: unlock.profileDigest || "",
      summary: unlock.profileSummary || null,
      source: {
        mode: profileSource.mode || "local",
        state: profileSource.state || "missing",
        present: Boolean(profileSource.present)
      }
    },
    session: {
      present: Boolean(session),
      lanProxy: lanProxy ? { host: lanProxy.host || "", port: Number(lanProxy.port || 0) } : null
    },
    runtime: {
      state: source?.runtimeState?.state || "stopped",
      children: Array.isArray(source?.runtimeState?.children)
        ? source.runtimeState.children.map((child) => ({
            id: child.id || "",
            host: child.host || "",
            port: Number(child.port || 0)
          }))
        : []
    },
    phoneSetup: source?.phoneSetup || {
      enabled: false,
      state: "lan_listener_off",
      summary: "局域网入口未开启"
    },
    actions: {
      unlock: { method: "POST", href: "/api/gateway/v2/unlock", requiresLocalAuth: true },
      lock: { method: "POST", href: "/api/gateway/v2/lock", requiresLocalAuth: true },
      profileImport: { method: "POST", href: "/api/gateway/v2/profile/import", requiresLocalAuth: true },
      profileExport: { method: "GET", href: "/api/gateway/v2/profile/export", requiresLocalAuth: true }
    },
    privacy: {
      bindDefault: "127.0.0.1",
      secretsReturned: false,
      rawLogsReturned: false
    }
  };
}

export function gatewayPacFromStatus(source = {}) {
  const pac = source?.phoneSetup?.pac || {};
  if (!source?.phoneSetup?.enabled || !pac.available || typeof pac.content !== "string" || !pac.content) {
    return {
      ok: false,
      statusCode: 409,
      mimeType: "application/json; charset=utf-8",
      content: JSON.stringify({
        ok: false,
        state: "lan_listener_off",
        summary: "局域网 PAC 需先启用局域网入口。"
      }, null, 2),
    };
  }
  return {
    ok: true,
    statusCode: 200,
    mimeType: pac.mimeType || "application/x-ns-proxy-autoconfig",
    content: pac.content,
  };
}

export function gatewayControllerActionBlocked(action) {
  return {
    ok: false,
    action,
    state: "local_auth_required",
    summary: "Gateway controller action requires explicit local authentication and is not enabled in this slice."
  };
}

export async function getGatewayControllerStatus() {
  const result = await runCommand("python3", [gatewayAgentScript, "status"], { timeoutMs: 5000, maxOutput: 64_000 });
  const parsed = parseJsonResult(result, {
    ok: false,
    enabled: gatewayAgentV2Enabled(),
    state: "unknown",
    summary: commandDetail(result),
    generatedAt: new Date().toISOString()
  });
  return gatewayControllerFromStatus(parsed);
}

export async function getGatewayControllerPhoneSetup() {
  const status = await getGatewayControllerStatus();
  return {
    ok: status.ok,
    phoneSetup: status.phoneSetup,
    session: status.session,
    privacy: status.privacy
  };
}

export async function getGatewayControllerPac() {
  const result = await runCommand("python3", [gatewayAgentScript, "status"], { timeoutMs: 5000, maxOutput: 64_000 });
  const parsed = parseJsonResult(result, {
    ok: false,
    enabled: gatewayAgentV2Enabled(),
    state: "unknown",
    summary: commandDetail(result),
    generatedAt: new Date().toISOString()
  });
  return gatewayPacFromStatus(parsed);
}

export function getGatewayControllerDiagnostics() {
  return {
    ok: true,
    redacted: true,
    summary: "Diagnostics export is redacted; raw logs and secrets are not returned by the controller API.",
    checks: [
      { id: "secrets", status: "pass", summary: "controller API does not return profile secrets" },
      { id: "logs", status: "pass", summary: "controller API does not return raw logs" }
    ]
  };
}

export function networkEventsFromRuntime(runtime) {
  const source = runtime.network_events || {};
  const events = Array.isArray(source.events) ? source.events : [];
  const pending = Array.isArray(source.pending) ? source.pending : events.filter((item) => item.status === "pending");
  return {
    generatedAt: source.generated_at || "",
    events,
    pending,
    policy: source.policy || {}
  };
}

export function mapRuntimeStatus(runtime, links, context = {}) {
  const services = serviceMap(runtime);
  const ports = portMap(runtime);
  const oldHttp = portProbe(ports, "old-http");
  const oldSocks = portProbe(ports, "old-socks");
  const newHttp = portProbe(ports, "new-http");
  const newSocks = portProbe(ports, "new-socks");
  const failover = portProbe(ports, "failover");
  const iphoneLan = portProbe(ports, "iphone-lan");
  const splitDns = portProbe(ports, "split-dns");
  const splitTcp = portProbe(ports, "split-tcp");

  const oldProxy = serviceProbe(services, "privoxy.service");
  const oldServer = serviceProbe(services, "shadowsocks-libev.service");
  const canaryClient = serviceProbe(services, "secondary-proxy-client.service");
  const canaryBridge = serviceProbe(services, "secondary-http-proxy.service");
  const failoverService = serviceProbe(services, "proxy-failover.service");
  const iphoneLanService = serviceProbe(services, "iphone-lan-proxy.service");
  const splitProxy = serviceProbe(services, "hotspot-split-proxy.service");
  const splitDnsService = serviceProbe(services, "hotspot-split-dns.service");
  const nftLoaded = runtime.nft?.state === "loaded";
  const iphoneLanProxy = iphoneLanProxyFromRuntime(runtime);
  const lanGateway = lanGatewayFromRuntime(runtime);
  const iphoneLanFirewall = boolProbe(
    iphoneLanProxy.firewall.status === "effective_open",
    iphoneLanProxy.firewall.status,
    iphoneLanProxy.firewall.summary
  );

  const domesticDns = runtime.dns_decisions?.domestic || "unknown";
  const foreignDns = runtime.dns_decisions?.foreign || "unknown";
  const hotspotPreflight = context.hotspotPreflight || runtime.hotspot_preflight || null;

  const mainActive = oldHttp.ok && oldSocks.ok && oldProxy.ok && oldServer.ok;
  const phoneActive = newHttp.ok && newSocks.ok && canaryClient.ok && canaryBridge.ok;
  const failoverActive = failover.ok && failoverService.ok;
  const splitActive = splitDns.ok && splitTcp.ok && splitDnsService.ok && splitProxy.ok && nftLoaded;
  const lanGatewayActive = lanGateway.enabled && lanGateway.ok;

  const status = {
    generatedAt: new Date().toISOString(),
    runtimeGeneratedAt: runtime.generated_at || "",
    links,
    statuses: [
      {
        id: "main-download",
        active: mainActive,
        summary: mainActive ? "Old desktop route is available" : "Old desktop route needs attention",
        probes: { oldHttp, oldSocks, oldProxy, oldServer }
      },
      {
        id: "phone-canary",
        active: phoneActive,
        summary: phoneActive ? "New phone canary route is ready" : "New phone canary route needs attention",
        probes: { newHttp, newSocks, iphoneLan, iphoneLanFirewall, canaryClient, canaryBridge, iphoneLanService }
      },
      {
        id: "app-failover",
        active: failoverActive,
        summary: failoverActive ? "Failover route is ready" : "Failover route needs attention",
        probes: { failover, failoverService, oldHttp, newHttp }
      },
      {
        id: "hotspot-split",
        active: splitActive,
        summary: splitActive ? "Transparent hotspot split gateway is loaded" : "Hotspot split gateway needs attention",
        probes: {
          splitDns,
          splitTcp,
          splitDnsService,
          splitProxy,
          nftables: boolProbe(nftLoaded, runtime.nft?.state || "unknown", runtime.nft?.detail || ""),
          domesticDns: boolProbe(domesticDns !== "unknown", domesticDns),
          foreignDns: boolProbe(foreignDns !== "unknown", foreignDns),
          hotspotGuard: boolProbe(Boolean(hotspotPreflight?.allowed), hotspotPreflight?.risk || "unknown", hotspotPreflight?.message || "")
        }
      },
      {
        id: "lan-gateway",
        active: lanGatewayActive,
        summary: lanGateway.enabled
          ? lanGateway.ok ? "LAN gateway is enabled for one iPhone" : "LAN gateway is enabled but plan needs attention"
          : "LAN gateway is planned but disabled",
        probes: {
          client: boolProbe(Boolean(lanGateway.clientIp), lanGateway.clientIp || "missing", lanGateway.cidr),
          router: boolProbe(Boolean(lanGateway.server), lanGateway.server || "missing", lanGateway.interface),
          upstream: boolProbe(Boolean(lanGateway.gateway), lanGateway.gateway || "missing", "router"),
          ipForward: boolProbe(lanGateway.ipForward, lanGateway.ipForward ? "enabled" : "disabled"),
          nftables: boolProbe(lanGateway.nft.state === "loaded", lanGateway.nft.state, lanGateway.nft.detail)
        }
      }
    ],
    environment: {
      httpProxy: process.env.HTTP_PROXY || process.env.http_proxy || "",
      httpsProxy: process.env.HTTPS_PROXY || process.env.https_proxy || "",
      allProxy: process.env.ALL_PROXY || process.env.all_proxy || "",
      defaultRoute: context.defaultRoute || ""
    },
    hotspotPreflight,
    iphoneLanProxy,
    lanGateway,
    linuxLifecycle: linuxLifecycleFromStatus(context.linuxLifecycle || runtime.linux_lifecycle || runtime.linuxLifecycle || {}),
    networkEvents: networkEventsFromRuntime(runtime),
    runtime
  };
  if (gatewayAgentV2Enabled()) {
    status.gatewayAgent = gatewayAgentFromStatus(context.gatewayAgent || runtime.gateway_agent_v2 || runtime.gatewayAgent || null);
  }
  return status;
}

export async function buildStatus() {
  const pending = [
    runCommand(proxyStack, ["json"], { timeoutMs: 20_000, maxOutput: 256_000 }),
    runCommand("ip", ["route", "get", "8.8.8.8"], { timeoutMs: 3000 }),
    runCommand(proxyStack, ["hotspot-preflight"], { timeoutMs: 8000 }),
    runCommand("python3", [gatewayAgentScript, "lifecycle-status"], { timeoutMs: 5000, maxOutput: 64_000 })
  ];
  if (gatewayAgentV2Enabled()) {
    pending.push(runCommand("python3", [gatewayAgentScript, "status"], { timeoutMs: 5000, maxOutput: 64_000 }));
  }
  const [runtimeResult, defaultRouteResult, preflightResult, lifecycleResult, gatewayAgentResult] = await Promise.all(pending);

  if (!runtimeResult.ok) {
    throw new Error(commandDetail(runtimeResult));
  }

  const runtime = parseJsonResult(runtimeResult);
  if (!runtime) {
    throw new Error("proxy-stack returned invalid JSON");
  }

  const gatewayAgent = gatewayAgentResult
    ? parseJsonResult(gatewayAgentResult, {
        ok: false,
        enabled: true,
        state: "unknown",
        summary: commandDetail(gatewayAgentResult),
        generatedAt: new Date().toISOString()
      })
    : null;

  return mapRuntimeStatus(runtime, loadLinks(), {
    defaultRoute: defaultRouteResult.stdout || defaultRouteResult.stderr,
    hotspotPreflight: parseJsonResult(preflightResult, {
      allowed: false,
      risk: "unknown",
      message: commandDetail(preflightResult)
    }),
    linuxLifecycle: parseJsonResult(lifecycleResult, {
      ok: false,
      state: "unknown",
      summary: commandDetail(lifecycleResult)
    }),
    gatewayAgent
  });
}

function metricFromCommand(linkId, label, result) {
  return {
    linkId,
    label,
    ok: Boolean(result?.ok),
    value: result?.ok ? "ok" : "failed",
    detail: result ? commandDetail(result) : "missing"
  };
}

export async function runBenchmark() {
  const result = await runCommand(proxyStack, ["test"], { timeoutMs: 70_000 });
  const parsed = parseJsonResult(result);
  if (!parsed) {
    return {
      generatedAt: new Date().toISOString(),
      metrics: [metricFromCommand("app-failover", "proxy-stack test", result)]
    };
  }
  return {
    generatedAt: new Date().toISOString(),
    metrics: [
      metricFromCommand("hotspot-split", "baidu split dns", parsed.dns_baidu),
      metricFromCommand("hotspot-split", "google split dns", parsed.dns_google),
      metricFromCommand("app-failover", "failover route", parsed.failover),
      metricFromCommand("main-download", "old proxy route", parsed.old_proxy)
    ]
  };
}

export async function getSelfCheck() {
  const result = await runCommand(proxyStack, ["self-check"], { timeoutMs: 30_000, maxOutput: 256_000 });
  const lifecycleResult = await runCommand("python3", [gatewayAgentScript, "lifecycle-status"], { timeoutMs: 5000, maxOutput: 64_000 });
  const parsed = parseJsonResult(result);
  if (!parsed) {
    return {
      generated_at: new Date().toISOString(),
      mode: "quick",
      overall: "fail",
      ok: false,
      checks: [
        {
          id: "self-check-command",
          status: "fail",
          summary: "proxy-stack self-check did not return JSON",
          detail: commandDetail(result)
        }
      ]
    };
  }
  const payload = { ...parsed, ok: result.ok && Boolean(parsed.ok) };
  payload.linux_lifecycle = parseJsonResult(lifecycleResult, {
    ok: false,
    state: "unknown",
    summary: commandDetail(lifecycleResult)
  });
  payload.checks = Array.isArray(payload.checks) ? [...payload.checks, linuxLifecycleSelfCheck(payload.linux_lifecycle)] : [
    linuxLifecycleSelfCheck(payload.linux_lifecycle)
  ];
  if (!payload.linux_lifecycle.ok && payload.overall !== "fail") {
    payload.overall = "warn";
  }
  if (gatewayAgentV2Enabled()) {
    const gatewayAgentResult = await runCommand("python3", [gatewayAgentScript, "self-check"], { timeoutMs: 5000, maxOutput: 64_000 });
    payload.gateway_agent_v2 = parseJsonResult(gatewayAgentResult, {
      ok: false,
      overall: "fail",
      summary: commandDetail(gatewayAgentResult)
    });
    payload.ok = payload.ok && Boolean(payload.gateway_agent_v2.ok);
    if (payload.overall !== "fail" && payload.gateway_agent_v2.overall === "fail") {
      payload.overall = "fail";
    }
  }
  return payload;
}

export const actions = [
  {
    id: "self-check",
    label: "Unified self-check",
    description: "Run the quick route, guard, port, event, and dashboard health check.",
    risk: "safe"
  },
  {
    id: "hotspot-preflight",
    label: "Hotspot preflight",
    description: "Check whether GY-Hotspot would disconnect the current upstream Wi-Fi.",
    risk: "safe"
  },
  {
    id: "hotspot-start-safe",
    label: "Safe hotspot start",
    description: "Start GY-Hotspot only if preflight sees another upstream interface.",
    risk: "caution"
  },
  {
    id: "test",
    label: "Run stack tests",
    description: "Run DNS split, failover, and old route checks through proxy-stack.",
    risk: "safe"
  },
  {
    id: "lan-gateway-plan",
    label: "LAN gateway plan",
    description: "Inspect the single-iPhone manual-router gateway plan.",
    risk: "safe"
  },
  {
    id: "lan-gateway-root-apply",
    label: "Show LAN gateway apply",
    description: "Display the root command that enables single-iPhone LAN gateway mode.",
    risk: "caution"
  },
  {
    id: "lan-gateway-root-remove",
    label: "Show LAN gateway rollback",
    description: "Display the root command that removes LAN gateway nftables rules.",
    risk: "caution"
  },
  {
    id: "restart-user",
    label: "Restart user services",
    description: "Restart canary, failover, split proxy, and split DNS user services.",
    risk: "caution"
  },
  {
    id: "update-cn",
    label: "Update CN routes",
    description: "Refresh the local China IPv4 route list through the existing proxy.",
    risk: "safe"
  },
  {
    id: "gateway-agent-start",
    label: "Start desktop session",
    description: "Create a local desktop session without touching root network rules.",
    risk: "safe"
  },
  {
    id: "linux-v3-stop",
    label: "Stop local control layer",
    description: "Stop desktop session/runtime state while preserving imported configuration.",
    risk: "safe"
  },
  {
    id: "linux-v3-uninstall-plan",
    label: "Show local uninstall",
    description: "Show the terminal-gated command that removes project-owned control files.",
    risk: "caution"
  },
  {
    id: "root-apply",
    label: "Show root apply",
    description: "Display the terminal command for nftables transparent gateway takeover.",
    risk: "caution"
  },
  {
    id: "root-remove",
    label: "Show root remove",
    description: "Display the terminal command for nftables rollback.",
    risk: "caution"
  }
];

export async function runAction(actionId) {
  if (actionId === "root-apply") {
    return {
      actionId,
      ok: false,
      requiresTerminal: true,
      command: "sudo ~/.local/bin/hotspot-split-gateway root-apply",
      stdout: "",
      stderr: "Root nftables changes stay terminal-gated."
    };
  }
  if (actionId === "root-remove") {
    return {
      actionId,
      ok: false,
      requiresTerminal: true,
      command: "sudo ~/.local/bin/hotspot-split-gateway root-remove",
      stdout: "",
      stderr: "Root nftables changes stay terminal-gated."
    };
  }
  if (actionId === "lan-gateway-root-apply") {
    const planResult = await runCommand(proxyStack, ["lan-gateway-plan"], { timeoutMs: 8000, maxOutput: 64_000 });
    const parsed = parseJsonResult(planResult, {});
    return {
      actionId,
      ok: false,
      requiresTerminal: true,
      command: parsed?.commands?.root_apply || "sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip <iphone-ip>",
      stdout: planResult.stdout,
      stderr: "Root nftables changes stay terminal-gated."
    };
  }
  if (actionId === "lan-gateway-root-remove") {
    return {
      actionId,
      ok: false,
      requiresTerminal: true,
      command: "sudo ~/.local/bin/proxy-stack lan-gateway-root-remove",
      stdout: "",
      stderr: "Root nftables rollback stays terminal-gated."
    };
  }
  if (actionId === "linux-v3-uninstall-plan") {
    const planResult = await runCommand("python3", [gatewayAgentScript, "uninstall", "--dry-run"], { timeoutMs: 8000, maxOutput: 64_000 });
    const parsed = parseJsonResult(planResult, {});
    return {
      actionId,
      ok: false,
      requiresTerminal: true,
      command: parsed?.commands?.uninstallApply || "~/.local/bin/gateway-agent uninstall --apply",
      stdout: planResult.stdout,
      stderr: "Local control layer uninstall is terminal-gated because it deletes project-owned config and runtime files."
    };
  }

  const table = {
    "self-check": [proxyStack, ["self-check"], 30_000, 256_000],
    "hotspot-preflight": [proxyStack, ["hotspot-preflight"], 8000],
    "hotspot-start-safe": [proxyStack, ["hotspot-start-safe"], 40_000],
    "test": [proxyStack, ["test"], 70_000],
    "lan-gateway-plan": [proxyStack, ["lan-gateway-plan"], 8000, 64_000],
    "restart-user": [proxyStack, ["restart-user"], 30_000],
    "update-cn": [proxyStack, ["update-cn"], 100_000],
    "gateway-agent-start": ["python3", [gatewayAgentScript, "start", "--lan-host", "127.0.0.1"], 15_000, 64_000, gatewayAgentActionEnv()],
    "linux-v3-stop": ["python3", [gatewayAgentScript, "stop"], 15_000, 64_000, gatewayAgentActionEnv()]
  };
  const command = table[actionId];
  if (!command) {
    return { actionId, ok: false, stdout: "", stderr: "Unknown action" };
  }
  const result = await runCommand(command[0], command[1], { timeoutMs: command[2], maxOutput: command[3], env: command[4] });
  return {
    actionId,
    ok: actionId === "hotspot-preflight" ? Boolean(result.stdout) : result.ok,
    stdout: result.stdout,
    stderr: result.stderr,
    result
  };
}

export async function getNetworkEvents() {
  const result = await runCommand(proxyStack, ["network-events"], { timeoutMs: 8000, maxOutput: 256_000 });
  const parsed = parseJsonResult(result);
  if (!parsed) {
    return {
      ok: false,
      generatedAt: new Date().toISOString(),
      events: [],
      pending: [],
      stderr: commandDetail(result)
    };
  }
  return { ok: result.ok, ...networkEventsFromRuntime({ network_events: parsed }) };
}

export async function resolveNetworkEvent(eventId, decision) {
  const result = await runCommand(proxyStack, ["upstream-select", eventId, decision], { timeoutMs: 15_000 });
  const parsed = parseJsonResult(result);
  return {
    ok: result.ok && Boolean(parsed?.ok),
    stdout: result.stdout,
    stderr: result.stderr,
    result: parsed || result
  };
}
