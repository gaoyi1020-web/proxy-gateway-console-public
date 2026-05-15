import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import {
  buildUpdateManifest,
  classifyReleaseAsset,
} from "../scripts/release/update-manifest.mjs";

const execFileAsync = promisify(execFile);

async function text(path) {
  return readFile(path, "utf8");
}

test("update manifest classifies installable Mac and source release assets", async () => {
  const dir = await mkdtemp(join(tmpdir(), "proxy-update-manifest-"));
  try {
    const macAsset = join(dir, "ProxyGateway-Mac-SelfUse-0.2.0.zip");
    const sourceAsset = join(dir, "ProxyGateway-Console-0.2.0-archive-20260515.tar.gz");
    await writeFile(macAsset, "mac package\n");
    await writeFile(sourceAsset, "source archive\n");

    const manifest = await buildUpdateManifest({
      repo: "gaoyi1020-web/proxy-gateway-console-public",
      tag: "v0.2.0",
      version: "0.2.0",
      assets: [macAsset, sourceAsset],
      generatedAt: "2026-05-15T00:00:00.000Z",
    });

    assert.equal(manifest.schemaVersion, 1);
    assert.equal(manifest.repo, "gaoyi1020-web/proxy-gateway-console-public");
    assert.equal(manifest.version, "0.2.0");
    assert.equal(manifest.tag, "v0.2.0");
    assert.equal(manifest.release.htmlUrl, "https://github.com/gaoyi1020-web/proxy-gateway-console-public/releases/tag/v0.2.0");

    const mac = manifest.assets.find((asset) => asset.id === "mac-self-use");
    assert.equal(mac.platform, "darwin");
    assert.equal(mac.arch, "universal");
    assert.equal(mac.installable, true);
    assert.equal(mac.url, "https://github.com/gaoyi1020-web/proxy-gateway-console-public/releases/download/v0.2.0/ProxyGateway-Mac-SelfUse-0.2.0.zip");
    assert.match(mac.sha256, /^[a-f0-9]{64}$/);
    assert.equal(mac.size, "mac package\n".length);

    const source = manifest.assets.find((asset) => asset.id === "source-archive");
    assert.equal(source.platform, "source");
    assert.equal(source.installable, false);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("update manifest rejects private runtime asset names", async () => {
  assert.throws(
    () => classifyReleaseAsset("upstream.json"),
    /private runtime asset/,
  );
  assert.throws(
    () => classifyReleaseAsset("profile.json.enc"),
    /private runtime asset/,
  );
});

test("self updater verifies manifest checksums before install", async () => {
  const updater = await text("scripts/update/proxy-gateway-self-update.sh");
  const macPackage = await text("scripts/macvpn/package-self-use-installer.sh");
  const macCtl = await text("scripts/macvpn/macvpnctl.sh");
  const linuxInstall = await text("scripts/desktop/linux-install-self-use.sh");

  assert.match(updater, /PROXY_GATEWAY_UPDATE_REPO:-gaoyi1020-web\/proxy-gateway-console-public/);
  assert.match(updater, /proxy-gateway-update-manifest\.json/);
  assert.match(updater, /sha256/);
  assert.match(updater, /verify_asset_checksum/);
  assert.match(updater, /expected checksum/);
  assert.match(updater, /--install/);
  assert.match(updater, /--yes/);
  assert.match(updater, /Install Proxy Gateway\.command/);
  assert.match(updater, /PROXY_GATEWAY_SKIP_ROOTCTL_INSTALL="\$\{PROXY_GATEWAY_SKIP_ROOTCTL_INSTALL:-1\}" bash "\$\{installer\}"/);
  assert.doesNotMatch(updater, /profile\.json\.enc/);
  assert.doesNotMatch(updater, /upstream\.json/);
  assert.match(macPackage, /payload\/VERSION/);
  assert.match(macPackage, /TARGET\}\/VERSION/);
  assert.match(macPackage, /payload\/update\/proxy-gateway-self-update\.sh/);
  assert.match(macPackage, /TARGET\}\/proxy-gateway-self-update\.sh/);
  assert.match(macCtl, /update-check\) run_update --check/);
  assert.match(macCtl, /update-download\) run_update --download/);
  assert.match(macCtl, /update-install\) run_update --install/);
  assert.match(linuxInstall, /INSTALL_ROOT\}\/VERSION/);
});

test("release workflow publishes update manifest beside release assets", async () => {
  const workflow = await text(".github/workflows/release.yml");
  const macBuildScript = await text("macos/ProxyGatewayDesktop/script/build_and_run.sh");

  assert.match(workflow, /name: Release/);
  assert.match(workflow, /workflow_dispatch/);
  assert.match(workflow, /ProxyGateway-Mac-SelfUse-\$\{\{ env\.RELEASE_VERSION \}\}\.zip/);
  assert.match(workflow, /proxy-gateway-update-manifest\.json/);
  assert.match(workflow, /scripts\/release\/update-manifest\.mjs/);
  assert.match(workflow, /gh release upload/);
  assert.match(workflow, /permissions:\n  contents: write/);
  assert.match(workflow, /PROXY_GATEWAY_DESKTOP_VERSION: \$\{\{ env\.RELEASE_VERSION \}\}/);
  assert.match(workflow, /PROXY_GATEWAY_DESKTOP_BUILD: \$\{\{ github\.run_number \}\}/);
  assert.match(macBuildScript, /SHORT_VERSION="\$\{PROXY_GATEWAY_DESKTOP_VERSION:-0\.2\.0\}"/);
  assert.match(macBuildScript, /BUNDLE_VERSION="\$\{PROXY_GATEWAY_DESKTOP_BUILD:-2\}"/);
});

test("update scripts are shell syntax clean", async () => {
  await execFileAsync("bash", ["-n", "scripts/update/proxy-gateway-self-update.sh"]);
});
