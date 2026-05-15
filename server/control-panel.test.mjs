import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { join } from "node:path";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { build } from "esbuild";

const require = createRequire(import.meta.url);

async function loadComponent(entryPoint, exportName = "default") {
  const tempDir = await mkdtemp(join(process.cwd(), "node_modules", ".component-test-"));
  const outfile = join(tempDir, `${entryPoint.split("/").pop().replace(/\.[^.]+$/, "")}.cjs`);
  await build({
    entryPoints: [entryPoint],
    outfile,
    bundle: true,
    platform: "node",
    format: "cjs",
    target: "node20",
    external: ["react", "react-dom", "react-dom/server"],
    logLevel: "silent"
  });
  const module = require(outfile);
  return {
    Component: module[exportName],
    cleanup: () => rm(tempDir, { recursive: true, force: true })
  };
}

const baseStatus = {
  generatedAt: "2026-05-09T12:00:00Z",
  links: [],
  statuses: [],
  environment: {
    httpProxy: "",
    httpsProxy: "",
    allProxy: "",
    defaultRoute: "default via 10.10.0.1 dev wlp0s20f3 src 10.10.0.10"
  },
  networkEvents: {
    events: [],
    pending: []
  }
};

const fullStatus = {
  ...baseStatus,
  iphoneLanProxy: {
    server: "10.10.0.10",
    port: 18181,
    setting: "10.10.0.10:18181",
    authentication: false,
    target: "CN/private direct, foreign -> 127.0.0.1:18122",
    allowCidr: "10.10.0.0/24",
    portOpen: true,
    firewall: { status: "effective_open", summary: "recent LAN client reached the bridge" },
    recentClients: [{ timestamp: "2026-05-09T12:00:00Z", ip: "10.10.0.20", port: 18181, local: true }],
    recentUpstreams: []
  },
  hotspotPreflight: {
    connection: "GY-Hotspot",
    allowed: true,
    risk: "safe",
    message: "safe",
    hotspot_interface: "wlp0s20f3",
    hotspot_mode: "wifi",
    default_route: "default via 10.10.0.1 dev wlp0s20f3",
    default_route_interface: "wlp0s20f3",
    recommendation: "ok"
  },
  linuxLifecycle: {
    ok: true,
    state: "installed",
    summary: "Linux v3 control layer is installed",
    contract: { stop: "preserve-config", uninstall: "purge-project-owned" },
    config: { path: "~/.config/proxy-gateway", present: true, profilePresent: true },
    runtime: { path: "/run/user/1000/proxy-gateway", present: true },
    service: { path: "~/.config/systemd/user/gateway-agent.service", present: true },
    wrapper: { path: "~/.local/bin/gateway-agent", present: true },
    commands: {
      stop: "~/.local/bin/gateway-agent stop",
      uninstallDryRun: "~/.local/bin/gateway-agent uninstall --dry-run",
      uninstallApply: "~/.local/bin/gateway-agent uninstall --apply"
    }
  },
  gatewayAgent: {
    v2: true,
    enabled: true,
    ok: true,
    state: "manifest_ready",
    summary: "Gateway agent v2 status is ready",
    mode: "read-only",
    updatedAt: "2026-05-09T12:00:00Z",
    probes: {
      profileSource: { ok: true, value: "encrypted_profile_present", detail: "local" },
      unlock: { ok: true, value: "unlocked", detail: "active" },
      session: { ok: true, value: "ready", detail: "session manifest exists" },
      lanExposure: { ok: false, value: "closed", detail: "LAN listener disabled" }
    },
    errors: ["profile auth token should be redacted"]
  }
};

const packageStatus = {
  ok: true,
  state: "installed",
  launcherMode: "release",
  summary: "Linux desktop self-use package is installed",
  installRoot: "~/.local/share/proxy-gateway-desktop/self-use",
  launcher: "~/.local/bin/proxy-gateway-desktop",
  releaseBinary: "~/.local/share/proxy-gateway-desktop/self-use/bin/proxy-gateway-test",
  sidecar: "~/.local/share/proxy-gateway-desktop/self-use/bin/gateway-agent",
  desktopEntry: "~/.local/share/applications/proxy-gateway-desktop.desktop",
  checks: {}
};

