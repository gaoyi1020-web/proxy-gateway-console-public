import test from "node:test";
import assert from "node:assert/strict";
import {
  buildLinuxProxyUnification,
  classifyExternalProxyServices,
  knownExternalProxyServices
} from "./linux-proxy-unification.js";

const runtime = {
  generated_at: "2026-05-07 23:55:31 +0800",
  topology: [
    { name: "Old route", path: "1080 SOCKS -> 8118 HTTP", role: "primary upstream" },
    { name: "New route", path: "11880 SOCKS -> 18122 HTTP", role: "failover upstream" },
    { name: "Failover", path: "18180 HTTP -> old first, new on failure", role: "foreign traffic bridge" },
    { name: "Hotspot split", path: "10.42.0.0/16 DNS:1053 TCP:12345", role: "domestic direct, foreign proxy" }
  ],
  services: [
    { name: "secondary-proxy-client.service", scope: "user", state: "active", ports: [11880], enabled: "enabled" },
    { name: "secondary-http-proxy.service", scope: "user", state: "active", ports: [18122], enabled: "enabled" },
    { name: "proxy-failover.service", scope: "user", state: "active", ports: [18180], enabled: "enabled" },
    { name: "iphone-lan-proxy.service", scope: "user", state: "active", ports: [18181], enabled: "enabled" },
    { name: "hotspot-split-dns.service", scope: "user", state: "active", ports: [1053], enabled: "enabled" },
    { name: "hotspot-split-proxy.service", scope: "user", state: "active", ports: [12345], enabled: "enabled" },
    { name: "shadowsocks-libev.service", scope: "system", state: "active", ports: [8388], enabled: "enabled" },
    { name: "privoxy.service", scope: "system", state: "active", ports: [8118], enabled: "disabled" }
  ],
  ports: [
    { id: "old-socks", label: "Old SOCKS", host: "127.0.0.1", port: 1080, open: true },
    { id: "old-http", label: "Old HTTP", host: "127.0.0.1", port: 8118, open: true },
    { id: "new-socks", label: "New SOCKS", host: "127.0.0.1", port: 11880, open: true },
    { id: "new-http", label: "New HTTP", host: "127.0.0.1", port: 18122, open: true },
    { id: "failover", label: "Failover HTTP", host: "127.0.0.1", port: 18180, open: true },
    { id: "iphone-lan", label: "iPhone LAN HTTP", host: "LAN", port: 18181, open: true },
    { id: "split-dns", label: "Split DNS", host: "127.0.0.1", port: 1053, open: true },
    { id: "split-tcp", label: "Split TCP", host: "127.0.0.1", port: 12345, open: true }
  ],
  iphone_lan_proxy: { server: "10.10.0.10", setting: "10.10.0.10:18181", port_open: true },
  lan_gateway: { enabled: true, server: "10.10.0.10", client_ip: "10.10.0.25" }
};

test("buildLinuxProxyUnification maps old and new upstream pools", () => {
  const result = buildLinuxProxyUnification(runtime, { externalServices: [] });

  assert.equal(result.ok, true);
  assert.equal(result.mode, "read-only");
  assert.equal(result.upstreams.length, 2);
  assert.deepEqual(result.upstreams.map((item) => item.id), ["old", "new"]);
  assert.equal(result.upstreams[0].http.port, 8118);
  assert.equal(result.upstreams[0].socks.port, 1080);
  assert.equal(result.upstreams[1].http.port, 18122);
  assert.equal(result.upstreams[1].socks.port, 11880);
});

test("buildLinuxProxyUnification maps project adapters without destructive commands", () => {
  const result = buildLinuxProxyUnification(runtime, { externalServices: [] });

  assert.deepEqual(result.adapters.map((item) => item.id), [
    "local-failover",
    "iphone-lan",
    "hotspot-dns",
    "hotspot-tcp",
    "lan-gateway"
  ]);
  assert.equal(result.policy.domestic, "direct");
  assert.equal(result.policy.private, "direct");
  assert.equal(result.policy.foreign, "proxy");
  assert.equal(result.actions.length, 0);
  assert.doesNotMatch(JSON.stringify(result), /systemctl|nft|nmcli|root-apply|restart/);
});

test("buildLinuxProxyUnification exposes optimization readiness without service cutover", () => {
  const status = buildLinuxProxyUnification(runtime, { externalServices: [] });

  assert.equal(status.mode, "read-only");
  assert.equal(status.optimizationReadiness.phase, "observe-only");
  assert.equal(status.optimizationReadiness.dispatcherActive, false);
  assert.ok(status.optimizationReadiness.blockers.includes("read-only-unification"));
  assert.ok(status.optimizationReadiness.blockers.includes("profile-missing-or-unverified"));
  assert.ok(status.optimizationReadiness.blockers.includes("phone-compat-unverified"));
  assert.deepEqual(status.optimizationReadiness.safeNextSteps, [
    "add deterministic network smoke",
    "verify real encrypted profile import",
    "build phone compatibility matrix",
    "promote unified HTTP dispatcher after read-only checks pass"
  ]);
});

test("classifyExternalProxyServices keeps non-project proxies out of the project version count", () => {
  const external = classifyExternalProxyServices([
    { name: "autossh-tunnel.service", command: "autossh -D 1080 miyao", port: 1080, status: "retrying" },
    { name: "content-creator-local.service", command: "python3 app.py", port: 5202, status: "active" },
    { name: "custom-provider-proxy.py", command: "python3 ~/bin/custom-provider-proxy.py", port: 18792, status: "active" }
  ]);

  assert.equal(external.length, 3);
  assert.equal(external[0].projectOwned, false);
  assert.match(external[0].risk, /port overlap/i);
  assert.equal(external[1].classification, "external-app-proxy");
  assert.equal(external[2].classification, "external-api-proxy");
});

test("knownExternalProxyServices returns redacted local external proxy inventory", () => {
  const external = knownExternalProxyServices({
    "autossh-tunnel.service": "retrying",
    "content-creator-local.service": "active",
    "custom-provider-proxy.py": "active"
  });

  assert.deepEqual(external.map((item) => item.name), [
    "autossh-tunnel.service",
    "content-creator-local.service",
    "custom-provider-proxy.py"
  ]);
  assert.equal(external[0].port, 1080);
  assert.equal(external[1].port, 5202);
  assert.equal(external[2].port, 18792);
  assert.doesNotMatch(JSON.stringify(external), /-k|password|secret|Vl4tr/);
});
