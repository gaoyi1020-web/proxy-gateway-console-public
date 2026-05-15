# Security Policy

Proxy Gateway Console is a local operator tool. Treat it as security-sensitive
infrastructure because it can inspect and guide local proxy routes.

## Supported Scope

Security fixes are expected on the default branch and public release branches.
Private deployment overlays, local profiles, credentials, and self-use
artifacts are not supported in the public repository.

## Reporting

Do not open public issues containing secrets, private endpoints, IP addresses,
device identifiers, logs, or screenshots from a live network.

For public reports, include only:

- affected version or commit;
- reproduction steps using placeholder addresses;
- expected and actual behavior;
- whether the issue requires local UI access, loopback API access, or shell
  access.

## Boundary

- The API must bind to `127.0.0.1` by default.
- The UI must not accept arbitrary shell commands.
- Root or administrator operations must stay allowlisted and terminal-gated.
- Real upstream credentials, private keys, profile ciphertext, logs, and
  machine-specific evidence must not be committed.
- Release artifacts should be built from reviewed source and published through
  GitHub Releases, not kept as tracked repository files.
