# Proxy Gateway Configuration Layer Contract

Status: frozen contract v1, 2026-05-04.

This document fixes the configuration boundary for the self-use Proxy Gateway system. Programs, installers, and UI code should depend on this contract instead of embedding one server, one region, or one credential set.

## Principle

The product is split into three layers:

```text
program package = app, engine, installers, rootctl, self-checks
configuration package = encrypted profiles, route policy, server identities
runtime state = generated on each device
```

The program package must be reusable when servers, regions, ports, or credentials change.

## What Belongs In The Program Package

Allowed:

- `Proxy Gateway Desktop.app`
- `ProxyGatewayMacVPN` kit scripts
- `sing-box` binary and templates
- install, uninstall, repair, and self-check scripts
- non-secret profile templates
- schema/validation code
- docs explaining how to import a profile

Not allowed:

- real upstream server hostnames or IPs
- real server ports when they identify private infrastructure
- passwords, tokens, UUIDs, private keys, auth strings, cookies, or API keys
- generated `sing-box.json`
- runtime logs or state snapshots
- `upstream.json` copied from a real machine

## Primary Profile Unit

The long-term configuration unit is:

```text
profile.json.enc
```

It is an encrypted envelope created by `agent/profile_crypto.py`:

```json
{
  "product": "PROXY_GATEWAY_PROFILE",
  "version": 1,
  "algorithm": "AES-256-GCM",
  "kdf": "PBKDF2-HMAC-SHA256",
  "iterations": 390000,
  "salt": "...",
  "nonce": "...",
  "ciphertext": "..."
}
```

The decrypted payload must validate as profile schema version `2`.

## Decrypted Profile Shape

Canonical non-secret shape:

```json
{
  "version": 2,
  "name": "personal-gateway",
  "routes": {
    "us": {
      "type": "socks",
      "endpoint": "socks5://127.0.0.1:11880",
      "authRef": "keychain:us"
    },
    "jp": {
      "type": "socks",
      "endpoint": "socks5://127.0.0.1:12880",
      "authRef": "keychain:jp"
    },
    "failover": {
      "type": "failover",
      "order": ["us", "jp"]
    },
    "lanProxy": {
      "type": "lanProxy",
      "bind": "dynamic",
      "policy": "cn-private-direct-foreign-proxy"
    }
  },
  "splitRules": {
    "policy": "cn-private-direct-foreign-proxy",
    "domestic": "direct",
    "private": "direct",
    "foreign": "failover"
  },
  "privacy": {
    "logs": "redacted",
    "state": "local-private"
  },
  "ui": {
    "defaultRegion": "us",
    "regions": [
      {"id": "us", "label": "US"},
      {"id": "jp", "label": "JP"}
    ]
  }
}
```

Rules:

- `version` must be `2`.
- `routes` must be non-empty.
- `splitRules.foreign` must point to a route id or `direct`.
- `lanProxy` is the same-LAN phone/iPad route surface.
- `ui.regions` is display metadata only; route ids remain authoritative.
- inline secret fields such as `password`, `token`, `auth`, `credential`, `uuid`, and `secret` are forbidden in the decrypted profile.
- secret material is resolved through `authRef` or imported into the platform's private store.

## Mac Adapter

The current Mac VPN kit uses:

```text
~/ProxyGatewayMacVPN/config/upstream.json
```

This is an adapter file for `sing-box`, not the cross-platform source of truth.

Mac packaging rule:

- the self-use installer may create an empty `config/` directory;
- it may include `upstream.template.json`;
- it must not include a real `upstream.json`;
- first-run import converts or copies a chosen profile into the Mac private config path;
- `macvpnctl.sh render-config` generates `config/sing-box.json` from private local config only.

Mac private paths:

```text
~/ProxyGatewayMacVPN/config/profile.json.enc
~/ProxyGatewayMacVPN/config/upstream.json
~/ProxyGatewayMacVPN/config/sing-box.json
~/ProxyGatewayMacVPN/logs/
~/ProxyGatewayMacVPN/state/
```

Only `profile.json.enc` may be exported for backup or migration. Generated `sing-box.json`, logs, and state are local runtime artifacts.

## Region Switching

Region switching means selecting a route id from the imported profile.

Examples:

```text
us -> US egress
jp -> JP egress
sg -> Singapore egress
eu -> Europe egress
failover -> configured failover order
```

The UI must show route ids or labels from the profile. It must not infer the region from local code.

After a region switch, the self-check must verify:

- profile schema;
- selected route exists;
- generated engine config validates;
- IPv4 egress;
- IPv6 bypass state;
- DNS behavior;
- at least one target connectivity probe.

## Install Package Contract

The self-use macOS package should accept one of these inputs:

```text
profile.json.enc
upstream.json
none
```

Behavior:

- `profile.json.enc`: copy to private config path with mode `600`, then unlock/import through the configured passphrase path.
- `upstream.json`: copy to private Mac adapter path with mode `600`, render `sing-box.json`, and mark the profile source as `mac-adapter`.
- `upstream.json -> profile.json.enc`: convert adapter metadata into a
  portable encrypted v2 profile using `gateway-agent profile-from-upstream`.
  The converted profile stores route ids, region labels, split policy, and
  `authRef` references only. Raw adapter fields such as server, port, method,
  and password remain outside the decrypted profile until a platform secret
  store/renderer is implemented.
- `none`: install program only and show `profile missing` until the user imports a config.

The installer must never auto-start the root VPN when the profile is missing or invalid.

## Self-Check Contract

Configuration checks should report:

```text
profile-source: missing | encrypted | mac-adapter
profile-schema: pass | warn | fail
selected-route: <route-id> | missing
secret-scan: pass | fail
rendered-config: present | missing | invalid
egress: pass | warn | fail
```

Warnings are acceptable for a freshly installed program-only package. Failures block start.

## Migration Rule

Changing servers or regions must not require changing app code.

Allowed migration:

```text
replace profile.json.enc
unlock/import
render config
run self-check
restart VPN if explicitly requested
```

Not allowed:

```text
edit app source
rebuild app for a new endpoint
embed credentials in installer
copy runtime logs into package
```

## Current Freeze Boundary

Frozen now:

- profile envelope format from `agent/profile_crypto.py`;
- decrypted profile `version=2` as the shared semantic model;
- no inline secret fields in profile payloads;
- Mac `upstream.json` is an adapter, not the source of truth;
- program packages do not include real profile data;
- configuration import is explicit.

Adapter conversion command:

```bash
~/.local/bin/gateway-agent profile-from-upstream \
  --from /path/to/upstream.json \
  --profile-output /path/to/profile.json.enc \
  --passphrase-file /path/to/passphrase.txt
```

The command output must remain sanitized. It may report `state=converted`,
route count, split policy, and digest metadata, but it must not print upstream
server, port, method, password, or rendered runtime config.

Not frozen yet:

- final macOS secure storage mechanism for `authRef`;
- iOS NetworkExtension profile adapter;
- Windows system proxy/VPN adapter;
- production profile provisioning UI.
