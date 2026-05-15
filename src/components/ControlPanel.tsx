import type { GatewayApi } from "../lib/gatewayApi";
import type { LinuxDesktopPackageStatus, LinuxProxyUnificationStatus, StatusResponse } from "../lib/types";
import OperationsPage from "./OperationsPage";

export default function ControlPanel({
  status,
  packageStatus,
  proxyUnification,
  gatewayApi,
  loading,
  onActionComplete,
  onOpenConfig
}: {
  status: StatusResponse | null;
  packageStatus: LinuxDesktopPackageStatus | null;
  proxyUnification: LinuxProxyUnificationStatus | null;
  gatewayApi: GatewayApi;
  loading: boolean;
  onActionComplete: () => void;
  onOpenConfig?: () => void;
}) {
  return (
    <section className="control-panel" aria-label="Proxy controls">
      <OperationsPage
        status={status}
        packageStatus={packageStatus}
        proxyUnification={proxyUnification}
        gatewayApi={gatewayApi}
        loading={loading}
        onActionComplete={onActionComplete}
        onActionEvent={() => undefined}
        onOpenConfig={onOpenConfig || (() => undefined)}
      />
    </section>
  );
}
