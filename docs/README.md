# Proxy Gateway Console Docs

This directory contains public-safe documentation for the reusable gateway
console core.

Start here:

- [Open source boundary](OPEN_SOURCE_BOUNDARY.md)
- [GitHub Actions budget](ACTIONS_BUDGET.md)
- [Safety boundaries](SAFETY.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Configuration contract](CONFIG_LAYER_CONTRACT.md)
- [LAN gateway guide](LAN_GATEWAY.md)

Private closeout evidence, local verification records, generated plans, and
self-use package notes should stay outside the public repository or under a
private ignored directory.

## Current Public Baseline

- Local API binds to `127.0.0.1`.
- The UI presents operations, config, status, and logs surfaces.
- Runtime helpers keep root-level gateway changes terminal-gated.
- Encrypted profile import is supported without committing real upstream
  credentials.
- Tests use placeholder values and fake tokens only.

## Development

```bash
npm install
npm run open-source:check
npm run license:audit
npm run build
npm test
```
