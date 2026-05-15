import { Clipboard, Eraser, FileSliders, Globe2, Network, Server } from "lucide-react";
import { useMemo, useState } from "react";
import type { GatewayApi } from "../lib/gatewayApi";
import type { LinuxDesktopPackageStatus, StatusResponse } from "../lib/types";
import LinuxConfigPanel from "./LinuxConfigPanel";
import LinuxPackagePanel from "./LinuxPackagePanel";

interface ConfigDraft {
  label: string;
  region: string;
  server: string;
  httpPort: string;
  socksPort: string;
  notes: string;
}

const defaultDraft: ConfigDraft = {
  label: "primary",
  region: "auto",
  server: "",
  httpPort: "18122",
  socksPort: "11880",
  notes: ""
};

function draftJson(draft: ConfigDraft) {
  return JSON.stringify(
    {
      profile: draft.label,
      region: draft.region,
      server: draft.server,
      ports: {
        http: Number(draft.httpPort) || draft.httpPort,
        socks: Number(draft.socksPort) || draft.socksPort
      },
      notes: draft.notes
    },
    null,
    2
  );
}

export default function LinuxConfigPage({
  status,
  packageStatus,
  gatewayApi,
  onImported
}: {
  status: StatusResponse | null;
  packageStatus: LinuxDesktopPackageStatus | null;
  gatewayApi: GatewayApi;
  onImported: () => void;
}) {
  const [draft, setDraft] = useState<ConfigDraft>(defaultDraft);
  const [copied, setCopied] = useState(false);
  const profilePresent = Boolean(status?.linuxLifecycle?.config.profilePresent);
  const configPath = status?.linuxLifecycle?.config.path || "~/.config/proxy-gateway";
  const renderedDraft = useMemo(() => draftJson(draft), [draft]);

  function updateDraft(field: keyof ConfigDraft, value: string) {
    setCopied(false);
    setDraft((current) => ({ ...current, [field]: value }));
  }

  async function copyDraft() {
    await navigator.clipboard.writeText(renderedDraft);
    setCopied(true);
  }

  function clearDraft() {
    setDraft(defaultDraft);
    setCopied(false);
  }

  return (
    <section className="config-page" aria-label="Configuration">
      <div className="panel-heading">
        <div>
          <h2>配置</h2>
          <p>导入加密配置，编辑非敏感连接草稿。</p>
        </div>
        <span className={`state-pill ${profilePresent ? "ok" : "warn"}`}>{profilePresent ? "已导入" : "待导入"}</span>
      </div>

      <div className="config-grid">
        <div className="config-column">
          <LinuxConfigPanel status={status} gatewayApi={gatewayApi} onImported={onImported} />
          <LinuxPackagePanel packageStatus={packageStatus} />
        </div>

        <section className="workbench-panel config-editor" aria-label="Configuration editor">
          <div className="workbench-panel-head">
            <div>
              <h2>
                <FileSliders size={18} />
                配置编辑
              </h2>
              <p>{configPath}</p>
            </div>
          </div>

          <div className="config-form-grid">
            <label>
              <Server size={16} />
              <span>名称</span>
              <input value={draft.label} onChange={(event) => updateDraft("label", event.currentTarget.value)} />
            </label>
            <label>
              <Globe2 size={16} />
              <span>区域</span>
              <input value={draft.region} onChange={(event) => updateDraft("region", event.currentTarget.value)} />
            </label>
            <label className="wide">
              <Network size={16} />
              <span>服务器</span>
              <input value={draft.server} onChange={(event) => updateDraft("server", event.currentTarget.value)} placeholder="主机名或域名" />
            </label>
            <label>
              <Network size={16} />
              <span>HTTP</span>
              <input inputMode="numeric" value={draft.httpPort} onChange={(event) => updateDraft("httpPort", event.currentTarget.value)} />
            </label>
            <label>
              <Network size={16} />
              <span>SOCKS</span>
              <input inputMode="numeric" value={draft.socksPort} onChange={(event) => updateDraft("socksPort", event.currentTarget.value)} />
            </label>
            <label className="wide">
              <FileSliders size={16} />
              <span>备注</span>
              <textarea value={draft.notes} onChange={(event) => updateDraft("notes", event.currentTarget.value)} rows={4} />
            </label>
          </div>

          <pre className="config-draft-preview">{renderedDraft}</pre>

          <div className="config-editor-actions">
            <button className="switch-button safe compact" onClick={() => void copyDraft()}>
              <Clipboard size={18} />
              <span>
                <strong>{copied ? "已复制" : "复制草稿"}</strong>
                <small>非敏感 JSON</small>
              </span>
            </button>
            <button className="switch-button caution compact" onClick={clearDraft}>
              <Eraser size={18} />
              <span>
                <strong>清空草稿</strong>
                <small>恢复默认字段</small>
              </span>
            </button>
          </div>
        </section>
      </div>
    </section>
  );
}
