import type { StatusResponse } from "./types";

export interface CommandResult {
  ok: boolean;
  stdout: string;
  stderr: string;
}

interface DesktopAgentStatus {
  ok?: boolean;
  enabled?: boolean;
  state?: string;
  summary?: string;
  generatedAt?: string;
  runtimeDir?: string;
  sessionPath?: string;
  session?: Record<string, unknown> | null;
  usb?: Record<string, unknown>;
  profileSource?: Record<string, unknown>;
  unlock?: Record<string, unknown>;
  privateRuntime?: Record<string, unknown>;
  phoneSetup?: Record<string, unknown>;
  probes?: Record<string, { ok?: boolean; value?: string; detail?: string }>;
}

interface BuildDesktopStatusInput {
  baseStatus: StatusResponse | null;
  commandResult?: CommandResult | null;
  commandError?: unknown;
  generatedAt?: string;
}

const fallbackBase: StatusResponse = {
  generatedAt: "",
  links: [],
  statuses: [],
  environment: {
    httpProxy: "",
    httpsProxy: "",
    allProxy: "",
    defaultRoute: ""
  },
  networkEvents: {
    events: [],
    pending: []
  }
};

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function parseCommandJson<T>(result: CommandResult, fallback: T): T {
  if (!result.ok && !result.stdout) {
    return fallback;
  }
  try {
    return JSON.parse(result.stdout) as T;
  } catch {
    return fallback;
  }
}

function stringValue(source: Record<string, unknown> | undefined, key: string, fallback = "") {
  const value = source?.[key];
  return typeof value === "string" ? value : fallback;
}

function boolProbe(ok: boolean, value: string, detail: string) {
  return { ok, value, detail };
}

function desktopAgentProbes(status: DesktopAgentStatus) {
  const session = status.session || null;
  const usb = status.usb || {};
  const profileSource = status.profileSource || {};
  const unlock = status.unlock || {};
  const privateRuntime = status.privateRuntime || {};
  const phoneSetup = status.phoneSetup || {};
  const sourceProbes = status.probes && typeof status.probes === "object" ? status.probes : {};

  return {
    ...sourceProbes,
    runtimeDir: boolProbe(Boolean(status.runtimeDir), status.runtimeDir || "missing", "local runtime path"),
    session: boolProbe(Boolean(session), session ? "present" : "missing", status.sessionPath || ""),
    profileSource: boolProbe(
      Boolean(profileSource.present),
      stringValue(profileSource, "state", "missing"),
      stringValue(profileSource, "mode", "local")
    ),
    usb: boolProbe(
      Boolean(usb.present && usb.trusted),
      stringValue(usb, "state", "not_implemented"),
      "optional recovery media"
    ),
    unlock: boolProbe(
      unlock.state === "unlocked",
      stringValue(unlock, "state", "locked"),
      stringValue(unlock, "bind", "127.0.0.1")
    ),
    privateRuntime: boolProbe(
      Boolean(privateRuntime.state),
      stringValue(privateRuntime, "state", "unknown"),
      stringValue(privateRuntime, "logs")
    ),
    lanExposure: boolProbe(
      Boolean(phoneSetup.enabled),
      stringValue(phoneSetup, "state", "lan_listener_off"),
      stringValue(phoneSetup, "summary")
    )
  };
}

export function buildDesktopStatus({
  baseStatus,
  commandResult,
  commandError,
  generatedAt = new Date().toISOString()
}: BuildDesktopStatusInput): StatusResponse {
  const base = baseStatus ?? fallbackBase;
  const sidecarError = commandError ? errorMessage(commandError) : "";
  const gatewayAgent = commandResult
    ? parseCommandJson<DesktopAgentStatus>(commandResult, {
        ok: commandResult.ok,
        enabled: true,
        state: "unknown",
        summary: commandResult.stderr || "desktop gateway-agent returned non-JSON output",
        generatedAt
      })
    : {
        ok: false,
        enabled: false,
        state: "sidecar_unavailable",
        summary: sidecarError
          ? `desktop gateway-agent unavailable: ${sidecarError}`
          : "desktop gateway-agent unavailable",
        generatedAt
      };

  return {
    ...base,
    generatedAt,
    gatewayAgent: {
      v2: true,
      enabled: Boolean(gatewayAgent.enabled),
      ok: Boolean(gatewayAgent.ok),
      state: String(gatewayAgent.state || "unknown"),
      summary: String(gatewayAgent.summary || ""),
      mode: "desktop",
      updatedAt: String(gatewayAgent.generatedAt || ""),
      probes: desktopAgentProbes(gatewayAgent),
      errors: sidecarError ? [sidecarError] : commandResult?.stderr ? [commandResult.stderr] : []
    }
  };
}
