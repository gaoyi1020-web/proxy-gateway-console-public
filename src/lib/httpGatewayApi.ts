import type { GatewayApi } from "./gatewayApi";
import type {
  ActionDefinition,
  ActionResult,
  LinuxDesktopPackageStatus,
  LinuxProxyUnificationStatus,
  LinuxProfileImportResult,
  NetworkDecision,
  NetworkDecisionResult,
  NetworkEventsResponse,
  StatusResponse
} from "./types";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${path} ${res.status}`);
  }
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    throw new Error(`${path} ${res.status}`);
  }
  return (await res.json()) as T;
}

export const httpGatewayApi: GatewayApi = {
  status: () => getJson<StatusResponse>("/api/status"),
  actions: async () => {
    const response = await getJson<{ actions: ActionDefinition[] }>("/api/actions");
    return response.actions;
  },
  runAction: (actionId: string) => postJson<ActionResult>("/api/actions/run", { actionId }),
  networkEvents: () => getJson<NetworkEventsResponse>("/api/network-events"),
  resolveNetworkEvent: (eventId: string, decision: NetworkDecision) =>
    postJson<NetworkDecisionResult>("/api/network-events/resolve", { eventId, decision }),
  linuxDesktopPackage: () => getJson<LinuxDesktopPackageStatus>("/api/linux/desktop-package"),
  linuxProxyUnification: () => getJson<LinuxProxyUnificationStatus>("/api/linux/proxy-unification"),
  importLinuxProfile: (fileName: string, contentBase64: string) =>
    postJson<LinuxProfileImportResult>("/api/linux/profile/import", { fileName, contentBase64 })
};
