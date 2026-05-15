import { invoke } from "@tauri-apps/api/core";
import { buildDesktopStatus, type CommandResult } from "./desktopStatus";
import type { GatewayApi } from "./gatewayApi";
import { httpGatewayApi } from "./httpGatewayApi";
import type {
  ActionDefinition,
  ActionResult,
  LinuxDesktopPackageStatus,
  LinuxProfileImportResult,
  NetworkDecision,
  NetworkDecisionResult,
  NetworkEventsResponse,
  StatusResponse
} from "./types";

const desktopActions: ActionDefinition[] = [
  {
    id: "self-check",
    label: "自检",
    description: "通过桌面 sidecar 检查本机状态、配置来源和运行态。",
    risk: "safe"
  },
  {
    id: "gateway-agent-start",
    label: "启动桌面会话",
    description: "创建桌面端本机会话，不修改 root 网络规则。",
    risk: "safe"
  },
  {
    id: "linux-v3-stop",
    label: "停止本机控制层",
    description: "通过桌面 sidecar 停止会话和运行态，保留配置。",
    risk: "safe"
  },
  {
    id: "linux-v3-uninstall-plan",
    label: "生成卸载命令",
    description: "只生成终端确认命令，不在桌面端直接删除配置。",
    risk: "caution"
  }
];

function commandToActionResult(actionId: string, result: CommandResult): ActionResult {
  let parsed: Record<string, unknown> | null = null;
  try {
    parsed = result.stdout ? JSON.parse(result.stdout) as Record<string, unknown> : null;
  } catch {
    parsed = null;
  }
  const parsedOk = typeof parsed?.ok === "boolean" ? parsed.ok : undefined;
  return {
    actionId,
    ok: parsedOk ?? result.ok,
    stdout: result.stdout,
    stderr: result.stderr || String(parsed?.summary || ""),
    result: parsed
  };
}

async function runDesktopAction(actionId: string): Promise<ActionResult> {
  if (actionId === "self-check") {
    return commandToActionResult(actionId, await invoke<CommandResult>("agent_self_check"));
  }
  if (actionId === "gateway-agent-start") {
    return commandToActionResult(
      actionId,
      await invoke<CommandResult>("agent_start", { lanHost: "127.0.0.1" })
    );
  }
  if (actionId === "linux-v3-stop") {
    return commandToActionResult(actionId, await invoke<CommandResult>("agent_stop"));
  }
  if (actionId === "linux-v3-uninstall-plan") {
    const result = await invoke<CommandResult>("agent_uninstall_plan");
    const actionResult = commandToActionResult(actionId, result);
    const parsed = actionResult.result as { commands?: { uninstallApply?: string } } | null;
    return {
      ...actionResult,
      ok: false,
      requiresTerminal: true,
      command: parsed?.commands?.uninstallApply || "~/.local/bin/gateway-agent uninstall --apply",
      stderr: actionResult.stderr || "本机控制层卸载必须在终端确认。"
    };
  }
  return {
    actionId,
    ok: false,
    stdout: "",
    stderr: "This action is not available in the installed desktop client."
  };
}

export const desktopGatewayApi: GatewayApi = {
  async status(): Promise<StatusResponse> {
    const base = await httpGatewayApi.status().catch(() => null);
    try {
      return buildDesktopStatus({
        baseStatus: base,
        commandResult: await invoke<CommandResult>("agent_status")
      });
    } catch (error) {
      return buildDesktopStatus({
        baseStatus: base,
        commandError: error
      });
    }
  },
  actions: async () => desktopActions,
  runAction: runDesktopAction,
  async networkEvents(): Promise<NetworkEventsResponse> {
    return { events: [], pending: [] };
  },
  async resolveNetworkEvent(_eventId: string, _decision: NetworkDecision): Promise<NetworkDecisionResult> {
    return { ok: false, stderr: "network event selection is Linux-host only in the desktop test app" };
  },
  linuxDesktopPackage: () => invoke<LinuxDesktopPackageStatus>("linux_desktop_package_status"),
  linuxProxyUnification: () => httpGatewayApi.linuxProxyUnification(),
  importLinuxProfile: (fileName: string, contentBase64: string) =>
    invoke<LinuxProfileImportResult>("agent_profile_import", { fileName, contentBase64 })
};
