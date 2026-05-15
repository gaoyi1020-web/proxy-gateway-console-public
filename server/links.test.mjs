import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  actions,
  gatewayControllerActionBlocked,
  gatewayControllerFromStatus,
  gatewayPacFromStatus,
  linuxLifecycleSelfCheck,
  mapRuntimeStatus,
  runAction
} from "./links.js";
import { linuxDesktopPackageStatus } from "./linux-desktop-status.js";
import { validateLinuxProfileUpload } from "./linux-profile-import.js";
import { buildLinuxProxyUnification } from "./linux-proxy-unification.js";

const links = [
  { id: "main-download", name: "Main", role: "", mode: "", route: "", ports: [], services: [], risk: "", benchmark: {} },
  { id: "phone-canary", name: "Phone", role: "", mode: "", route: "", ports: [], services: [], risk: "", benchmark: {} },
  { id: "app-failover", name: "Failover", role: "", mode: "", route: "", ports: [], services: [], risk: "", benchmark: {} },
  { id: "hotspot-split", name: "Split", role: "", mode: "", route: "", ports: [], services: [], risk: "", benchmark: {} },
  { id: "lan-gateway", name: "LAN Gateway", role: "", mode: "", route: "", ports: [], services: [], risk: "", benchmark: {} }
];

const runtime = {
  generated_at: "2026-05-03 17:20:00 +0800",
  services: [
    { name: "shadowsocks-libev.service", state: "active" },
    { name: "privoxy.service", state: "active" },
    { name: "secondary-proxy-client.service", state: "active" },
    { name: "secondary-http-proxy.service", state: "active" },
    { name: "proxy-failover.service", state: "active" },
    { name: "iphone-lan-proxy.service", state: "active" },
    { name: "hotspot-split-proxy.service", state: "active" },
    { name: "hotspot-split-dns.service", state: "active" }
  ],
  ports: [
    { id: "old-socks", open: true },
    { id: "old-http", open: true },
    { id: "new-socks", open: true },
    { id: "new-http", open: true },
    { id: "failover", open: true },
    { id: "iphone-lan", open: true, host: "LAN", port: 18181 },
    { id: "split-dns", open: true },
    { id: "split-tcp", open: true }
  ],
  iphone_lan_proxy: {
    server: "10.10.0.10",
    port: 18181,
    setting: "10.10.0.10:18181",
    authentication: false,
    target: "CN/private direct, foreign -> 127.0.0.1:18122",
    firewall: { status: "effective_open", summary: "recent LAN client reached the bridge" },
    recent_clients: [{ timestamp: "2026-05-03 19:32:02,747", ip: "10.10.0.20", port: 62791, local: false }],
    recent_upstreams: [{ timestamp: "2026-05-03 19:34:04,606", target: "captive.apple.com:443", route: "new" }]
  },
  lan_gateway: {
    ok: true,
    enabled: false,
    server: "10.10.0.10",
    interface: "wlp0s20f3",
    gateway: "10.10.0.1",
    cidr: "10.10.0.0/24",
    client_ip: "10.10.0.20",
    ip_forward: true,
    manual_iphone: {
      ip: "10.10.0.20",
      subnet_mask: "255.255.255.0",
      router: "10.10.0.10",
      dns: "10.10.0.10"
    },
    nft: { state: "disabled", detail: "No such file or directory" },
    commands: {
      root_apply: "sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip 10.10.0.20",
      root_remove: "sudo ~/.local/bin/proxy-stack lan-gateway-root-remove"
    }
  },
  nft: { state: "loaded" },
  dns_decisions: { domestic: "direct DNS www.baidu.com", foreign: "remote DNS retry www.google.com" },
  network_events: {
    events: [
      {
        id: "evt-phone",
        type: "phone_tether_detected",
        status: "pending",
        interface: "enxiphone",
        connection: "iPhone USB",
        driver: "ipheth"
      },
      {
        id: "evt-old",
        type: "phone_tether_detected",
        status: "resolved",
        interface: "usb0",
        connection: "Android USB",
        driver: "rndis_host"
      }
    ],
    pending: [
      {
        id: "evt-phone",
        type: "phone_tether_detected",
        status: "pending",
        interface: "enxiphone",
        connection: "iPhone USB",
        driver: "ipheth"
      }
    ]
  }
};

