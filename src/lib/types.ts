export type LinkId = "main-download" | "phone-canary" | "app-failover" | "hotspot-split" | "lan-gateway";

export interface LinkDefinition {
  id: LinkId;
  name: string;
  role: string;
  mode: string;
  route: string;
  ports: string[];
  services: string[];
  risk: string;
  benchmark: {
    httpProxy?: string;
    socksProxy?: string;
    dnsProxy?: string;
    pingHost?: string;
  };
}

export interface ProbeResult {
  ok: boolean;
  value: string;
  detail?: string;
}

export interface LinkStatus {
  id: LinkId;
  active: boolean;
  summary: string;
  probes: Record<string, ProbeResult>;
}

export interface StatusResponse {
  generatedAt: string;
  runtimeGeneratedAt?: string;
  links: LinkDefinition[];
  statuses: LinkStatus[];
  environment: {
    httpProxy: string;
    httpsProxy: string;
    allProxy: string;
    defaultRoute: string;
  };
  hotspotPreflight?: HotspotPreflight | null;
  iphoneLanProxy?: IPhoneLanProxyStatus;
  lanGateway?: LanGatewayStatus;
  linuxLifecycle?: LinuxLifecycleStatus;
  gatewayAgent?: GatewayAgentStatus;
  networkEvents: NetworkEventsResponse;
  runtime?: unknown;
}

export interface LinuxLifecycleStatus {
  ok: boolean;
  state: string;
  summary: string;
  contract: {
    stop: "preserve-config" | string;
    uninstall: "purge-project-owned" | string;
  };
  config: {
    path: string;
    present: boolean;
    profilePresent: boolean;
  };
  runtime: {
    path: string;
    present: boolean;
  };
  service: {
    path: string;
    present: boolean;
  };
  wrapper: {
    path: string;
    present: boolean;
  };
  commands: {
    stop: string;
    uninstallDryRun: string;
    uninstallApply: string;
  };
}

export interface GatewayAgentStatus {
  v2: true;
  enabled: boolean;
  ok: boolean;
  state: string;
  summary: string;
  mode: "read-only" | string;
  updatedAt: string;
  probes: Record<string, ProbeResult>;
  errors: string[];
}

export interface IPhoneLanProxyStatus {
  server: string;
  port: number;
  setting: string;
  authentication: boolean;
  target: string;
  allowCidr: string;
  portOpen: boolean;
  firewall: {
    status: string;
    summary: string;
    evidence?: unknown;
    allowCommand?: string;
  };
  recentClients: Array<{
    timestamp: string;
    ip: string;
    port: number;
    local: boolean;
  }>;
  recentUpstreams: Array<{
    timestamp: string;
    method?: string;
    target: string;
    route: string;
  }>;
}

export interface LanGatewayStatus {
  ok: boolean;
  enabled: boolean;
  mode: string;
  server: string;
  interface: string;
  gateway: string;
  cidr: string;
  clientIp: string;
  inferredClientIp: string;
  ipForward: boolean;
  manualIphone: {
    ip: string;
    subnetMask: string;
    router: string;
    dns: string;
  };
  nft: {
    state: string;
    detail: string;
  };
  errors: string[];
  commands: {
    rootApply: string;
    rootRemove: string;
    check: string;
  };
  notes: string[];
}

export interface HotspotPreflight {
  connection: string;
  allowed: boolean;
  risk: string;
  message: string;
  hotspot_interface: string;
  hotspot_mode: string;
  default_route: string;
  default_route_interface: string;
  recommendation: string;
}

export interface BenchmarkMetric {
  linkId: LinkId;
  label: string;
  ok: boolean;
  value: string;
  detail: string;
}

export interface BenchmarkResponse {
  generatedAt: string;
  metrics: BenchmarkMetric[];
}

export interface ActionDefinition {
  id: string;
  label: string;
  description: string;
  risk: "safe" | "caution";
}

export interface ActionResult {
  actionId: string;
  ok: boolean;
  stdout?: string;
  stderr?: string;
  requiresTerminal?: boolean;
  command?: string;
  result?: unknown;
}

export type NetworkDecision =
  | "keep-current"
  | "use-phone-once"
  | "ignore-once"
  | "always-keep-current"
  | "always-use-phone";

export interface NetworkEventChoice {
  id: NetworkDecision;
  label: string;
  policy: string;
}

export interface NetworkEvent {
  id: string;
  type: string;
  status: "pending" | "resolved";
  interface: string;
  connection: string;
  driver: string;
  connection_known?: boolean;
  carrier?: boolean;
  operstate?: string;
  message?: string;
  default_route?: string;
  default_route_interface?: string;
  created_at?: string;
  updated_at?: string;
  observed_count?: number;
  choices?: NetworkEventChoice[];
}

export interface NetworkEventsResponse {
  ok?: boolean;
  generatedAt?: string;
  events: NetworkEvent[];
  pending: NetworkEvent[];
  policy?: Record<string, unknown>;
  stderr?: string;
}

export interface NetworkDecisionResult {
  ok: boolean;
  stdout?: string;
  stderr?: string;
  result?: unknown;
}

export interface LinuxProfileImportResult {
  ok: boolean;
  state: string;
  summary: string;
  profileSource?: {
    mode: string;
    path: string;
  };
}

export interface LinuxDesktopPackageStatus {
  ok: boolean;
  state: "installed" | "missing" | string;
  launcherMode: "release" | "dev" | "missing" | "unknown" | string;
  summary: string;
  installRoot: string;
  launcher: string;
  releaseBinary: string;
  sidecar: string;
  desktopEntry: string;
  desktopCopy?: string;
  icon?: string;
  legacyDesktopEntries?: string[];
  legacyPresent?: string[];
  launcherBackups?: string[];
  checks: Record<string, boolean>;
}

export interface ProxyUnifiedEndpoint {
  host: string;
  port: number;
  open: boolean;
  planned?: boolean;
}

export interface ProxyUnifiedUpstream {
  id: "old" | "new" | string;
  label: string;
  role: string;
  http: ProxyUnifiedEndpoint;
  socks: ProxyUnifiedEndpoint;
  services: string[];
  ready: boolean;
}

export interface ProxyUnifiedAdapter {
  id: string;
  label: string;
  endpoint: ProxyUnifiedEndpoint;
  target: string;
  owner: string;
  ready: boolean;
}

export interface ExternalProxyService {
  name: string;
  port: number;
  status: string;
  projectOwned: false;
  classification: string;
  risk: string;
}

export interface LinuxProxyOptimizationReadiness {
  phase: "observe-only" | "dispatcher-candidate" | "dispatcher-active";
  dispatcherActive: boolean;
  blockers: string[];
  safeNextSteps: string[];
}

export interface LinuxProxyUnificationStatus {
  ok: boolean;
  mode: "read-only" | string;
  generatedAt: string;
  versionCount: number;
  unifiedEntry: {
    currentHttp: ProxyUnifiedEndpoint;
    futureSocks: ProxyUnifiedEndpoint;
  };
  upstreams: ProxyUnifiedUpstream[];
  adapters: ProxyUnifiedAdapter[];
  policy: {
    private: string;
    domestic: string;
    foreign: string;
    preferredForeignUpstream: string;
    fallbackOrder: string[];
  };
  externalServices: ExternalProxyService[];
  optimizationReadiness: LinuxProxyOptimizationReadiness;
  risks: string[];
  recommendedCutoverOrder: string[];
  actions: never[];
}
