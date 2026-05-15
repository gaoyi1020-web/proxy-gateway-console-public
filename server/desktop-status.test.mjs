import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { join } from "node:path";
import { build } from "esbuild";

const require = createRequire(import.meta.url);

async function loadDesktopStatus() {
  const tempDir = await mkdtemp(join(process.cwd(), "node_modules", ".desktop-status-test-"));
  const outfile = join(tempDir, "desktopStatus.cjs");
  await build({
    entryPoints: ["src/lib/desktopStatus.ts"],
    outfile,
    bundle: true,
    platform: "node",
    format: "cjs",
    target: "node20",
    logLevel: "silent"
  });
  const module = require(outfile);
  return {
    module,
    cleanup: () => rm(tempDir, { recursive: true, force: true })
  };
}

const baseStatus = {
  generatedAt: "2026-05-05T00:00:00.000Z",
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
  }
};

test("buildDesktopStatus degrades to HTTP status when desktop sidecar is missing", async () => {
  const { module, cleanup } = await loadDesktopStatus();
  try {
    const status = module.buildDesktopStatus({
      baseStatus,
      commandError: new Error("没有那个文件或目录 (os error 2)"),
      generatedAt: "2026-05-05T04:40:00.000Z"
    });

    assert.equal(status.generatedAt, "2026-05-05T04:40:00.000Z");
    assert.deepEqual(status.links, baseStatus.links);
    assert.deepEqual(status.statuses, baseStatus.statuses);
    assert.deepEqual(status.networkEvents, baseStatus.networkEvents);
    assert.equal(status.gatewayAgent.v2, true);
    assert.equal(status.gatewayAgent.enabled, false);
    assert.equal(status.gatewayAgent.ok, false);
    assert.equal(status.gatewayAgent.state, "sidecar_unavailable");
    assert.match(status.gatewayAgent.summary, /desktop gateway-agent unavailable/);
    assert.deepEqual(status.gatewayAgent.errors, ["没有那个文件或目录 (os error 2)"]);
  } finally {
    await cleanup();
  }
});

test("buildDesktopStatus maps sidecar probes for the installed desktop client", async () => {
  const { module, cleanup } = await loadDesktopStatus();
  try {
    const status = module.buildDesktopStatus({
      baseStatus,
      commandResult: {
        ok: true,
        stderr: "",
        stdout: JSON.stringify({
          ok: true,
          enabled: true,
          state: "manifest_ready",
          summary: "v2 session manifest is ready",
          generatedAt: "2026-05-05T04:41:00.000Z",
          runtimeDir: "/run/user/1000/proxy-gateway",
          sessionPath: "/run/user/1000/proxy-gateway/session.json",
          session: { sessionId: "abc" },
          profileSource: { present: true, state: "encrypted_profile_present", mode: "local" },
          unlock: { state: "unlocked", bind: "127.0.0.1" },
          privateRuntime: { state: "tmpfs", logs: "redacted" },
          phoneSetup: { enabled: true, state: "ready", summary: "LAN listener ready" }
        })
      },
      generatedAt: "2026-05-05T04:42:00.000Z"
    });

    assert.equal(status.gatewayAgent.enabled, true);
    assert.equal(status.gatewayAgent.ok, true);
    assert.equal(status.gatewayAgent.state, "manifest_ready");
    assert.equal(status.gatewayAgent.probes.runtimeDir.value, "/run/user/1000/proxy-gateway");
    assert.equal(status.gatewayAgent.probes.session.value, "present");
    assert.equal(status.gatewayAgent.probes.profileSource.value, "encrypted_profile_present");
    assert.equal(status.gatewayAgent.probes.unlock.value, "unlocked");
    assert.equal(status.gatewayAgent.probes.lanExposure.value, "ready");
  } finally {
    await cleanup();
  }
});
