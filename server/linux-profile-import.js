import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runCommand } from "./command.js";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const rootDir = resolve(__dirname, "..");
const gatewayAgentScript = resolve(rootDir, "agent/gateway_agent.py");
const maxProfileBytes = 1024 * 1024;

function decodeBase64(value) {
  try {
    return Buffer.from(String(value || ""), "base64");
  } catch {
    return Buffer.alloc(0);
  }
}

export function validateLinuxProfileUpload(payload = {}) {
  const fileName = String(payload.fileName || "");
  if (fileName !== "profile.json.enc" && !fileName.endsWith(".json.enc")) {
    return { ok: false, state: "blocked", summary: "Linux import only accepts profile.json.enc" };
  }

  const bytes = decodeBase64(payload.contentBase64);
  if (!bytes.length || bytes.length > maxProfileBytes) {
    return { ok: false, state: "blocked", summary: "encrypted profile size is invalid" };
  }

  let envelope;
  try {
    envelope = JSON.parse(bytes.toString("utf8"));
  } catch {
    return { ok: false, state: "blocked", summary: "encrypted profile is not valid JSON" };
  }

  const expected = {
    product: "PROXY_GATEWAY_PROFILE",
    version: 1,
    algorithm: "AES-256-GCM",
    kdf: "PBKDF2-HMAC-SHA256",
    iterations: 390000
  };
  for (const [key, value] of Object.entries(expected)) {
    if (envelope?.[key] !== value) {
      return { ok: false, state: "blocked", summary: `encrypted profile ${key} mismatch` };
    }
  }

  if (typeof envelope.salt !== "string" || typeof envelope.nonce !== "string" || typeof envelope.ciphertext !== "string") {
    return { ok: false, state: "blocked", summary: "encrypted profile envelope is incomplete" };
  }

  return { ok: true, fileName, bytes: bytes.length, buffer: bytes };
}

function parseJson(value, fallback) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function blockedImportResult() {
  return { ok: false, state: "blocked", summary: "profile import failed" };
}

function redactImportResult(parsed) {
  return {
    ok: Boolean(parsed?.ok),
    state: parsed?.state || "unknown",
    summary: parsed?.summary || "",
    profileSource: {
      mode: parsed?.profileSource?.mode || "local",
      path: parsed?.profileSource?.path || ""
    }
  };
}

export async function importLinuxProfileUpload(payload = {}, options = {}) {
  const upload = validateLinuxProfileUpload(payload);
  if (!upload.ok) {
    return upload;
  }

  const ownsTempDir = !options.tempDir;
  const tempBase = options.tempParent || tmpdir();
  const tempDir = options.tempDir || await mkdtemp(join(tempBase, "proxy-gateway-profile-"));
  const runner = options.runner || runCommand;
  const tempProfile = join(tempDir, "profile.json.enc");

  try {
    await writeFile(tempProfile, upload.buffer, { mode: 0o600 });
    const result = await runner("python3", [gatewayAgentScript, "profile-import", "--from", tempProfile], {
      timeoutMs: 8000,
      maxOutput: 64_000
    });
    const parsed = parseJson(result.stdout, blockedImportResult());
    return redactImportResult(parsed);
  } catch {
    return blockedImportResult();
  } finally {
    if (ownsTempDir) {
      await rm(tempDir, { recursive: true, force: true });
    }
  }
}
