import { useCallback, useEffect, useState } from "react";
import DesktopAgentPanel from "./components/DesktopAgentPanel";
import DesktopMacVpnPanel from "./components/DesktopMacVpnPanel";
import DesktopProxyPanel from "./components/DesktopProxyPanel";
import LinuxConfigPage from "./components/LinuxConfigPage";
import LogsPage from "./components/LogsPage";
import NetworkDecisionPrompt from "./components/NetworkDecisionPrompt";
import OperationsPage from "./components/OperationsPage";
import StatusPage from "./components/StatusPage";
import WebWorkbenchLayout from "./components/WebWorkbenchLayout";
import type { WebWorkbenchView, WorkbenchActionLogEntry, WorkbenchApiErrorEntry } from "./components/webWorkbenchTypes";
import { desktopGatewayApi } from "./lib/desktopGatewayApi";
import { runtimeSurface } from "./lib/gatewayApi";
import { httpGatewayApi } from "./lib/httpGatewayApi";
import { desktopPanels } from "./lib/surface";
import type { LinuxDesktopPackageStatus, LinuxProxyUnificationStatus, NetworkDecision, NetworkEventsResponse, StatusResponse } from "./lib/types";

const gatewayApi = runtimeSurface().desktop ? desktopGatewayApi : httpGatewayApi;

export default function App() {
  const surface = runtimeSurface();
  const panels = desktopPanels(surface);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [packageStatus, setPackageStatus] = useState<LinuxDesktopPackageStatus | null>(null);
  const [proxyUnification, setProxyUnification] = useState<LinuxProxyUnificationStatus | null>(null);
  const [networkEvents, setNetworkEvents] = useState<NetworkEventsResponse | null>(null);
  const [view, setView] = useState<WebWorkbenchView>("operations");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLog, setActionLog] = useState<WorkbenchActionLogEntry[]>([]);
  const [apiErrorLog, setApiErrorLog] = useState<WorkbenchApiErrorEntry[]>([]);

  const recordApiError = useCallback((scope: string, err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    setApiErrorLog((items) => [
      {
        id: `${Date.now()}-${scope}`,
        at: new Date().toISOString(),
        scope,
        message
      },
      ...items
    ].slice(0, 20));
    return message;
  }, []);

  const recordAction = useCallback((entry: WorkbenchActionLogEntry) => {
    setActionLog((items) => [entry, ...items].slice(0, 20));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [next, nextPackage, nextProxyUnification] = await Promise.all([
        gatewayApi.status(),
        gatewayApi.linuxDesktopPackage().catch(() => null),
        gatewayApi.linuxProxyUnification().catch(() => null)
      ]);
      setStatus(next);
      setPackageStatus(nextPackage);
      setProxyUnification(nextProxyUnification);
      setNetworkEvents(next.networkEvents);
    } catch (err) {
      setError(recordApiError("status", err));
    } finally {
      setLoading(false);
    }
  }, [recordApiError]);

  const refreshNetworkEvents = useCallback(async () => {
    try {
      setNetworkEvents(await gatewayApi.networkEvents());
    } catch (err) {
      setError(recordApiError("network-events", err));
    }
  }, [recordApiError]);

  const handleNetworkDecision = useCallback(async (eventId: string, decision: NetworkDecision) => {
    try {
      const result = await gatewayApi.resolveNetworkEvent(eventId, decision);
      await refreshNetworkEvents();
      void refresh();
      return result;
    } catch (err) {
      setError(recordApiError("network-decision", err));
      throw err;
    }
  }, [refresh, refreshNetworkEvents, recordApiError]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 20_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    void refreshNetworkEvents();
    const timer = window.setInterval(() => void refreshNetworkEvents(), 4_000);
    return () => window.clearInterval(timer);
  }, [refreshNetworkEvents]);

  function renderPage() {
    if (view === "operations") {
      return (
        <OperationsPage
          status={status}
          packageStatus={packageStatus}
          proxyUnification={proxyUnification}
          gatewayApi={gatewayApi}
          loading={loading}
          onActionComplete={refresh}
          onActionEvent={recordAction}
          onOpenConfig={() => setView("config")}
        />
      );
    }
    if (view === "config") {
      return (
        <LinuxConfigPage
          status={status}
          packageStatus={packageStatus}
          gatewayApi={gatewayApi}
          onImported={refresh}
        />
      );
    }
    if (view === "status") {
      return (
        <StatusPage
          status={status}
          packageStatus={packageStatus}
          proxyUnification={proxyUnification}
        />
      );
    }
    return (
      <LogsPage
        status={status}
        networkEvents={networkEvents}
        actionLog={actionLog}
        apiErrorLog={apiErrorLog}
      />
    );
  }

  return (
    <WebWorkbenchLayout
      activeView={view}
      onViewChange={setView}
      status={status}
      networkEvents={networkEvents}
      loading={loading}
      error={error}
      onRefresh={() => void refresh()}
    >
      {renderPage()}

      {panels.length ? (
        <details className="advanced-desktop-tools">
          <summary>高级桌面工具</summary>
          <section className="desktop-grid" aria-label="Desktop controls">
            {panels.includes("agent") ? <DesktopAgentPanel onActionComplete={refresh} /> : null}
            {panels.includes("proxy") ? <DesktopProxyPanel /> : null}
            {panels.includes("mac") ? <DesktopMacVpnPanel onActionComplete={refresh} /> : null}
          </section>
        </details>
      ) : null}

      <NetworkDecisionPrompt events={networkEvents?.pending ?? []} onDecision={handleNetworkDecision} />
    </WebWorkbenchLayout>
  );
}
