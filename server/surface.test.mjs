import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { build } from "esbuild";

const require = createRequire(import.meta.url);

async function loadSurface() {
  const tempDir = await mkdtemp(join(process.cwd(), "node_modules", ".surface-test-"));
  const outfile = join(tempDir, "surface.cjs");
  await build({
    entryPoints: ["src/lib/surface.ts"],
    outfile,
    bundle: true,
    platform: "node",
    format: "cjs",
    target: "node20",
    logLevel: "silent"
  });
  return {
    module: require(outfile),
    cleanup: () => rm(tempDir, { recursive: true, force: true })
  };
}

test("detectSurface identifies Linux desktop shell", async () => {
  const { module, cleanup } = await loadSurface();
  try {
    const surface = module.detectSurface({
      hasTauri: true,
      userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605"
    });
    assert.deepEqual(surface, { desktop: true, os: "linux" });
  } finally {
    await cleanup();
  }
});

test("desktopPanels hides Mac-only controls on Linux", async () => {
  const { module, cleanup } = await loadSurface();
  try {
    assert.deepEqual(module.desktopPanels({ desktop: true, os: "linux" }), ["agent", "proxy"]);
    assert.deepEqual(module.desktopPanels({ desktop: true, os: "mac" }), ["agent", "proxy", "mac"]);
    assert.deepEqual(module.desktopPanels({ desktop: false, os: "web" }), []);
  } finally {
    await cleanup();
  }
});
