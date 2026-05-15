# GitHub Actions Budget

Proxy Gateway Console keeps GitHub-hosted Actions focused on low-cost source
verification. Expensive platform builds should run only when someone chooses to
spend the minutes.

## Default Policy

- `CI` may run on pull requests and pushes to `main`.
- `CI` must stay on `ubuntu-latest` and should remain source-only.
- iOS and signed IPA workflows must stay `workflow_dispatch` only.
- Mac/iOS workflows must not run automatically on pull requests.
- All workflows must use `concurrency` with `cancel-in-progress: true` so a new
  push cancels the older run for the same ref.

## Expensive Workflows

These workflows use GitHub-hosted macOS runners and can consume monthly minutes
quickly:

- `iOS Upstream Candidate`
- `iOS Signed IPA`

Run them manually only when the output is needed for a release decision. For
routine development, prefer local hardware, a self-hosted runner, or a separate
server environment.

## Budget Alert Response

When GitHub sends an Actions usage alert:

1. Check active runs:

   ```bash
   gh run list --repo gaoyi1020-web/proxy-gateway-console --status in_progress --limit 20
   gh run list --repo gaoyi1020-web/proxy-gateway-console --status queued --limit 20
   ```

2. Cancel nonessential long-running jobs:

   ```bash
   gh run cancel <run-id> --repo gaoyi1020-web/proxy-gateway-console
   ```

3. Confirm the PR is not repeatedly triggering macOS/iOS workflows.
4. Keep local validation evidence in the PR while the account budget blocks
   hosted CI.

## Local CI Fallback

Use the local CI gate when GitHub-hosted runners are blocked by quota, spending
limits, or billing:

```bash
npm run ci:local
```

For a clean checkout or a machine with unknown dependencies:

```bash
CI_LOCAL_INSTALL=1 npm run ci:local
```

The local gate runs the public-core scan, license audit, production build,
Node/Python/runtime tests, shell syntax checks, Mac kit static verification, and
package-boundary checks. It also runs the Tauri desktop compile check when the
generated sidecar binary is present; set `CI_LOCAL_DESKTOP_CHECK=1` to require
that check after running `scripts/desktop/build-agent-sidecar.sh`.

## Public Release Note

If this repository is published as a public project, standard GitHub-hosted
Actions runners become free for public repositories. Until then, treat all
private-repo Actions minutes as scarce.
