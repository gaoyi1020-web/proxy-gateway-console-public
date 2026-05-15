import test from "node:test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { linuxDesktopPackageStatus } from "./linux-desktop-status.js";

test("linuxDesktopPackageStatus reports release launcher install", async () => {
  const home = await mkdtemp(join(tmpdir(), "linux-package-status-"));
  try {
    await mkdir(join(home, ".local/bin"), { recursive: true });
    await mkdir(join(home, ".local/share/applications"), { recursive: true });
    await mkdir(join(home, ".local/share/icons/hicolor/128x128/apps"), { recursive: true });
    await mkdir(join(home, ".local/share/proxy-gateway-desktop/self-use/bin"), { recursive: true });
    await writeFile(join(home, ".local/bin/proxy-gateway-desktop"), "exec /x/proxy-gateway-test\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/proxy-gateway-desktop/self-use/bin/proxy-gateway-test"), "#!/bin/sh\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/proxy-gateway-desktop/self-use/bin/gateway-agent"), "#!/bin/sh\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/applications/proxy-gateway-desktop.desktop"), `Exec=${join(home, ".local/bin/proxy-gateway-desktop")}\nIcon=proxy-gateway-desktop\n`);
    await writeFile(join(home, ".local/share/icons/hicolor/128x128/apps/proxy-gateway-desktop.png"), "png\n");

    const status = await linuxDesktopPackageStatus({ home });

    assert.equal(status.ok, true);
    assert.equal(status.state, "installed");
    assert.equal(status.launcherMode, "release");
    assert.deepEqual(status.legacyPresent, []);
    assert.equal(status.checks.singleDesktopEntry, true);
    assert.equal(status.checks.icon, true);
    assert.equal(status.checks.desktopEntryIcon, true);
    assert.equal(status.checks.launcherBackupsArchived, true);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test("linuxDesktopPackageStatus flags duplicate legacy launchers", async () => {
  const home = await mkdtemp(join(tmpdir(), "linux-package-status-"));
  try {
    await mkdir(join(home, ".local/bin"), { recursive: true });
    await mkdir(join(home, ".local/share/applications"), { recursive: true });
    await mkdir(join(home, ".local/share/icons/hicolor/128x128/apps"), { recursive: true });
    await mkdir(join(home, ".local/share/proxy-gateway-desktop/self-use/bin"), { recursive: true });
    await writeFile(join(home, ".local/bin/proxy-gateway-desktop"), "exec /x/proxy-gateway-test\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/proxy-gateway-desktop/self-use/bin/proxy-gateway-test"), "#!/bin/sh\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/proxy-gateway-desktop/self-use/bin/gateway-agent"), "#!/bin/sh\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/applications/proxy-gateway-desktop.desktop"), `Exec=${join(home, ".local/bin/proxy-gateway-desktop")}\nIcon=proxy-gateway-desktop\n`);
    await writeFile(join(home, ".local/share/icons/hicolor/128x128/apps/proxy-gateway-desktop.png"), "png\n");
    await writeFile(join(home, ".local/share/applications/proxy-app.desktop"), "Name=Proxy\n");

    const status = await linuxDesktopPackageStatus({ home });

    assert.equal(status.ok, false);
    assert.equal(status.state, "installed");
    assert.equal(status.checks.singleDesktopEntry, false);
    assert.match(status.summary, /duplicate launcher entries/);
    assert.equal(status.legacyPresent.length, 1);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test("linuxDesktopPackageStatus flags missing desktop app icon", async () => {
  const home = await mkdtemp(join(tmpdir(), "linux-package-status-"));
  try {
    await mkdir(join(home, ".local/bin"), { recursive: true });
    await mkdir(join(home, ".local/share/applications"), { recursive: true });
    await mkdir(join(home, ".local/share/proxy-gateway-desktop/self-use/bin"), { recursive: true });
    await writeFile(join(home, ".local/bin/proxy-gateway-desktop"), "exec /x/proxy-gateway-test\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/proxy-gateway-desktop/self-use/bin/proxy-gateway-test"), "#!/bin/sh\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/proxy-gateway-desktop/self-use/bin/gateway-agent"), "#!/bin/sh\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/applications/proxy-gateway-desktop.desktop"), `Exec=${join(home, ".local/bin/proxy-gateway-desktop")}\nIcon=network-vpn\n`);

    const status = await linuxDesktopPackageStatus({ home });

    assert.equal(status.ok, false);
    assert.equal(status.state, "installed");
    assert.equal(status.checks.icon, false);
    assert.equal(status.checks.desktopEntryIcon, false);
    assert.match(status.summary, /icon is incomplete/);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test("linuxDesktopPackageStatus flags launcher backups outside archive", async () => {
  const home = await mkdtemp(join(tmpdir(), "linux-package-status-"));
  try {
    await mkdir(join(home, ".local/bin"), { recursive: true });
    await mkdir(join(home, ".local/share/applications"), { recursive: true });
    await mkdir(join(home, ".local/share/icons/hicolor/128x128/apps"), { recursive: true });
    await mkdir(join(home, ".local/share/proxy-gateway-desktop/self-use/bin"), { recursive: true });
    await writeFile(join(home, ".local/bin/proxy-gateway-desktop"), "exec /x/proxy-gateway-test\n", { mode: 0o755 });
    await writeFile(join(home, ".local/bin/proxy-gateway-desktop.bak.20260508180137"), "old\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/proxy-gateway-desktop/self-use/bin/proxy-gateway-test"), "#!/bin/sh\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/proxy-gateway-desktop/self-use/bin/gateway-agent"), "#!/bin/sh\n", { mode: 0o755 });
    await writeFile(join(home, ".local/share/applications/proxy-gateway-desktop.desktop"), `Exec=${join(home, ".local/bin/proxy-gateway-desktop")}\nIcon=proxy-gateway-desktop\n`);
    await writeFile(join(home, ".local/share/icons/hicolor/128x128/apps/proxy-gateway-desktop.png"), "png\n");

    const status = await linuxDesktopPackageStatus({ home });

    assert.equal(status.ok, false);
    assert.equal(status.state, "installed");
    assert.equal(status.checks.launcherBackupsArchived, false);
    assert.equal(status.launcherBackups.length, 1);
    assert.match(status.summary, /launcher backups outside the archive/);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test("linuxDesktopPackageStatus flags old dev launcher", async () => {
  const home = await mkdtemp(join(tmpdir(), "linux-package-status-"));
  try {
    await mkdir(join(home, ".local/bin"), { recursive: true });
    await writeFile(join(home, ".local/bin/proxy-gateway-desktop"), "npm run desktop:dev\n", { mode: 0o755 });

    const status = await linuxDesktopPackageStatus({ home });

    assert.equal(status.ok, false);
    assert.equal(status.launcherMode, "dev");
    assert.match(status.summary, /dev command/);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test("linuxDesktopPackageStatus reports missing install with stable paths", async () => {
  const home = await mkdtemp(join(tmpdir(), "linux-package-status-"));
  try {
    const status = await linuxDesktopPackageStatus({ home });

    assert.equal(status.ok, false);
    assert.equal(status.state, "missing");
    assert.match(status.launcher, /proxy-gateway-desktop/);
    assert.match(status.releaseBinary, /proxy-gateway-test/);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});