test("maps proxy-stack runtime status to console link statuses", () => {
  const status = mapRuntimeStatus(runtime, links, {
    defaultRoute: "8.8.8.8 via 10.10.0.1 dev wlp0s20f3",
    hotspotPreflight: {
      allowed: false,
      risk: "would_disconnect_upstream",
      message: "Starting GY-Hotspot would disconnect upstream Wi-Fi"
    }
  });

  assert.equal(status.statuses.length, 5);
  assert.equal(status.statuses.find((item) => item.id === "main-download").active, true);
  assert.equal(status.statuses.find((item) => item.id === "phone-canary").active, true);
  assert.equal(status.statuses.find((item) => item.id === "app-failover").active, true);
  assert.equal(status.statuses.find((item) => item.id === "hotspot-split").active, true);
  assert.equal(status.statuses.find((item) => item.id === "lan-gateway").active, false);
  assert.equal(status.hotspotPreflight.allowed, false);
  assert.equal(status.environment.defaultRoute, "8.8.8.8 via 10.10.0.1 dev wlp0s20f3");
});

test("maps iPhone LAN proxy readiness for phone setup UI", () => {
  const status = mapRuntimeStatus(runtime, links);

  assert.equal(status.iphoneLanProxy.setting, "10.10.0.10:18181");
  assert.equal(status.iphoneLanProxy.target, "CN/private direct, foreign -> 127.0.0.1:18122");
  assert.equal(status.iphoneLanProxy.firewall.status, "effective_open");
  assert.equal(status.iphoneLanProxy.recentClients[0].ip, "10.10.0.20");
  assert.equal(status.iphoneLanProxy.recentUpstreams[0].target, "captive.apple.com:443");
  assert.equal(status.statuses.find((item) => item.id === "phone-canary").probes.iphoneLanFirewall.ok, true);
});

test("maps LAN gateway plan for dashboard and terminal-gated actions", () => {
  const status = mapRuntimeStatus(runtime, links);
  const lanStatus = status.statuses.find((item) => item.id === "lan-gateway");

  assert.equal(status.lanGateway.clientIp, "10.10.0.20");
  assert.equal(status.lanGateway.manualIphone.router, "10.10.0.10");
  assert.equal(status.lanGateway.commands.rootApply, "sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip 10.10.0.20");
  assert.equal(lanStatus.active, false);
  assert.equal(lanStatus.probes.client.value, "10.10.0.20");
  assert.equal(lanStatus.probes.ipForward.ok, true);
});

test("maps pending network events for the upstream selector", () => {
  const status = mapRuntimeStatus(runtime, links);

  assert.equal(status.networkEvents.pending.length, 1);
  assert.equal(status.networkEvents.pending[0].id, "evt-phone");
  assert.equal(status.networkEvents.pending[0].connection, "iPhone USB");
});

test("maps Linux v3 lifecycle status for the compact control layer", () => {
  const status = mapRuntimeStatus(runtime, links, {
    linuxLifecycle: {
      ok: true,
      state: "installed",
      summary: "Linux v3 control layer is installed",
      contract: {
        stop: "preserve-config",
        uninstall: "purge-project-owned"
      },
      config: {
        path: "~/.config/proxy-gateway",
        present: true,
        profilePresent: true
      },
      runtime: {
        path: "/run/user/1000/proxy-gateway",
        present: true
      },
      service: {
        path: "~/.config/systemd/user/gateway-agent.service",
        present: true
      },
      wrapper: {
        path: "~/.local/bin/gateway-agent",
        present: true
      },
      commands: {
        stop: "~/.local/bin/gateway-agent stop",
        uninstallDryRun: "~/.local/bin/gateway-agent uninstall --dry-run",
        uninstallApply: "~/.local/bin/gateway-agent uninstall --apply"
      }
    }
  });

  assert.equal(status.linuxLifecycle.state, "installed");
  assert.equal(status.linuxLifecycle.config.profilePresent, true);
  assert.equal(status.linuxLifecycle.contract.stop, "preserve-config");
  assert.equal(status.linuxLifecycle.contract.uninstall, "purge-project-owned");
});

test("maps Linux v3 lifecycle into unified self-check evidence", () => {
  const check = linuxLifecycleSelfCheck({
    ok: true,
    state: "installed",
    summary: "Linux v3 control layer is installed",
    contract: {
      stop: "preserve-config",
      uninstall: "purge-project-owned"
    },
    config: {
      path: "~/.config/proxy-gateway",
      present: true,
      profilePresent: true
    }
  });

  assert.equal(check.id, "linux-v3-lifecycle");
  assert.equal(check.status, "pass");
  assert.equal(check.evidence.contract.stop, "preserve-config");
  assert.equal(check.evidence.config.profilePresent, true);
});

