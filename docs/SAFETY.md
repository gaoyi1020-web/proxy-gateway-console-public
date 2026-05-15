# Safety Boundaries

Proxy Gateway Console is a local operator console. It is not a hosted public
web application and should stay bound to loopback unless a deployment overlay
explicitly narrows and documents a LAN exposure.

## Non-Negotiable Boundaries

- Do not store or print proxy passwords, WireGuard private keys, SSH keys, API
  keys, signing material, cookies, or cloud access keys.
- Do not expose the API outside `127.0.0.1` by default.
- Do not accept arbitrary shell commands from the UI.
- Do not create, stop, or delete cloud resources from the UI.
- Do not switch existing application services to the failover route
  automatically. Each service must opt in.
- Do not enable a transparent hotspot gateway when the upstream and hotspot use
  the same Wi-Fi adapter.
- Do not let USB phone tethering silently take over the host default route.
- Do not enable LAN gateway mode for a whole subnet. The controlled path is one
  explicit client address at a time.
- Do not load transparent nftables rules unless the operator explicitly chooses
  that mode.

## Allowed Public-Core Actions

- Read local status through fixed, allowlisted commands.
- Run non-destructive stack tests and self-checks.
- Show terminal-gated privileged commands without executing them.
- Restart project-owned user services when the action is allowlisted.
- Import encrypted profiles through the documented profile contract.
- Generate local-only setup guidance with placeholder addresses.

## Example Routes

| Purpose | Local entry | Upstream |
| --- | --- | --- |
| Main local proxy | `127.0.0.1:8118`, `127.0.0.1:1080` | private upstream |
| Phone or secondary proxy | `127.0.0.1:18122`, `127.0.0.1:11880` | private upstream |
| Local app failover | `127.0.0.1:18180` | primary local route, fallback secondary route |
| Same-LAN phone proxy | `LAN-IP:18181` | direct private ranges, proxy foreign routes |
| Single-client LAN gateway | `LAN-IP` as manual router | DNS and TCP redirect through local services |

## Privilege Model

The backend runs as the current user. Commands requiring root, sudo, or polkit
must fail cleanly when permission is absent and report redacted stderr to the
UI. Privileged helpers should stay separate, fixed-command, and allowlisted
rather than expanding the Node API surface.
