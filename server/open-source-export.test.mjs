import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

async function text(path) {
  return readFile(path, "utf8");
}

test("public export script creates a no-history snapshot from the Git index", async () => {
  const script = await text("scripts/open-source/export-public-snapshot.sh");
  const packageJson = JSON.parse(await text("package.json"));
  const gitignore = await text(".gitignore");

  assert.equal(packageJson.scripts["open-source:check"], "bash scripts/open-source/check-public-core.sh");
  assert.equal(packageJson.scripts["open-source:export"], "bash scripts/open-source/export-public-snapshot.sh");
  assert.match(gitignore, /dist\/open-source\//);
  assert.match(script, /git ls-files -z --cached/);
  assert.match(script, /git diff --quiet/);
  assert.match(script, /SOURCE_MANIFEST\.txt/);
  assert.match(script, /history=included=false/);
  assert.match(script, /docs\/THIRD_PARTY_NOTICES\.md/);
});

test("public core check blocks tracked private paths and traces", async () => {
  const script = await text("scripts/open-source/check-public-core.sh");

  assert.match(script, /blocked private or generated paths are tracked/);
  assert.match(script, /private trace scan found blocked patterns/);
  assert.match(script, /docs\/ACTIONS_BUDGET\.md/);
  assert.match(script, /192\[.\]168\[.\]10\[.\]/);
});

test("public source tree does not track generated dist artifacts", async () => {
  const { stdout } = await execFileAsync("git", ["ls-files", "dist"]);

  assert.equal(stdout.trim(), "");
});

test("public export script excludes private package and closeout material", async () => {
  const script = await text("scripts/open-source/export-public-snapshot.sh");

  assert.match(script, /dist\/\*/);
  assert.match(script, /src-tauri\/binaries\/\*/);
  assert.match(script, /docs\/verification\/\*/);
  assert.match(script, /docs\/superpowers\/\*/);
  assert.match(script, /docs\/cgc\/\*/);
  assert.match(script, /docs\/phone-compat\/\*/);
  assert.match(script, /profile\.json\.enc/);
  assert.match(script, /publickey/);
  assert.match(script, /privatekey/);
});

test("public export script scans blocked private traces before publishing", async () => {
  const script = await text("scripts/open-source/export-public-snapshot.sh");

  assert.match(script, /scan_private_traces/);
  assert.match(script, /\/\[h\]ome\/g/);
  assert.match(script, /\/\[U\]sers\/g/);
  assert.match(script, /192\[.\]168\[.\]10\[.\]/);
  assert.match(script, /BEGIN \(OPENSSH\|RSA\|DSA\|EC\)\[\[:space:\]\]\+PRIVATE\[\[:space:\]\]\+KEY/);
  assert.match(script, /private trace scan found blocked patterns/);
});
