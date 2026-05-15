function portById(runtime, id) {
  return (runtime.ports || []).find((item) => item.id === id) || null;
}

function endpoint(runtime, id, fallbackHost, fallbackPort) {
  const item = portById(runtime, id);
  return {
    host: item?.host || fallbackHost,
    port: Number(item?.port || fallbackPort),
    open: Boolean(item?.open)
  };
}

function upstream(id, label, http, socks, services) {
  return {
    id,
    label,
    role: id === "old" ? "legacy-compatible-upstream" : "canary-preferred-upstream",
    http,
    socks,
    services,
    ready: Boolean(http.open || socks.open)
  };
}

function adapter(id, label, endpointValue, target, owner, ready) {
  return { id, label, endpoint: endpointValue, target, owner, ready: Boolean(ready) };
}

export function classifyExternalProxyServices(items = []) {
  return items.map((item) => {
    const name = item.name || "unknown";
    const command = item.command || "";
    const port = Number(item.port || 0);
    const isAutossh = name.includes("autossh") || command.includes("autossh");
    const isCustomProvider = name.includes("custom-provider") || command.includes("custom-provider-proxy");
    const isContentCreator = name.includes("content-creator") || command.includes("/content-creator/");
    return {
      name,
      port,
      status: item.status || "unknown",
      projectOwned: false,
      classification: isAutossh
        ? "external-socks-tunnel"
        : isCustomProvider
          ? "external-api-proxy"
          : isContentCreator
            ? "external-app-proxy"
            : "external-proxy",
      risk: isAutossh && port === 1080 ? "port overlap with old SOCKS; keep isolated before cutover" : "external to proxy-gateway-console"
    };
  });
}

export function knownExternalProxyServices(statusByName = {}) {
  return [
    { name: "autossh-tunnel.service", port: 1080, status: statusByName["autossh-tunnel.service"] || "unknown" },
    { name: "content-creator-local.service", port: 5202, status: statusByName["content-creator-local.service"] || "unknown" },
    { name: "custom-provider-proxy.py", port: 18792, status: statusByName["custom-provider-proxy.py"] || "unknown" }
  ];
}

export function buildLinuxProxyUnification(runtime = {}, options = {}) {
  const oldHttp = endpoint(runtime, "old-http", "127.0.0.1", 8118);
  const oldSocks = endpoint(runtime, "old-socks", "127.0.0.1", 1080);
  const newHttp = endpoint(runtime, "new-http", "127.0.0.1", 18122);
  const newSocks = endpoint(runtime, "new-socks", "127.0.0.1", 11880);
  const failover = endpoint(runtime, "failover", "127.0.0.1", 18180);
  const iphone = endpoint(runtime, "iphone-lan", runtime.iphone_lan_proxy?.server || "LAN", 18181);
  const splitDns = endpoint(runtime, "split-dns", "0.0.0.0", 1053);
  const splitTcp = endpoint(runtime, "split-tcp", "0.0.0.0", 12345);

  return {
    ok: true,
    mode: "read-only",
    generatedAt: runtime.generated_at || new Date().toISOString(),
    versionCount: 2,
    unifiedEntry: {
      currentHttp: failover,
      futureSocks: { host: "127.0.0.1", port: 18182, open: false, planned: true }
    },
    upstreams: [
      upstream("old", "旧代理", oldHttp, oldSocks, ["shadowsocks-libev.service", "privoxy.service"]),
      upstream("new", "新代理", newHttp, newSocks, ["secondary-proxy-client.service", "secondary-http-proxy.service"])
    ],
    adapters: [
      adapter("local-failover", "本机统一 HTTP", failover, "old/new upstream pool", "proxy-gateway", failover.open),
      adapter("iphone-lan", "手机 LAN", iphone, "CN/private direct, foreign -> new", "proxy-gateway", iphone.open),
      adapter("hotspot-dns", "热点 DNS", splitDns, "split decision -> failover", "proxy-gateway", splitDns.open),
      adapter("hotspot-tcp", "热点 TCP", splitTcp, "transparent TCP -> failover", "proxy-gateway", splitTcp.open),
      adapter(
        "lan-gateway",
        "LAN 网关",
        { host: runtime.lan_gateway?.server || "", port: 0, open: Boolean(runtime.lan_gateway?.enabled) },
        "single selected client",
        "proxy-gateway-root-gated",
        runtime.lan_gateway?.enabled
      )
    ],
    policy: {
      private: "direct",
      domestic: "direct",
      foreign: "proxy",
      preferredForeignUpstream: "new",
      fallbackOrder: ["new", "old"]
    },
    externalServices: classifyExternalProxyServices(options.externalServices || []),
    optimizationReadiness: {
      phase: "observe-only",
      dispatcherActive: false,
      blockers: [
        "read-only-unification",
        "profile-missing-or-unverified",
        "phone-compat-unverified",
        "root-gated-lan-hotspot"
      ],
      safeNextSteps: [
        "add deterministic network smoke",
        "verify real encrypted profile import",
        "build phone compatibility matrix",
        "promote unified HTTP dispatcher after read-only checks pass"
      ]
    },
    risks: [
      "read-only model only; no service cutover in v5 phase 1",
      "autossh-tunnel may overlap old SOCKS design on port 1080 and must stay classified as external",
      "hotspot and LAN gateway remain root-gated"
    ],
    recommendedCutoverOrder: ["observe-only", "local app unified HTTP", "iphone LAN adapter", "hotspot split adapters", "LAN gateway"],
    actions: []
  };
}