test("omits gateway agent status unless v2 feature flag is enabled", () => {
  const previous = process.env.GATEWAY_AGENT_V2;
  delete process.env.GATEWAY_AGENT_V2;
  try {
    const status = mapRuntimeStatus(runtime, links);

    assert.equal(status.gatewayAgent, undefined);
  } finally {
    if (previous === undefined) {
      delete process.env.GATEWAY_AGENT_V2;
    } else {
      process.env.GATEWAY_AGENT_V2 = previous;
    }
  }
});

test("maps gateway agent v2 status as read-only when enabled", () => {
  const previous = process.env.GATEWAY_AGENT_V2;
  process.env.GATEWAY_AGENT_V2 = "1";
  try {
    const status = mapRuntimeStatus(runtime, links, {
      gatewayAgent: {
        ok: true,
        enabled: true,
        state: "manifest_ready",
        summary: "read-only status available",
        generatedAt: "2026-05-03T12:00:00Z",
        runtimeDir: "/run/user/1000/proxy-gateway",
        sessionPath: "/run/user/1000/proxy-gateway/session.json",
        session: {
          listeners: {
            httpProxy: { host: "127.0.0.1", port: 43123 }
          }
        },
        usb: { present: false, trusted: false, state: "not_implemented" },
        privateRuntime: { state: "tmpfs", logs: "redacted" }
      }
    });

    assert.equal(status.gatewayAgent.v2, true);
    assert.equal(status.gatewayAgent.mode, "read-only");
    assert.equal(status.gatewayAgent.enabled, true);
    assert.equal(status.gatewayAgent.ok, true);
    assert.equal(status.gatewayAgent.state, "manifest_ready");
    assert.equal(status.gatewayAgent.probes.runtimeDir.value, "/run/user/1000/proxy-gateway");
    assert.equal(status.gatewayAgent.probes.session.value, "present");
  } finally {
    if (previous === undefined) {
      delete process.env.GATEWAY_AGENT_V2;
    } else {
      process.env.GATEWAY_AGENT_V2 = previous;
    }
  }
});

test("maps gateway controller contract without leaking secrets", () => {
  const controller = gatewayControllerFromStatus({
    ok: true,
    enabled: true,
    state: "manifest_ready",
    summary: "session ready",
    generatedAt: "2026-05-04T00:00:00Z",
    profileSource: {
      mode: "local",
      state: "encrypted_profile_present",
      present: true,
      path: "~/.config/proxy-gateway/profile.json.enc"
    },
    unlock: {
      state: "unlocked",
      profileLoaded: true,
      profileDigest: "abc123",
      profileSummary: {
        name: "linux-lan-gateway",
        routeIds: ["old", "new", "failover", "lanProxy"]
      }
    },
    session: {
      listeners: {
        lanProxy: { host: "10.10.0.10", port: 42001 },
        httpProxy: { host: "127.0.0.1", port: 42002 }
      }
    },
    runtimeState: {
      state: "running",
      children: [{ id: "lanProxy", host: "10.10.0.10", port: 42001 }]
    },
    phoneSetup: {
      enabled: true,
      state: "lan_listener_on",
      summary: "LAN proxy is available",
      pac: {
        available: true,
        mimeType: "application/x-ns-proxy-autoconfig",
        content: "function FindProxyForURL(url, host) { return \"PROXY 10.10.0.10:42001; DIRECT\"; }"
      }
    }
  });
  const serialized = JSON.stringify(controller);

  assert.equal(controller.version, 2);
  assert.equal(controller.profile.source.mode, "local");
  assert.equal(controller.profile.loaded, true);
  assert.equal(controller.runtime.state, "running");
  assert.equal(controller.phoneSetup.state, "lan_listener_on");
  assert.equal(controller.phoneSetup.pac.available, true);
  assert.equal(controller.privacy.secretsReturned, false);
  assert.doesNotMatch(serialized, /profile\.json\.enc/);
  assert.doesNotMatch(serialized, /127\.0\.0\.1:42002/);
});

test("gateway PAC contract returns PAC content only when LAN setup is enabled", () => {
  const missing = gatewayPacFromStatus({ phoneSetup: { enabled: false } });
  const present = gatewayPacFromStatus({
    phoneSetup: {
      enabled: true,
      pac: {
        available: true,
        mimeType: "application/x-ns-proxy-autoconfig",
        content: "function FindProxyForURL(url, host) { return \"PROXY 10.10.0.10:42001; DIRECT\"; }"
      }
    }
  });

  assert.equal(missing.ok, false);
  assert.equal(missing.statusCode, 409);
  assert.equal(present.ok, true);
  assert.match(present.content, /FindProxyForURL/);
  assert.doesNotMatch(present.content, /127\.0\.0\.1/);
});

