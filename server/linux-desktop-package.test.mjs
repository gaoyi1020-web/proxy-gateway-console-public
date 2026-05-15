import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

async function text(path) {
  return readFile(path, "utf8");
}

test("Linux self-use desktop installer does not launch tauri dev", async () => {
  const installScript = await text("scripts/desktop/linux-install-self-use.sh");
  const verifyScript = await text("scripts/desktop/linux-verify-self-use.sh");

  assert.match(installScript, /INSTALL_ROOT=/);
  assert.match(installScript, /\.local\/share\/proxy-gateway-desktop/);
  assert.match(installScript, /proxy-gateway-desktop\.desktop/);
  assert.match(installScript, /LEGACY_DESKTOP_FILES=/);
  assert.match(installScript, /legacy-launchers/);
  assert.match(installScript, /ICON_NAME="proxy-gateway-desktop"/);
  assert.match(installScript, /Icon=\$\{ICON_NAME\}/);
  assert.match(installScript, /gtk-update-icon-cache/);
  assert.match(installScript, /proxy-gateway-desktop\.bak\.\*/);
  assert.match(installScript, /Exec=\$\{LAUNCHER\}/);
  assert.match(installScript, /INSTALL_ROOT\}\/notices/);
  assert.match(installScript, /THIRD_PARTY_NOTICES\.md/);
  assert.doesNotMatch(installScript, /cp "\$\{DESKTOP_FILE\}" "\$\{DESKTOP_COPY\}"/);
  assert.doesNotMatch(installScript, /desktop:dev/);
  assert.doesNotMatch(installScript, /tauri dev/);
  assert.match(verifyScript, /desktop:dev/);
  assert.match(verifyScript, /must not launch npm run desktop:dev/);
  assert.match(verifyScript, /desktop copy is not installed/);
  assert.match(verifyScript, /legacy proxy app entry is absent/);
  assert.match(verifyScript, /app icon exists/);
  assert.match(verifyScript, /desktop entry uses installed app icon/);
  assert.match(verifyScript, /launcher backups are archived/);
  assert.match(verifyScript, /project license notice exists/);
  assert.match(verifyScript, /third-party notices exist/);
});

test("Linux self-use build script creates release artifacts and sidecar manifest", async () => {
  const buildScript = await text("scripts/desktop/linux-build-self-use.sh");

  assert.match(buildScript, /npm run build/);
  assert.match(buildScript, /scripts\/desktop\/build-agent-sidecar\.sh --apply/);
  assert.match(buildScript, /npm run desktop:build -- --no-bundle/);
  assert.doesNotMatch(buildScript, /cargo build --release --manifest-path src-tauri\/Cargo\.toml/);
  assert.match(buildScript, /OS file watch limit reached|failed to watch/);
  assert.match(buildScript, /verify_embedded_frontend/);
  assert.match(buildScript, /refusing to package stale or dev-url desktop build/);
  assert.match(buildScript, /existing-embedded-after-watch-limit/);
  assert.match(buildScript, /Reusing existing embedded release binary/);
  assert.match(buildScript, /preserve_dist_artifacts/);
  assert.match(buildScript, /restore_dist_artifacts/);
  assert.match(buildScript, /archive self-use/);
  assert.match(buildScript, /embedded_path="\/assets\/\$\(basename "\$\{asset\}"\)"/);
  assert.match(buildScript, /install -m 0755 "\$\{SIDECAR\}" "\$\{RELEASE_SIDECAR\}"/);
  assert.match(buildScript, /BUILD_MODE=/);
  assert.match(buildScript, /buildMode=%s/);
  assert.match(buildScript, /thirdPartyNotices=%s/);
  assert.match(buildScript, /RELEASE_SIDECAR=/);
  assert.match(buildScript, /src-tauri\/target\/release\/gateway-agent/);
  assert.match(buildScript, /sha256sum/);
  assert.match(buildScript, /dist\/linux-self-use/);
  assert.doesNotMatch(buildScript, /desktop:dev/);
});

test("system nft service template uses explicit public install defaults", async () => {
  const service = await text("runtime/proxy-stack/hotspot-split-nft.service");

  assert.match(service, /HOTSPOT_SPLIT_BASE=\/var\/lib\/hotspot-split-gateway/);
  assert.match(service, /HOTSPOT_SPLIT_BIN=\/usr\/local\/bin\/hotspot-split-gateway/);
  assert.match(service, /ExecStart=\/usr\/bin\/env bash -lc 'exec "\$HOTSPOT_SPLIT_BIN" root-apply'/);
  assert.doesNotMatch(service, /~\/\.local/);
  assert.doesNotMatch(service, /%h/);
});

