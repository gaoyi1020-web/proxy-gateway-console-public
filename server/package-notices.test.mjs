import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

async function text(path) {
  return readFile(path, "utf8");
}

test("source and USB packages retain project and third-party notices", async () => {
  const awsPackage = await text("scripts/cloud/package-v2-for-aws.sh");
  const usbStage = await text("scripts/stage-usb-v2.sh");

  assert.match(awsPackage, /tar -tzf "\$\{OUT\}" \.\/LICENSE \.\/docs\/THIRD_PARTY_NOTICES\.md/);
  assert.match(usbStage, /test -f "\$\{APP_DIR\}\/LICENSE"/);
  assert.match(usbStage, /test -f "\$\{APP_DIR\}\/docs\/THIRD_PARTY_NOTICES\.md"/);
});

test("Mac self-use package includes license notices and verifies them", async () => {
  const packageScript = await text("scripts/macvpn/package-self-use-installer.sh");
  const verifyScript = await text("scripts/macvpn/verify-mac-self-use-package-sandbox.sh");

  assert.match(packageScript, /PACKAGE_DIR\}\/notices/);
  assert.match(packageScript, /install -m 0644 "\$\{ROOT_DIR\}\/LICENSE" "\$\{PACKAGE_DIR\}\/notices\/LICENSE"/);
  assert.match(packageScript, /install -m 0644 "\$\{ROOT_DIR\}\/docs\/THIRD_PARTY_NOTICES\.md" "\$\{PACKAGE_DIR\}\/notices\/THIRD_PARTY_NOTICES\.md"/);
  assert.match(packageScript, /scripts\/update\/proxy-gateway-self-update\.sh/);
  assert.match(packageScript, /PROXY_GATEWAY_SKIP_ROOTCTL_INSTALL/);
  assert.match(packageScript, /root controller install skipped/);
  assert.match(packageScript, /OUT_DIR="\$\{ROOT_DIR\}\/\$\{OUT_DIR\}"/);
  assert.match(packageScript, /ZIP_PATH="\$\{OUT_DIR\}\/ProxyGateway-Mac-SelfUse-\$\{VERSION\}\.zip"/);
  assert.match(packageScript, /test -f "\$\{PACKAGE_DIR\}\/notices\/LICENSE"/);
  assert.match(packageScript, /test -f "\$\{PACKAGE_DIR\}\/notices\/THIRD_PARTY_NOTICES\.md"/);
  assert.match(verifyScript, /project license notice/);
  assert.match(verifyScript, /third-party notices/);
});

test("Cargo vendor package includes notices beside vendored dependencies", async () => {
  const vendorScript = await text("scripts/desktop/package-cargo-vendor.sh");

  assert.match(vendorScript, /mkdir -p notices/);
  assert.match(vendorScript, /install -m 0644 "\$\{ROOT_DIR\}\/LICENSE" notices\/LICENSE/);
  assert.match(vendorScript, /install -m 0644 "\$\{ROOT_DIR\}\/docs\/THIRD_PARTY_NOTICES\.md" notices\/THIRD_PARTY_NOTICES\.md/);
  assert.match(vendorScript, /tar -czf "\$\{OUT\}" -C "\$\{work_dir\}" vendor \.cargo notices/);
  assert.match(vendorScript, /notices\/THIRD_PARTY_NOTICES\.md/);
});
