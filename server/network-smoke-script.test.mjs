import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const py = readFileSync("scripts/network/network_smoke.py", "utf8");
const sh = readFileSync("scripts/network/network-smoke.sh", "utf8");

test("network smoke probe separates naked and explicit proxy routes", () => {
  assert.match(py, /ProxyHandler\(\{\}\)/);
  assert.match(py, /127\.0\.0\.1:18180/);
  assert.match(py, /PROXY_GATEWAY_LAN_PROXY_URL/);
  assert.match(py, /https:\/\/chatgpt\.com\/cdn-cgi\/trace/);
  assert.match(py, /https:\/\/www\.google\.com\/generate_204/);
  assert.doesNotMatch(py, /os\.environ\[['"]HTTP_PROXY['"]\]/);
  assert.doesNotMatch(py, /192\.168\.10\./);
});

test("network smoke wrapper is a thin python entrypoint", () => {
  assert.match(sh, /python3 "\$\{SCRIPT_DIR\}\/network_smoke\.py"/);
  assert.doesNotMatch(sh, /sudo|nft|nmcli|systemctl restart|hotspot-safe-start/);
});
