import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { join } from "node:path";
import { build } from "esbuild";

const require = createRequire(import.meta.url);

async function loadViewModel() {
  const tempDir = await mkdtemp(join(process.cwd(), "node_modules", ".linux-console-view-model-test-"));
  const outfile = join(tempDir, "linuxConsoleViewModel.cjs");
  await build({
    entryPoints: ["src/components/linuxConsoleViewModel.ts"],
    outfile,
    bundle: true,
    platform: "node",
    format: "cjs",
    target: "node20",
    logLevel: "silent"
  });
  const module = require(outfile);
  return {
    buildLinuxConsoleViewModel: module.buildLinuxConsoleViewModel,
    cleanup: () => rm(tempDir, { recursive: true, force: true })
  };
}

const baseStatus = {
  generatedAt: "2026-05-09T00:00:00Z",
  links: [],
  statuses: [],
  environment: {
    httpProxy: "",
    httpsProxy: "",
    allProxy: "",
    defaultRoute: ""
  },
  networkEvents: {
    events: [],
    pending: []
  },
  linuxLifecycle: {
    ok: true,
    state: "ready",
    summary: "ready",
    contract: { stop: "preserve-config", uninstall: "purge-project-owned" },
    config: {
      path: "~/.config/proxy-gateway",
      present: true,
      profilePresent: true
    },
    runtime: { path: "/run/user/1000/proxy-gateway", present: true },
    service: { path: "~/.config/systemd/user/proxy-dashboard.service", present: true },
    wrapper: { path: "~/.local/bin/proxy-gateway-desktop", present: true },
    commands: {
      stop: "proxy-gateway stop",
      uninstallDryRun: "proxy-gateway uninstall --dry-run",
      uninstallApply: "proxy-gateway uninstall --apply"
    }
  },
  iphoneLanProxy: {
    server: "10.10.0.10",
    port: 18181,
    setting: "10.10.0.10:18181",
    authentication: false,
    target: "foreign -> new",
    allowCidr: "10.10.0.0/24",
    portOpen: false,
    firewall: { status: "closed", summary: "not open" },
    recentClients: [],
    recentUpstreams: []
  },
  hotspotPreflight: {
    connection: "hotspot",
    allowed: false,
    risk: "gui_locked",
    message: "热点保护触发",
    hotspot_interface: "wlan0",
    hotspot_mode: "ap",
    default_route: "default via 10.10.0.1",
    default_route_interface: "wlan0",
    recommendation: "keep current"
  },
  gatewayAgent: {
    v2: true,
    enabled: true,
    ok: true,
    state: "manifest_ready",
    summary: "ready",
    mode: "read-only",
    updatedAt: "2026-05-09T00:00:00Z",
    probes: {
      session: { ok: false, value: "manifest" }
    },
    errors: []
  }
};

const proxyUnification = {
  ok: true,
  mode: "read-only",
  generatedAt: "2026-05-09T00:00:00Z",
  versionCount: 2,
  unifiedEntry: {
    currentHttp: { host: "127.0.0.1", port: 18180, open: true },
    futureSocks: { host: "127.0.0.1", port: 18182, open: false, planned: true }
  },
  upstreams: [],
  adapters: [],
  policy: {
    private: "direct",
    domestic: "direct",
    foreign: "proxy",
    preferredForeignUpstream: "new",
    fallbackOrder: ["new", "old"]
  },
  externalServices: [],
  optimizationReadiness: {
    phase: "observe-only",
    dispatcherActive: false,
    blockers: [],
    safeNextSteps: []
  },
  risks: [],
  recommendedCutoverOrder: [],
  actions: []
};

test("buildLinuxConsoleViewModel maps runtime status into stable console cards", async () => {
  const { buildLinuxConsoleViewModel, cleanup } = await loadViewModel();
  try {
    const viewModel = buildLinuxConsoleViewModel(baseStatus, proxyUnification);

    assert.equal(viewModel.sessionActive, true);
    assert.equal(viewModel.sessionActionId, "linux-v3-stop");
    assert.deepEqual(viewModel.cards.map((card) => card.id), ["service", "phone", "config", "guard"]);

    assert.deepEqual(viewModel.cards.map((card) => [card.id, card.state, card.stateLabel]), [
      ["service", "ok", "在线"],
      ["phone", "warn", "关注"],
      ["config", "ok", "在线"],
      ["guard", "warn", "关注"]
    ]);

    assert.equal(viewModel.cards[0].value, "正常");
    assert.equal(viewModel.cards[0].summary, "本机入口 127.0.0.1:18180");
    assert.equal(viewModel.cards[2].summary, "加密配置已存在");
  } finally {
    await cleanup();
  }
});

test("buildLinuxConsoleViewModel keeps empty state deterministic before status loads", async () => {
  const { buildLinuxConsoleViewModel, cleanup } = await loadViewModel();
  try {
    const viewModel = buildLinuxConsoleViewModel(null, null);

    assert.equal(viewModel.sessionActive, false);
    assert.equal(viewModel.sessionActionId, "gateway-agent-start");
    assert.deepEqual(viewModel.cards.map((card) => [card.id, card.state, card.value, card.stateLabel]), [
      ["service", "off", "等待", "等待"],
      ["phone", "off", "未就绪", "等待"],
      ["config", "off", "未导入", "等待"],
      ["guard", "off", "等待检测", "等待"]
    ]);
  } finally {
    await cleanup();
  }
});

test("buildLinuxConsoleViewModel keeps operation cards concise", async () => {
  const { buildLinuxConsoleViewModel, cleanup } = await loadViewModel();
  try {
    const noisyStatus = {
      ...baseStatus,
      hotspotPreflight: {
        ...baseStatus.hotspotPreflight,
        allowed: false,
        message: "Use sudo ~/.local/bin/hotspot-safe-start after moving upstream to Ethernet."
      }
    };
    const viewModel = buildLinuxConsoleViewModel(noisyStatus, proxyUnification);
    const guard = viewModel.cards.find((card) => card.id === "guard");

    assert.equal(guard.summary, "热点保护已启用；详情见状态页");
    assert.doesNotMatch(guard.summary, /sudo|hotspot-safe-start|Ethernet/i);
  } finally {
    await cleanup();
  }
});
