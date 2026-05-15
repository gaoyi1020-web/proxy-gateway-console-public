# Proxy Stack Runtime

This runtime layer contains local helper scripts for status checks, route
planning, failover proxy state, and controlled gateway operations.

The public source must stay deployment-neutral. Real service names, upstream
providers, LAN IPs, device identifiers, and log output belong in a private
overlay.

## Typical Commands

```bash
~/.local/bin/proxy-stack status
~/.local/bin/proxy-stack self-check
~/.local/bin/proxy-stack self-check --deep
~/.local/bin/proxy-stack test
~/.local/bin/proxy-stack logs
~/.local/bin/proxy-stack lan-gateway-plan
```

Root-gated commands must stay explicit:

```bash
sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip CLIENT-IP
sudo ~/.local/bin/proxy-stack lan-gateway-root-remove
```

## Local Routes

The default public examples use placeholder local ports:

- main local HTTP proxy: `127.0.0.1:8118`
- secondary HTTP proxy: `127.0.0.1:18122`
- local failover proxy: `127.0.0.1:18180`
- same-LAN phone proxy: `LAN-IP:18181`

Private deployments can map these to real upstreams through local config.

## Safety

- Keep the dashboard and API loopback-only by default.
- Do not print secrets, encrypted profile payloads, or generated runtime
  configs.
- Do not apply nftables changes for a whole subnet.
- Prefer read-only plan/status commands before root apply paths.
