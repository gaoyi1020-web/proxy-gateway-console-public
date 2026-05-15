import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

async function text(path) {
  return readFile(path, "utf8");
}

test("GitHub workflows cancel duplicate runs on the same ref", async () => {
  const workflows = [
    ".github/workflows/ci.yml",
    ".github/workflows/ios-upstream-candidate.yml",
    ".github/workflows/ios-signed-ipa.yml",
  ];

  for (const workflow of workflows) {
    const source = await text(workflow);

    assert.match(source, /^concurrency:\n  group: \$\{\{ github\.workflow \}\}-\$\{\{ github\.ref \}\}\n  cancel-in-progress: true/m, workflow);
  }
});

test("expensive iOS candidate workflow is manual-only", async () => {
  const source = await text(".github/workflows/ios-upstream-candidate.yml");

  assert.match(source, /^\s+workflow_dispatch:/m);
  assert.doesNotMatch(source, /^\s+pull_request:/m);
  assert.match(source, /runs-on: macos-15/);
});

test("Actions budget policy documents manual macOS and iOS workflows", async () => {
  const docsIndex = await text("docs/README.md");
  const policy = await text("docs/ACTIONS_BUDGET.md");

  assert.match(docsIndex, /ACTIONS_BUDGET\.md/);
  assert.match(policy, /Mac\/iOS workflows must not run automatically on pull requests/);
  assert.match(policy, /cancel-in-progress: true/);
  assert.match(policy, /gh run cancel <run-id>/);
});

test("local CI fallback is documented and wired", async () => {
  const packageJson = JSON.parse(await text("package.json"));
  const readme = await text("README.md");
  const policy = await text("docs/ACTIONS_BUDGET.md");
  const localCi = await text("scripts/local-ci.sh");

  assert.equal(packageJson.scripts["ci:local"], "bash scripts/local-ci.sh");
  assert.match(readme, /npm run ci:local/);
  assert.match(policy, /CI_LOCAL_INSTALL=1 npm run ci:local/);
  assert.match(localCi, /npm run open-source:check/);
  assert.match(localCi, /npm run license:audit/);
  assert.match(localCi, /CI_LOCAL_DESKTOP_CHECK:-auto/);
  assert.match(localCi, /desktop sidecar binary missing; npm run desktop:check skipped in auto mode/);
  assert.match(localCi, /npm run desktop:check/);
});

test("Dependabot keeps public dependency updates bounded", async () => {
  const dependabot = await text(".github/dependabot.yml");

  assert.match(dependabot, /package-ecosystem: "npm"/);
  assert.match(dependabot, /package-ecosystem: "cargo"/);
  assert.match(dependabot, /package-ecosystem: "github-actions"/);
  assert.match(dependabot, /package-ecosystem: "pip"/);
  assert.match(dependabot, /open-pull-requests-limit: 3/);
  assert.match(dependabot, /interval: "weekly"/);
});
