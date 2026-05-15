import { CheckCircle2, CircleAlert, PackageCheck } from "lucide-react";
import type { LinuxDesktopPackageStatus } from "../lib/types";

export default function LinuxPackagePanel({ packageStatus }: { packageStatus: LinuxDesktopPackageStatus | null }) {
  const ok = Boolean(packageStatus?.ok);
  return (
    <section className="linux-v4-panel" aria-label="Linux desktop package">
      <div className="linux-v4-panel-head">
        <PackageCheck size={20} />
        <span>
          <strong>Linux 桌面包</strong>
          <small>{packageStatus?.summary || "等待安装状态"}</small>
        </span>
      </div>
      <div className={`linux-v4-package-state ${ok ? "ok" : "warn"}`}>
        {ok ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}
        <span>{packageStatus?.launcherMode || "unknown"}</span>
      </div>
      <code>{packageStatus?.launcher || "~/.local/bin/proxy-gateway-desktop"}</code>
    </section>
  );
}
