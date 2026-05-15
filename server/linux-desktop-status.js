import { access, constants, readdir } from "node:fs/promises";
import { readFile, stat } from "node:fs/promises";
import { join } from "node:path";

async function executable(path) {
  try {
    await access(path, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function present(path) {
  try {
    const item = await stat(path);
    return item.isFile() || item.isDirectory();
  } catch {
    return false;
  }
}

async function launcherMode(path) {
  try {
    const text = await readFile(path, "utf8");
    if (/desktop:dev|tauri dev|npm run desktop:dev|vite --host 127\.0\.0\.1/.test(text)) {
      return "dev";
    }
    if (/proxy-gateway-test/.test(text)) {
      return "release";
    }
    return "unknown";
  } catch {
    return "missing";
  }
}

export async function linuxDesktopPackageStatus(options = {}) {
  const home = options.home || process.env.HOME || "";
  const installRoot = join(home, ".local/share/proxy-gateway-desktop/self-use");
  const binDir = join(home, ".local/bin");
  const launcher = join(home, ".local/bin/proxy-gateway-desktop");
  const releaseBinary = join(installRoot, "bin/proxy-gateway-test");
  const sidecar = join(installRoot, "bin/gateway-agent");
  const desktopEntry = join(home, ".local/share/applications/proxy-gateway-desktop.desktop");
  const desktopCopy = join(home, "Desktop/Proxy Gateway Desktop.desktop");
  const icon = join(home, ".local/share/icons/hicolor/128x128/apps/proxy-gateway-desktop.png");
  const legacyDesktopEntries = [
    join(home, ".local/share/applications/proxy-app.desktop"),
    join(home, ".local/share/applications/proxy-dashboard.desktop")
  ];
  let desktopEntryText = "";
  try {
    desktopEntryText = await readFile(desktopEntry, "utf8");
  } catch {
    desktopEntryText = "";
  }
  let launcherBackups = [];
  try {
    const entries = await readdir(binDir);
    launcherBackups = entries
      .filter((entry) => /^proxy-gateway-desktop\.bak\./.test(entry))
      .map((entry) => join(binDir, entry));
  } catch {
    launcherBackups = [];
  }
  const mode = await launcherMode(launcher);
  const legacyPresent = [];
  for (const entry of legacyDesktopEntries) {
    if (await present(entry)) {
      legacyPresent.push(entry);
    }
  }
  const desktopCopyPresent = await present(desktopCopy);
  const checks = {
    launcher: await executable(launcher),
    releaseBinary: await executable(releaseBinary),
    sidecar: await executable(sidecar),
    desktopEntry: await present(desktopEntry),
    singleDesktopEntry: legacyPresent.length === 0 && !desktopCopyPresent,
    icon: await present(icon),
    desktopEntryIcon: /^Icon=proxy-gateway-desktop$/m.test(desktopEntryText),
    launcherBackupsArchived: launcherBackups.length === 0
  };
  const installed = checks.launcher && checks.releaseBinary && checks.sidecar && checks.desktopEntry;
  const ok = installed && mode === "release" && checks.singleDesktopEntry && checks.icon
    && checks.desktopEntryIcon && checks.launcherBackupsArchived;
  const summary = ok
    ? "Linux desktop self-use package is installed"
    : mode === "dev"
      ? "launcher still uses a dev command"
      : installed && !checks.singleDesktopEntry
        ? "Linux desktop package has duplicate launcher entries"
        : installed && !checks.launcherBackupsArchived
          ? "Linux desktop package has launcher backups outside the archive"
          : installed && (!checks.icon || !checks.desktopEntryIcon)
            ? "Linux desktop package icon is incomplete"
            : "Linux desktop package is incomplete";
  return {
    ok,
    state: installed ? "installed" : "missing",
    launcherMode: mode,
    summary,
    installRoot,
    launcher,
    releaseBinary,
    sidecar,
    desktopEntry,
    desktopCopy,
    icon,
    legacyDesktopEntries,
    legacyPresent,
    launcherBackups,
    checks
  };
}
