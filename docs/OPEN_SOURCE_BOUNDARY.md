# Open Source Boundary

This document defines what can be public and what must stay private for Proxy
Gateway Console.

## Public Core

The public repository should contain the reusable product core:

- React/Tauri UI in `src/` and `src-tauri/`.
- Loopback-only Node API in `server/`.
- Python agent and runtime helpers in `agent/` and `runtime/`.
- Non-secret templates in `config/`.
- Install, validation, and packaging scripts that use placeholders or
  environment variables.
- Tests and fixtures that use fake tokens, example IP ranges, and temporary
  paths.
- Safety, configuration, third-party notice, and contribution documentation.

## Private Overlay

Keep these outside the public repository:

- real upstream proxy servers, ports, methods, usernames, passwords, tokens, and
  API keys;
- SSH keys, Apple signing certificates, provisioning profiles, and App Store
  Connect keys;
- encrypted user profiles, generated runtime configs, logs, network snapshots,
  screenshots, and local verification evidence;
- home or office LAN addresses, device MAC addresses, hostnames, usernames, and
  machine-specific paths;
- self-use `.zip` and `.tar.gz` release artifacts.

## Public-Ready Checklist

Foundation items for the public-core boundary:

- [x] Add a license and root security policy.
- [x] Rewrite the root README around the reusable public core.
- [x] Ignore private evidence directories and self-use release artifacts.
- [x] Replace public documentation examples with placeholders.
- [x] Add third-party notice documentation and a local license audit command.
- [x] Keep package publication disabled with `"private": true`.
- [x] Keep expensive Mac/iOS GitHub Actions manual-only and duplicate runs
      cancelled.

Follow-up cleanup required before changing repository visibility:

- [x] Remove already tracked self-use archives from the Git index.
- [x] Remove already tracked private verification and planning records from the
      Git index.
- [x] Replace committed machine-specific home paths, private LAN addresses, and
      private upstream labels in source, tests, and runtime examples with
      placeholders.
- [x] Run current-file secret scan after cleanup changes are staged.
- [ ] Run history secret scan before changing GitHub visibility.
- [ ] Publish only after rewriting/squashing history or exporting a clean public
      repository, because existing history contains private machine and network
      evidence.
- [ ] Revisit whether npm publishing is in scope.

## Release Rule

Changing the GitHub repository from private to public should be a separate,
explicit action after this checklist passes. Public visibility must not be used
as the cleanup mechanism.
