import test from "node:test";
import assert from "node:assert/strict";
import { runCommand } from "./command.js";

test("runCommand keeps larger stdout when maxOutput is configured", async () => {
  const payloadSize = 20_000;
  const result = await runCommand("/usr/bin/python3", ["-c", `import sys; sys.stdout.write("x" * ${payloadSize})`], {
    maxOutput: 32_000
  });

  assert.equal(result.ok, true);
  assert.equal(result.stdout.length, payloadSize);
});
