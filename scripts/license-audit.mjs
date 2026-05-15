#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";

const permissiveAlternatives = /\b(MIT|Apache-2\.0|BSD-[23]-Clause|ISC|Zlib|0BSD|Unlicense|MIT-0)\b/i;
const strongCopyleft = /\b(AGPL|GPL|LGPL|SSPL)\b/i;

function licenseRisk(license) {
  if (!license || license === "UNKNOWN") {
    return "unknown";
  }
  if (strongCopyleft.test(license) && !/\bOR\b/i.test(license)) {
    return "copyleft";
  }
  if (strongCopyleft.test(license) && !permissiveAlternatives.test(license)) {
    return "copyleft";
  }
  return "";
}

function printCounts(label, licenses) {
  const counts = new Map();
  for (const license of licenses) {
    counts.set(license || "UNKNOWN", (counts.get(license || "UNKNOWN") || 0) + 1);
  }
  console.log(`\n${label}`);
  for (const [license, count] of [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    console.log(`  ${license}: ${count}`);
  }
}

function auditNpm() {
  if (!existsSync("package-lock.json")) {
    return [];
  }
  const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
  const rows = Object.entries(lock.packages || {})
    .filter(([path]) => path.startsWith("node_modules/"))
    .map(([path, pkg]) => ({
      ecosystem: "npm",
      name: path.replace(/^node_modules\//, ""),
      version: pkg.version || "",
      license: typeof pkg.license === "string" ? pkg.license : JSON.stringify(pkg.license || pkg.licenses || "UNKNOWN")
    }));
  printCounts("npm package licenses", rows.map((row) => row.license));
  return rows;
}

function auditCargo() {
  if (!existsSync("src-tauri/Cargo.toml")) {
    return [];
  }
  const metadata = JSON.parse(
    execFileSync(
      "cargo",
      ["metadata", "--manifest-path", "src-tauri/Cargo.toml", "--format-version", "1", "--locked"],
      { encoding: "utf8", maxBuffer: 32 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"] }
    )
  );
  const rows = metadata.packages
    .filter((pkg) => pkg.source)
    .map((pkg) => ({
      ecosystem: "cargo",
      name: pkg.name,
      version: pkg.version || "",
      license: pkg.license || pkg.license_file || "UNKNOWN"
    }));
  printCounts("cargo crate licenses", rows.map((row) => row.license));
  return rows;
}

function main() {
  const rows = [...auditNpm(), ...auditCargo()];
  const blockers = rows
    .map((row) => ({ ...row, risk: licenseRisk(row.license) }))
    .filter((row) => row.risk);

  if (blockers.length > 0) {
    console.error("\nlicense audit blockers:");
    for (const row of blockers) {
      console.error(`  ${row.ecosystem}:${row.name}@${row.version} ${row.license} (${row.risk})`);
    }
    process.exit(1);
  }

  const notices = rows.filter((row) => /MPL|CC-BY|Unicode/i.test(row.license));
  if (notices.length > 0) {
    console.log("\nnotice-only licenses to preserve in binary releases:");
    for (const row of notices) {
      console.log(`  ${row.ecosystem}:${row.name}@${row.version} ${row.license}`);
    }
  }
  console.log("\nlicense audit passed");
}

main();