test("frontend build preserves package archive directories", async () => {
  const packageJson = JSON.parse(await text("package.json"));
  const viteConfig = await text("vite.config.ts");
  const cleanScript = await text("scripts/frontend-clean-dist.sh");

  assert.match(packageJson.scripts.build, /scripts\/frontend-clean-dist\.sh/);
  assert.match(viteConfig, /emptyOutDir:\s*false/);
  assert.match(cleanScript, /! -name archive/);
  assert.match(cleanScript, /! -name self-use/);
  assert.match(cleanScript, /! -name linux-self-use/);
});

test("Linux self-use install and verify use release sidecar beside app binary", async () => {
  const installScript = await text("scripts/desktop/linux-install-self-use.sh");
  const verifyScript = await text("scripts/desktop/linux-verify-self-use.sh");
  const smokeScript = await text("scripts/desktop/linux-smoke-self-use.sh");
  const packageJson = JSON.parse(await text("package.json"));

  assert.match(installScript, /RELEASE_SIDECAR=/);
  assert.match(installScript, /target\/release\/gateway-agent/);
  assert.match(installScript, /install -m 0755 "\$\{RELEASE_SIDECAR\}" "\$\{INSTALL_ROOT\}\/bin\/gateway-agent"/);
  assert.match(installScript, /install -m 0644 "\$\{ROOT_DIR\}\/LICENSE" "\$\{INSTALL_ROOT\}\/notices\/LICENSE"/);
  assert.match(installScript, /install -m 0644 "\$\{ROOT_DIR\}\/docs\/THIRD_PARTY_NOTICES\.md" "\$\{INSTALL_ROOT\}\/notices\/THIRD_PARTY_NOTICES\.md"/);
  assert.match(verifyScript, /SIDECAR_BIN="\$\{INSTALL_ROOT\}\/bin\/gateway-agent"/);
  assert.match(verifyScript, /sidecar binary exists/);
  assert.match(verifyScript, /LICENSE_FILE="\$\{INSTALL_ROOT\}\/notices\/LICENSE"/);
  assert.match(verifyScript, /THIRD_PARTY_NOTICES="\$\{INSTALL_ROOT\}\/notices\/THIRD_PARTY_NOTICES\.md"/);
  assert.equal(packageJson.scripts["desktop:smoke:self-use"], "scripts/desktop/linux-smoke-self-use.sh");
  assert.match(smokeScript, /GATEWAY_AGENT_RUNTIME_DIR="\$\{TMP_DIR\}\/runtime"/);
  assert.match(smokeScript, /profile-import --from/);
  assert.match(smokeScript, /uninstall --dry-run/);
  assert.match(smokeScript, /Linux self-use desktop smoke: pass/);
});