const proxyUnification = {
  ok: true,
  mode: "read-only",
  generatedAt: "2026-05-09T12:00:00Z",
  versionCount: 2,
  unifiedEntry: {
    currentHttp: { host: "127.0.0.1", port: 18180, open: true },
    futureSocks: { host: "127.0.0.1", port: 18182, open: false, planned: true }
  },
  upstreams: [
    {
      id: "old",
      label: "旧代理",
      role: "legacy-compatible-upstream",
      http: { host: "127.0.0.1", port: 8118, open: true },
      socks: { host: "127.0.0.1", port: 1080, open: true },
      services: ["shadowsocks-libev.service", "privoxy.service"],
      ready: true
    },
    {
      id: "new",
      label: "新代理",
      role: "canary-preferred-upstream",
      http: { host: "127.0.0.1", port: 18122, open: true },
      socks: { host: "127.0.0.1", port: 11880, open: true },
      services: ["secondary-proxy-client.service"],
      ready: true
    }
  ],
  adapters: [
    { id: "local-failover", label: "本机统一 HTTP", endpoint: { host: "127.0.0.1", port: 18180, open: true }, target: "old/new upstream pool", owner: "proxy-gateway", ready: true },
    { id: "iphone-lan", label: "手机 LAN", endpoint: { host: "LAN", port: 18181, open: true }, target: "foreign -> new", owner: "proxy-gateway", ready: true }
  ],
  policy: {
    private: "direct",
    domestic: "direct",
    foreign: "proxy",
    preferredForeignUpstream: "new",
    fallbackOrder: ["new", "old"]
  },
  externalServices: [
    { name: "autossh-tunnel.service", port: 1080, status: "retrying", projectOwned: false, classification: "external-socks-tunnel", risk: "port overlap with old SOCKS; keep isolated before cutover" }
  ],
  optimizationReadiness: {
    phase: "observe-only",
    dispatcherActive: false,
    blockers: ["read-only-unification", "profile-missing-or-unverified"],
    safeNextSteps: ["add deterministic network smoke"]
  },
  risks: ["read-only model only"],
  recommendedCutoverOrder: ["observe-only", "local app unified HTTP"],
  actions: []
};

const gatewayApi = {
  status: async () => fullStatus,
  actions: async () => [
    { id: "self-check", label: "自检", description: "刷新状态", risk: "safe" },
    { id: "gateway-agent-start", label: "启动桌面会话", description: "启动会话", risk: "safe" },
    { id: "linux-v3-stop", label: "停止本机控制层", description: "停止", risk: "safe" },
    { id: "restart-user", label: "重启代理服务", description: "重启", risk: "caution" }
  ],
  runAction: async (actionId) => ({ ok: true, actionId, stdout: "", stderr: "" }),
  networkEvents: async () => ({ events: [], pending: [] }),
  resolveNetworkEvent: async () => ({ ok: true }),
  linuxDesktopPackage: async () => packageStatus,
  linuxProxyUnification: async () => proxyUnification,
  importLinuxProfile: async () => ({ ok: true, state: "imported", summary: "imported" })
};

test("WebWorkbenchLayout renders four stable navigation entries", async () => {
  const { Component: WebWorkbenchLayout, cleanup } = await loadComponent("src/components/WebWorkbenchLayout.tsx");
  try {
    const markup = renderToStaticMarkup(
      React.createElement(WebWorkbenchLayout, {
        activeView: "operations",
        onViewChange: () => {},
        status: fullStatus,
        networkEvents: { events: [], pending: [] },
        loading: false,
        onRefresh: () => {},
        children: React.createElement("section", null, "body")
      })
    );

    assert.match(markup, /操作/);
    assert.match(markup, /配置/);
    assert.match(markup, /状态/);
    assert.match(markup, /日志/);
    assert.match(markup, /10\.10\.0\.10:18181/);
    assert.match(markup, /待处理事件：0/);
  } finally {
    await cleanup();
  }
});

