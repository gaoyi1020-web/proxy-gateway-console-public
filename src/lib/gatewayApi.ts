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
import { detectSurface, type RuntimeSurface } from "./surface";

export type { RuntimeSurface } from "./surface";

export interface GatewayApi {
  status(): Promise<StatusResponse>;
  actions(): Promise<ActionDefinition[]>;
  runAction(actionId: string): Promise<ActionResult>;
  networkEvents(): Promise<NetworkEventsResponse>;
  resolveNetworkEvent(eventId: string, decision: NetworkDecision): Promise<NetworkDecisionResult>;
  linuxDesktopPackage(): Promise<LinuxDesktopPackageStatus>;
  linuxProxyUnification(): Promise<LinuxProxyUnificationStatus>;
  importLinuxProfile(fileName: string, contentBase64: string): Promise<LinuxProfileImportResult>;
}

export function runtimeSurface(): RuntimeSurface {
  const maybeWindow = window as unknown as { __TAURI_INTERNALS__?: unknown };
  return {
    ...detectSurface({
      hasTauri: Boolean(maybeWindow.__TAURI_INTERNALS__),
      userAgent: window.navigator.userAgent
    })
  };
}