test("sidecar builder isolates PyInstaller from system Python", async () => {
  const sidecarScript = await text("scripts/desktop/build-agent-sidecar.sh");

  assert.match(sidecarScript, /PYINSTALLER_VENV=/);
  assert.match(sidecarScript, /PYINSTALLER_PYTHON="\$\{PYINSTALLER_VENV\}\/bin\/python"/);
  assert.match(sidecarScript, /\$\{PYINSTALLER_PYTHON\}" -m pip --version/);
  assert.match(sidecarScript, /import cryptography/);
  assert.match(sidecarScript, /pyinstaller cryptography/);
  assert.match(sidecarScript, /python3 -m venv/);
  assert.match(sidecarScript, /command -v virtualenv/);
  assert.match(sidecarScript, /uv venv --seed/);
  assert.match(sidecarScript, /\$\{PYINSTALLER_PYTHON\}" -m PyInstaller/);
  assert.match(sidecarScript, /--clean/);
  assert.match(sidecarScript, /AGENT_HIDDEN_IMPORTS=/);
  assert.match(sidecarScript, /--paths "\$\{ROOT_DIR\}\/agent"/);
  assert.match(sidecarScript, /--hidden-import "\$\{module\}"/);
  assert.match(sidecarScript, /port_registry/);
  assert.match(sidecarScript, /profile_crypto/);
  assert.doesNotMatch(sidecarScript, /pip install --user/);
});

test("Tauri Linux bundle config includes square icons", async () => {
  const tauriConfig = JSON.parse(await text("src-tauri/tauri.conf.json"));

  assert.ok(Array.isArray(tauriConfig.bundle.icon));
  assert.match(tauriConfig.bundle.icon.join("\n"), /icons\/128x128\.png/);
  assert.match(tauriConfig.bundle.icon.join("\n"), /icons\/128x128@2x\.png/);
  assert.deepEqual(tauriConfig.bundle.resources, ["../LICENSE", "../docs/THIRD_PARTY_NOTICES.md"]);
});

test("Tauri main window label matches the desktop capability scope", async () => {
  const tauriConfig = JSON.parse(await text("src-tauri/tauri.conf.json"));
  const capability = JSON.parse(await text("src-tauri/capabilities/default.json"));

  const labels = tauriConfig.app.windows.map((window) => window.label);

  assert.ok(labels.every(Boolean), "all Tauri windows should have explicit labels");
  assert.deepEqual(labels, ["main"]);
  assert.deepEqual(capability.windows, labels);
});

test("Tauri main window opens at the Linux desktop workbench size", async () => {
  const tauriConfig = JSON.parse(await text("src-tauri/tauri.conf.json"));
  const [mainWindow] = tauriConfig.app.windows;

  assert.equal(mainWindow.width, 1180);
  assert.equal(mainWindow.height, 820);
  assert.equal(mainWindow.minWidth, 920);
  assert.equal(mainWindow.minHeight, 680);
  assert.equal(mainWindow.center, true);
  assert.equal(mainWindow.resizable, true);
});

test("Tauri desktop integrates profile import and terminal-gated uninstall plan", async () => {
  const agentSource = await text("src-tauri/src/agent.rs");
  const linuxDesktopSource = await text("src-tauri/src/linux_desktop.rs");
  const mainSource = await text("src-tauri/src/main.rs");
  const desktopApi = await text("src/lib/desktopGatewayApi.ts");

  assert.match(mainSource, /agent::agent_profile_import/);
  assert.match(mainSource, /agent::agent_uninstall_plan/);
  assert.match(agentSource, /pub async fn agent_profile_import/);
  assert.match(agentSource, /profile-import/);
  assert.match(agentSource, /validate_profile_envelope/);
  assert.match(agentSource, /redact_import_value/);
  assert.match(agentSource, /pub async fn agent_uninstall_plan/);
  assert.match(agentSource, /--dry-run/);
  assert.match(mainSource, /linux_desktop::linux_desktop_package_status/);
  assert.match(linuxDesktopSource, /pub fn linux_desktop_package_status/);
  assert.match(linuxDesktopSource, /Icon=proxy-gateway-desktop/);
  assert.match(linuxDesktopSource, /launcherBackupsArchived/);
  assert.match(desktopApi, /invoke<LinuxProfileImportResult>\("agent_profile_import"/);
  assert.match(desktopApi, /invoke<CommandResult>\("agent_uninstall_plan"\)/);
  assert.match(desktopApi, /invoke<LinuxDesktopPackageStatus>\("linux_desktop_package_status"\)/);
});

test("Linux control actions use the GatewayApi instead of direct HTTP fetch", async () => {
  const controlActions = await text("src/components/LinuxControlActions.tsx");
  const gatewayApi = await text("src/lib/gatewayApi.ts");
  const httpApi = await text("src/lib/httpGatewayApi.ts");
  const desktopApi = await text("src/lib/desktopGatewayApi.ts");

  assert.doesNotMatch(controlActions, /fetch\("\/api\/actions/);
  assert.match(controlActions, /gatewayApi\.actions\(\)/);
  assert.match(controlActions, /gatewayApi\.runAction\(actionId\)/);
  assert.match(gatewayApi, /actions\(\): Promise<ActionDefinition\[\]>/);
  assert.match(gatewayApi, /runAction\(actionId: string\): Promise<ActionResult>/);
  assert.match(httpApi, /getJson<\{ actions: ActionDefinition\[\] \}>\("\/api\/actions"\)/);
  assert.match(httpApi, /postJson<ActionResult>\("\/api\/actions\/run"/);
  assert.match(desktopApi, /const desktopActions: ActionDefinition\[\]/);
  assert.match(desktopApi, /runDesktopAction/);
});
