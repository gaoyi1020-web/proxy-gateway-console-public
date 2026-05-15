export type WebWorkbenchView = "operations" | "config" | "status" | "logs";

export interface WorkbenchActionLogEntry {
  id: string;
  at: string;
  actionId: string;
  label: string;
  ok: boolean;
  message: string;
}

export interface WorkbenchApiErrorEntry {
  id: string;
  at: string;
  scope: string;
  message: string;
}
