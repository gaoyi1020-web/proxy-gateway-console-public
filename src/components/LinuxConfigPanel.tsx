import { FileLock2, Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import type { GatewayApi } from "../lib/gatewayApi";
import type { LinuxProfileImportResult, StatusResponse } from "../lib/types";

async function fileToBase64(file: File) {
  const buffer = await file.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

export default function LinuxConfigPanel({
  status,
  gatewayApi,
  onImported
}: {
  status: StatusResponse | null;
  gatewayApi: GatewayApi;
  onImported: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<LinuxProfileImportResult | null>(null);
  const [error, setError] = useState("");
  const profilePresent = Boolean(status?.linuxLifecycle?.config.profilePresent);

  async function importSelected(file: File | undefined) {
    if (!file) {
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const next = await gatewayApi.importLinuxProfile(file.name, await fileToBase64(file));
      setResult(next);
      if (next.ok) {
        onImported();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="linux-v4-panel" aria-label="Linux config import">
      <div className="linux-v4-panel-head">
        <FileLock2 size={20} />
        <span>
          <strong>导入加密配置</strong>
          <small>{profilePresent ? "profile.json.enc 已导入" : "选择加密配置文件"}</small>
        </span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".enc,.json.enc,application/json"
        onChange={(event) => void importSelected(event.currentTarget.files?.[0])}
      />
      <button className="switch-button safe" onClick={() => inputRef.current?.click()} disabled={busy}>
        {busy ? <Loader2 className="spin" size={18} /> : <Upload size={18} />}
        <span>
          <strong>导入 profile.json.enc</strong>
          <small>仅复制加密配置，不解密显示内容</small>
        </span>
      </button>
      {result ? <div className={`inline-result ${result.ok ? "ok" : "warn"}`}>{result.summary || result.state}</div> : null}
      {error ? <div className="inline-result danger">{error}</div> : null}
    </section>
  );
}
