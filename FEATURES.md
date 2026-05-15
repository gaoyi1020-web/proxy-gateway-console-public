# Proxy Gateway Feature Boundary

This file tracks the reusable public-core boundary. Private deployment
evidence, local release artifacts, and machine-specific runtime state are
intentionally outside this checklist.

## Public Core Scope

- Linux local gateway runtime helpers live under `runtime/proxy-stack/`.
- The Node API is loopback-only by default.
- The Web console is split into operations, config, status, and logs views.
- The desktop/control UI keeps advanced maintenance controls out of the normal
  path.
- Gateway actions are allowlisted and privilege-sensitive actions remain
  terminal-gated.
- Configuration remains separate from the program package.
- Real credentials, private profiles, generated runtime configs, and logs are
  not committed.
- Tests cover the server, Python agent/runtime helpers, and frontend type
  build.

## Private Overlay Scope

Keep these in a private deployment overlay:

- real upstream routes and credentials;
- exact LAN IPs, device MAC addresses, hostnames, and local usernames;
- self-use installers and generated archives;
- historical verification evidence and local closeout records;
- Apple signing material and signed app build artifacts.

## Phone Compatibility Module

Phone-side per-app validation, native mobile controller UI, VPN or
NetworkExtension work, device packet capture, and mobile compatibility scoring
are separate modules. They should consume the public status/self-check
contracts rather than duplicating host probes.

## Verification Commands

```bash
npm test
npm run build
```

Optional local deployment checks can run in a private overlay after confirming
they do not expose secrets or machine-specific evidence.
