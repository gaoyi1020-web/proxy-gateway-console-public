import { Gauge, Loader2, Play } from "lucide-react";
import { useState } from "react";
import type { BenchmarkResponse } from "../lib/types";

async function runBenchmark() {
  const res = await fetch("/api/benchmark", { method: "POST" });
  if (!res.ok) {
    throw new Error(`benchmark ${res.status}`);
  }
  return (await res.json()) as BenchmarkResponse;
}

export default function Benchmark() {
  const [result, setResult] = useState<BenchmarkResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleRun() {
    setBusy(true);
    setError("");
    try {
      setResult(await runBenchmark());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2><Gauge size={18} /> Benchmark</h2>
          <p>DNS split, failover route, and old proxy route checks.</p>
        </div>
        <button className="icon-button" onClick={() => void handleRun()} disabled={busy}>
          {busy ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
          <span>{busy ? "Running" : "Run"}</span>
        </button>
      </div>

      {error ? <div className="banner danger">{error}</div> : null}

      <div className="metric-table">
        <div className="metric-head">
          <span>Link</span>
          <span>Metric</span>
          <span>Value</span>
          <span>Detail</span>
        </div>
        {result?.metrics.map((metric, index) => (
          <div className="metric-row" key={`${metric.linkId}-${metric.label}-${index}`}>
            <span>{metric.linkId}</span>
            <span>{metric.label}</span>
            <strong className={metric.ok ? "text-ok" : "text-warn"}>{metric.value}</strong>
            <span>{metric.detail}</span>
          </div>
        )) ?? <div className="empty-row">No benchmark run yet</div>}
      </div>
    </section>
  );
}
