# Proxy Gateway Console

Local-first control console for a personal proxy gateway. The project combines
a React/Tauri operator UI, a Node loopback API, and Python runtime helpers for
status checks, encrypted profiles, failover routing, and LAN proxy workflows.

The public project is designed to be reusable without carrying a developer's
private network state. Real upstream servers, credentials, device evidence,
logs, and release artifacts belong in a private deployment layer.

## What It Provides

- Loopback-only web console and desktop control surface.
- Status-first operations, config, logs, and diagnostic views.
- Python runtime helpers for gateway status, port registry, session state, and
  route policy checks.
- Encrypted profile import and schema validation.
- Single-client LAN gateway planning with terminal-gated privileged commands.
- Tests for the Node API, Python runtime, and frontend type build.

## Public And Private Split

Public source should include:

- `src/`, `server/`, `agent/`, `runtime/`, `scripts/`, and non-secret config
  templates.
- Safety, configuration, and release-readiness documentation.
- Test fixtures that use example IPs, placeholder paths, and fake tokens only.

Private deployment should keep:

- Real proxy upstreams, passwords, API keys, SSH keys, Apple signing material,
  and encrypted user profiles.
- Home or office network IPs, device MAC addresses, local usernames, logs, and
  machine-specific verification records.
- Built self-use installers and archives. Publish release artifacts through
  GitHub Releases after a separate review.

See [docs/OPEN_SOURCE_BOUNDARY.md](docs/OPEN_SOURCE_BOUNDARY.md) for the
working boundary and remaining public-release checks.
Third-party dependency notices are tracked in
[docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).

## Architecture

| Area | Path | Purpose |
| --- | --- | --- |
| Web UI | `src/` | React operations console |
| API | `server/` | Loopback-only control and status API |
| Runtime agent | `agent/` | Profile, session, health, and lifecycle helpers |
| Proxy stack | `runtime/proxy-stack/` | Local routing and self-check commands |
| Config templates | `config/` | Non-secret route and profile examples |
| Desktop shell | `src-tauri/` | Tauri desktop packaging |
| Tests | `server/*.test.mjs`, `agent/tests/`, `runtime/proxy-stack/tests/` | Public-safe coverage |

## Requirements

- Node.js 22.x
- npm 10.x
- Python 3.11+
- Rust/Tauri toolchain for desktop builds
- Linux for the full proxy-stack runtime path

## Quickstart

Use these commands from a fresh clone to validate the public project and start
the loopback development services:

```bash
git clone https://github.com/gaoyi1020-web/proxy-gateway-console-public.git
cd proxy-gateway-console-public
npm ci
npm run ci:local
```

Start the API and web UI in separate terminals:

```bash
npm run server
npm run dev
```

The API binds to `127.0.0.1:4077`. The Vite dev server binds to
`127.0.0.1:5177`.

If you are validating an existing checkout whose dependencies may be missing or
stale, use `CI_LOCAL_INSTALL=1 npm run ci:local` to refresh npm and Python test
dependencies before running the checks.

## Public Usability Matrix

| Area | Works From A Public Clone | Requires Private Local Configuration |
| --- | --- | --- |
| Install and local CI | `npm ci` and `npm run ci:local` | None |
| Loopback API and web UI | `npm run server` and `npm run dev` | None for the development surfaces |
| Tests and build | Node API, Python agent/runtime, UI typecheck, and frontend build | None |
| Profile handling | Placeholder-safe schema validation and import paths | Real encrypted profiles stay outside Git |
| Proxy-stack runtime | Static checks and public-safe tests | Linux host setup plus your own upstream proxy profile |
| LAN gateway planning | Public code path and terminal-gated plan flow | Your own LAN interface and private route details |
| Desktop shell | Tauri source and compile check when a sidecar exists | Generated sidecar binary and local release/signing process |

The public repository is therefore ready for developer setup, review, and
extension. It is not a one-command consumer installer: real upstream servers,
credentials, encrypted profiles, LAN details, generated sidecars, and signed
release artifacts must be supplied by each private deployment.

## Development

```bash
npm ci
npm run ci:local
npm run license:audit
npm run build
npm test
```

When GitHub-hosted Actions minutes are unavailable, use `npm run ci:local` as
the local source CI gate. The Tauri desktop compile check runs automatically
when the generated sidecar binary is present; use
`CI_LOCAL_DESKTOP_CHECK=1 npm run ci:local` to require it after running
`scripts/desktop/build-agent-sidecar.sh`.

## Example Local Proxy Entries

These examples are placeholders. Replace them through private deployment
configuration, not committed source.

```bash
HTTP_PROXY=http://127.0.0.1:18180
HTTPS_PROXY=http://127.0.0.1:18180
```

For same-LAN phone testing, use the LAN IP reported by your runtime plan, for
example `192.0.2.10:18181`. Do not commit real device IPs or MAC addresses.

## Security

This is a local operator console, not a hosted public web application. Keep the
API bound to loopback, keep privileged changes terminal-gated, and never commit
secrets or machine-specific runtime evidence.

Read [SECURITY.md](SECURITY.md) and [docs/SAFETY.md](docs/SAFETY.md) before
opening the repository or publishing releases.
