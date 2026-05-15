# Updates

Proxy Gateway uses a public-safe release manifest for self-use updates.

The public repository owns source, release packaging scripts, checksums, and the
updater entrypoint. Private deployment remains responsible for real upstream
profiles, encrypted configuration, Apple signing material, and machine-specific
runtime state.

## Release Assets

The release workflow publishes:

- `ProxyGateway-Mac-SelfUse-<version>.zip`
- `ProxyGateway-Console-<version>-archive-<date>.tar.gz`
- `proxy-gateway-update-manifest.json`

The manifest is schema version `1` and records each asset name, platform,
architecture, size, URL, installability, and SHA256 checksum.

## Client Update Check

Run from an installed machine:

```bash
scripts/update/proxy-gateway-self-update.sh --check
```

Download and verify the matching package without installing:

```bash
scripts/update/proxy-gateway-self-update.sh --download --keep
```

Install is explicit and requires confirmation through the command line:

```bash
scripts/update/proxy-gateway-self-update.sh --install --yes
```

The updater refuses to install before the downloaded asset matches the manifest
SHA256. Mac updates still run the package installer, so privileged root
controller changes remain terminal-gated by `sudo`.

## Publishing

Use the `Release` GitHub Actions workflow with a version such as `0.2.1`.

The workflow builds the Mac self-use package, creates a source archive, generates
the update manifest, and uploads all release assets to the matching GitHub
Release tag.

Do not attach private runtime files to a public release. In particular, never
publish `upstream.json`, `profile.json.enc`, `sing-box.json`, logs, SSH keys, or
machine-specific verification evidence.
