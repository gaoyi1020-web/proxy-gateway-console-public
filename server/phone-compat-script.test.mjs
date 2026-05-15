import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const script = readFileSync("scripts/phone-compat/collect-host-evidence.sh", "utf8");

test("phone compatibility host collector is read-only", () => {
  assert.match(script, /ss -ltnp/);
  assert.match(script, /ip neigh show/);
  assert.match(script, /scripts\/cgc network-scan/);
  assert.doesNotMatch(script, /\bsudo\b|nft\s+|iptables|nmcli|systemctl\s+(restart|stop|start|enable|disable)|pkill|kill\s+-9/);
});

test("phone compatibility host collector redacts sensitive strings", () => {
  assert.match(script, /sed -E/);
  assert.match(script, /token|password|authorization|cookie|secret/i);
  assert.match(script, /mac-redacted/);
  assert.match(script, /head -n 120/);
});
