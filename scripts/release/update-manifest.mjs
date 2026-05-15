#!/usr/bin/env node
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, stat, writeFile } from "node:fs/promises";
import { basename, dirname } from "node:path";
import { pathToFileURL } from "node:url";

const MANIFEST_NAME = "proxy-gateway-update-manifest.json";
const PRIVATE_ASSET_PATTERN = /^(upstream[.]json|sing-box[.]json|profile[.]json[.]enc|privatekey|publickey)$|[.](log|tmp|pem|key)$/i;

function usage() {
  return `usage: scripts/release/update-manifest.mjs --repo owner/name --tag vX.Y.Z --version X.Y.Z --asset <path> [--asset <path> ...] --out <path>

Creates ${MANIFEST_NAME} for GitHub Release based updates.
`;
}

function slug(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "asset";
}

function releaseAssetUrl(repo, tag, name) {
  return `https://github.com/${repo}/releases/download/${encodeURIComponent(tag)}/${encodeURIComponent(name)}`;
}

async function sha256File(path) {
  const hash = createHash("sha256");
  await new Promise((resolve, reject) => {
    const stream = createReadStream(path);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("error", reject);
    stream.on("end", resolve);
  });
  return hash.digest("hex");
}

export function classifyReleaseAsset(assetName) {
  const name = basename(assetName);

  if (PRIVATE_ASSET_PATTERN.test(name)) {
    throw new Error(`private runtime asset is not allowed in update manifest: ${name}`);
  }

  if (/^ProxyGateway-Mac-SelfUse-.+[.]zip$/i.test(name)) {
    return {
      id: "mac-self-use",
      kind: "self-use-zip",
      platform: "darwin",
      arch: "universal",
      installable: true,
      installHint: "Unzip and run Install Proxy Gateway.command",
    };
  }

  const linux = /^ProxyGateway-Linux-SelfUse-.+-([A-Za-z0-9_.-]+)[.]tar[.]gz$/i.exec(name);
  if (linux) {
    return {
      id: `linux-self-use-${slug(linux[1])}`,
      kind: "self-use-tar",
      platform: "linux",
      arch: linux[1],
      installable: true,
      installHint: "Extract and run Install Proxy Gateway.sh",
    };
  }

  if (/^ProxyGateway-Console-.+archive.+[.]tar[.]gz$/i.test(name)) {
    return {
      id: "source-archive",
      kind: "source-archive",
      platform: "source",
      arch: "any",
      installable: false,
      installHint: "Source archive for review and manual builds",
    };
  }

  return {
    id: slug(name.replace(/[.](zip|tar[.]gz)$/i, "")),
    kind: "generic",
    platform: "unknown",
    arch: "unknown",
    installable: false,
    installHint: "Generic release asset",
  };
}

export async function buildUpdateManifest(options) {
  const repo = options.repo;
  const tag = options.tag;
  const version = options.version;
  const assets = options.assets ?? [];
  const generatedAt = options.generatedAt ?? new Date().toISOString();

  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo ?? "")) {
    throw new Error(`invalid GitHub repository: ${repo}`);
  }
  if (!tag) {
    throw new Error("release tag is required");
  }
  if (!version) {
    throw new Error("release version is required");
  }
  if (assets.length === 0) {
    throw new Error("at least one release asset is required");
  }

  const seen = new Map();
  const manifestAssets = [];
  for (const assetPath of assets) {
    const name = basename(assetPath);
    const assetStat = await stat(assetPath);
    const classification = classifyReleaseAsset(name);
    const occurrence = seen.get(classification.id) ?? 0;
    seen.set(classification.id, occurrence + 1);
    const id = occurrence === 0 ? classification.id : `${classification.id}-${occurrence + 1}`;

    manifestAssets.push({
      id,
      name,
      kind: classification.kind,
      platform: classification.platform,
      arch: classification.arch,
      installable: classification.installable,
      installHint: classification.installHint,
      url: releaseAssetUrl(repo, tag, name),
      sha256: await sha256File(assetPath),
      size: assetStat.size,
    });
  }

  return {
    schemaVersion: 1,
    generatedAt,
    repo,
    version,
    tag,
    release: {
      htmlUrl: `https://github.com/${repo}/releases/tag/${encodeURIComponent(tag)}`,
      apiUrl: `https://api.github.com/repos/${repo}/releases/tags/${encodeURIComponent(tag)}`,
    },
    assets: manifestAssets,
  };
}

function parseArgs(argv) {
  const options = {
    assets: [],
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case "--repo":
        options.repo = argv[++i];
        break;
      case "--tag":
        options.tag = argv[++i];
        break;
      case "--version":
        options.version = argv[++i];
        break;
      case "--asset":
        options.assets.push(argv[++i]);
        break;
      case "--out":
        options.out = argv[++i];
        break;
      case "--generated-at":
        options.generatedAt = argv[++i];
        break;
      case "-h":
      case "--help":
        options.help = true;
        break;
      default:
        throw new Error(`unknown argument: ${arg}`);
    }
  }

  return options;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(usage());
    return;
  }
  if (!options.out) {
    throw new Error("--out is required");
  }

  const manifest = await buildUpdateManifest(options);
  await mkdir(dirname(options.out), { recursive: true });
  await writeFile(options.out, `${JSON.stringify(manifest, null, 2)}\n`);
  process.stdout.write(`wrote: ${options.out}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.stderr.write(usage());
    process.exit(1);
  });
}