test("OperationsPage exposes daily controls without full topology", async () => {
  const { Component: OperationsPage, cleanup } = await loadComponent("src/components/OperationsPage.tsx");
  try {
    const markup = renderToStaticMarkup(
      React.createElement(OperationsPage, {
        status: fullStatus,
        packageStatus,
        proxyUnification,
        gatewayApi,
        loading: false,
        onActionComplete: () => {},
        onActionEvent: () => {},
        onOpenConfig: () => {}
      })
    );

    assert.match(markup, /服务状态/);
    assert.match(markup, /手机入口/);
    assert.match(markup, /配置状态/);
    assert.match(markup, /保护状态/);
    assert.match(markup, /自检/);
    assert.match(markup, /打开配置/);
    assert.doesNotMatch(markup, /重启代理服务/);
    assert.doesNotMatch(markup, /生成卸载命令/);
    assert.doesNotMatch(markup, /热点预检|安全启动热点|更新 CN 分流/);
    assert.doesNotMatch(markup, /代理详情/);
    assert.doesNotMatch(markup, /维护动作/);
  } finally {
    await cleanup();
  }
});

test("StatusPage is read-only and contains diagnostics", async () => {
  const { Component: StatusPage, cleanup } = await loadComponent("src/components/StatusPage.tsx");
  try {
    const markup = renderToStaticMarkup(
      React.createElement(StatusPage, {
        status: fullStatus,
        packageStatus,
        proxyUnification
      })
    );

    assert.match(markup, /运行状态/);
    assert.match(markup, /功能状态/);
    assert.match(markup, /当前默认路由/);
    assert.match(markup, /代理状态/);
    assert.doesNotMatch(markup, /<button[^>]*>自检/);
    assert.doesNotMatch(markup, /<button[^>]*>重启代理服务/);
    assert.doesNotMatch(markup, /执行动作/);
    assert.doesNotMatch(markup, /维护动作/);
  } finally {
    await cleanup();
  }
});

test("LogsPage renders session history and network events without secrets", async () => {
  const { Component: LogsPage, cleanup } = await loadComponent("src/components/LogsPage.tsx");
  try {
    const markup = renderToStaticMarkup(
      React.createElement(LogsPage, {
        status: fullStatus,
        networkEvents: {
          events: [{ id: "usb-1", type: "usb-network", status: "pending", interface: "enx1", connection: "iPhone", driver: "ipheth", message: "iPhone USB network detected", created_at: "2026-05-09T12:00:00Z" }],
          pending: [{ id: "usb-1", type: "usb-network", status: "pending", interface: "enx1", connection: "iPhone", driver: "ipheth", message: "iPhone USB network detected", created_at: "2026-05-09T12:00:00Z" }]
        },
        actionLog: [{ id: "a1", at: "2026-05-09T12:00:00Z", actionId: "self-check", label: "自检", ok: true, message: "完成" }],
        apiErrorLog: [{ id: "e1", at: "2026-05-09T12:01:00Z", scope: "status", message: "Connection refused token=abc123" }]
      })
    );

    assert.match(markup, /最新动作/);
    assert.match(markup, /API 错误/);
    assert.match(markup, /网络事件/);
    assert.match(markup, /iPhone USB network detected/);
    assert.match(markup, /token=\[redacted\]/);
    assert.doesNotMatch(markup, /abc123|profile\.json\.enc|password=/i);
  } finally {
    await cleanup();
  }
});

test("LinuxConfigPage keeps encrypted import separate from non-sensitive editing", async () => {
  const { Component: LinuxConfigPage, cleanup } = await loadComponent("src/components/LinuxConfigPage.tsx");
  try {
    const markup = renderToStaticMarkup(
      React.createElement(LinuxConfigPage, {
        status: fullStatus,
        packageStatus,
        gatewayApi,
        onImported: () => {}
      })
    );

    assert.match(markup, /导入加密配置/);
    assert.match(markup, /导入 profile\.json\.enc/);
    assert.match(markup, /配置编辑/);
    assert.match(markup, /非敏感 JSON/);
    assert.doesNotMatch(markup, /auth|password|token/i);
  } finally {
    await cleanup();
  }
});
