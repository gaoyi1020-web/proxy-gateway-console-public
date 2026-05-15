import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { importLinuxProfileUpload, validateLinuxProfileUpload } from "./linux-profile-import.js";

const validEnvelope = {
  product: "PROXY_GATEWAY_PROFILE",
  version: 1,
  algorithm: "AES-256-GCM",
  kdf: "PBKDF2-HMAC-SHA256",
  iterations: 390000,
  salt: "c2FsdC1ieXRlcy0xMjM0",
  nonce: "bm9uY2UtYnl0ZXM",
  ciphertext: "Y2lwaGVydGV4dA=="
};

function body(payload = validEnvelope) {
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64");
}

test("validateLinuxProfileUpload accepts encrypted profile envelopes only", () => {
  const upload = validateLinuxProfileUpload({
    fileName: "profile.json.enc",
    contentBase64: body()
  });

  assert.equal(upload.ok, true);
  assert.equal(upload.fileName, "profile.json.enc");
  assert.equal(upload.bytes > 20, true);
});

test("validateLinuxProfileUpload rejects wrong extension and bad envelope", () => {
  assert.equal(validateLinuxProfileUpload({ fileName: "upstream.json", contentBase64: body() }).ok, false);
  assert.equal(validateLinuxProfileUpload({ fileName: "profile.json.enc", contentBase64: body({ product: "x" }) }).ok, false);
});

test("importLinuxProfileUpload copies through gateway-agent and does not echo ciphertext", async () => {
  const tempDir = await mkdtemp(join(tmpdir(), "linux-profile-import-"));
  const calls = [];
  try {
    const result = await importLinuxProfileUpload(
      { fileName: "profile.json.enc", contentBase64: body() },
      {
        tempDir,
        runner: async (cmd, args) => {
          calls.push([cmd, args]);
          const from = args[args.indexOf("--from") + 1];
          const written = await readFile(from, "utf8");
          assert.match(written, /PROXY_GATEWAY_PROFILE/);
          return {
            ok: true,
            stdout: JSON.stringify({
              ok: true,
              state: "imported",
              profileSource: { mode: "local", path: "~/.config/proxy-gateway/profile.json.enc" }
            }),
            stderr: ""
          };
        }
      }
    );

    assert.equal(result.ok, true);
    assert.equal(result.state, "imported");
    assert.equal(calls.length, 1);
    assert.doesNotMatch(JSON.stringify(result), /Y2lwaGVydGV4dA/);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("importLinuxProfileUpload cleans owned temp directory after import", async () => {
  const parent = await mkdtemp(join(tmpdir(), "linux-profile-import-parent-"));
  try {
    const result = await importLinuxProfileUpload(
      { fileName: "profile.json.enc", contentBase64: body() },
      {
        tempParent: parent,
        runner: async () => ({ ok: true, stdout: JSON.stringify({ ok: true, state: "imported" }), stderr: "" })
      }
    );

    assert.equal(result.ok, true);
    assert.deepEqual(await readdir(parent), []);
  } finally {
    await rm(parent, { recursive: true, force: true });
  }
});

test("importLinuxProfileUpload returns generic failure details", async () => {
  const result = await importLinuxProfileUpload(
    { fileName: "profile.json.enc", contentBase64: body() },
    {
      runner: async () => {
        throw new Error("stack trace with /private/path");
      }
    }
  );

  assert.equal(result.ok, false);
  assert.equal(result.summary, "profile import failed");
  assert.doesNotMatch(JSON.stringify(result), /private\/path|stack trace/);
});