test("gateway controller sensitive actions are blocked without local auth", () => {
  const unlock = gatewayControllerActionBlocked("unlock");
  const profileImport = gatewayControllerActionBlocked("profile-import");
  const profileExport = gatewayControllerActionBlocked("profile-export");

  assert.equal(unlock.ok, false);
  assert.equal(unlock.state, "local_auth_required");
  assert.equal(unlock.action, "unlock");
  assert.equal(profileImport.state, "local_auth_required");
  assert.equal(profileExport.state, "local_auth_required");
});

test("Linux web actions can start a loopback-only v2 gateway session", async () => {
  const previousFlag = process.env.GATEWAY_AGENT_V2;
  const previousRuntimeDir = process.env.GATEWAY_AGENT_RUNTIME_DIR;
  const runtimeDir = await mkdtemp(join(tmpdir(), "gateway-agent-web-action-"));

  try {
    process.env.GATEWAY_AGENT_V2 = "0";
    process.env.GATEWAY_AGENT_RUNTIME_DIR = runtimeDir;

    assert.ok(actions.some((action) => action.id === "gateway-agent-start"));

    const start = await runAction("gateway-agent-start");
    const parsed = JSON.parse(start.stdout);
    assert.equal(start.ok, true);
    assert.equal(parsed.enabled, true);
    assert.equal(parsed.state, "manifest_ready");
    assert.equal(parsed.session.listeners.lanProxy.host, "127.0.0.1");

    const stop = await runAction("linux-v3-stop");
    assert.equal(stop.ok, true);
  } finally {
    if (previousFlag === undefined) {
      delete process.env.GATEWAY_AGENT_V2;
    } else {
      process.env.GATEWAY_AGENT_V2 = previousFlag;
    }
    if (previousRuntimeDir === undefined) {
      delete process.env.GATEWAY_AGENT_RUNTIME_DIR;
    } else {
      process.env.GATEWAY_AGENT_RUNTIME_DIR = previousRuntimeDir;
    }
    await rm(runtimeDir, { recursive: true, force: true });
  }
});

test("Linux profile import validation rejects non encrypted config", () => {
  const result = validateLinuxProfileUpload({
    fileName: "upstream.json",
    contentBase64: Buffer.from("{}").toString("base64")
  });

  assert.equal(result.ok, false);
  assert.match(result.summary, /profile\.json\.enc/);
});

test("Linux desktop package status has stable launcher fields", async () => {
  const status = await linuxDesktopPackageStatus({ home: "/tmp/proxy-gateway-missing-home" });

  assert.equal(status.state, "missing");
  assert.match(status.launcher, /proxy-gateway-desktop/);
  assert.match(status.releaseBinary, /proxy-gateway-test/);
});

test("Linux local UI routes expose profile import and package status", () => {
  const server = readFileSync("server/index.mjs", "utf8");

  assert.match(server, /linuxDesktopPackageStatus/);
  assert.match(server, /importLinuxProfileUpload/);
  assert.match(server, /\/api\/linux\/desktop-package/);
  assert.match(server, /\/api\/linux\/profile\/import/);
});

test("Linux proxy unification model is read-only and has no destructive commands", () => {
  const result = buildLinuxProxyUnification({
    ports: [
      { id: "old-socks", host: "127.0.0.1", port: 1080, open: true },
      { id: "old-http", host: "127.0.0.1", port: 8118, open: true },
      { id: "new-socks", host: "127.0.0.1", port: 11880, open: true },
      { id: "new-http", host: "127.0.0.1", port: 18122, open: true },
      { id: "failover", host: "127.0.0.1", port: 18180, open: true },
      { id: "iphone-lan", host: "LAN", port: 18181, open: true },
      { id: "split-dns", host: "0.0.0.0", port: 1053, open: true },
      { id: "split-tcp", host: "0.0.0.0", port: 12345, open: true }
    ]
  });

  assert.equal(result.versionCount, 2);
  assert.equal(result.mode, "read-only");
  assert.equal(result.actions.length, 0);
  assert.doesNotMatch(JSON.stringify(result), /root-apply|systemctl|nft|nmcli|restart/);

  const source = readFileSync(new URL("./index.mjs", import.meta.url), "utf8");
  assert.match(source, /\/api\/linux\/proxy-unification/);
  assert.match(source, /knownExternalProxyServices/);
  assert.match(source, /externalServices:\s*knownExternalProxyServices\(\)/);
});
