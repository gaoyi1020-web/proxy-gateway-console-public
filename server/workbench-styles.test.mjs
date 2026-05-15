import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const globalCss = readFileSync("src/styles.css", "utf8");
const linuxWorkbenchCssPath = "src/styles/linux-workbench.css";
const linuxWorkbenchCss = existsSync(linuxWorkbenchCssPath) ? readFileSync(linuxWorkbenchCssPath, "utf8") : "";
const css = `${globalCss}\n${linuxWorkbenchCss}`;

test("Linux workbench styles live in a scoped stylesheet", () => {
  assert.equal(existsSync(linuxWorkbenchCssPath), true);
  assert.match(readFileSync("src/main.tsx", "utf8"), /import "\.\/styles\/linux-workbench\.css";/);
  assert.doesNotMatch(globalCss, /\.linux-status-workbench/);
  assert.doesNotMatch(globalCss, /\.(?:linux-|simple-|config-grid|feature-switch|switch-panel|switch-grid|switch-button|control-grid|control-card|state-pill|inline-result|maintenance-actions|desktop-detail-grid|runtime-state-grid|workbench-top-grid|console-layout|web-workbench|web-summary|operations-page|status-page|logs-page)/);
  assert.match(linuxWorkbenchCss, /\.linux-status-workbench/);
});

test("Linux status workbench uses light dashboard surface classes", () => {
  assert.match(css, /\.linux-status-workbench/);
  assert.match(css, /\.web-workbench-shell/);
  assert.match(css, /\.web-workbench-sidebar/);
  assert.match(css, /\.web-summary-strip/);
  assert.match(css, /\.operations-page/);
  assert.match(css, /\.status-page/);
  assert.match(css, /\.logs-page/);
  assert.match(css, /\.simple-status-card/);
  assert.match(css, /\.simple-action-button/);
  assert.match(css, /\.workbench-panel/);
  assert.match(css, /\.console-layout/);
  assert.match(css, /\.console-status-stack/);
  assert.match(css, /\.feature-switch/);
  assert.match(css, /\.toggle-track/);
  assert.match(css, /\.linux-status-tile/);
  assert.match(css, /\.runtime-state-panel/);
  assert.match(css, /\.config-page/);
});

test("Linux v4 and v5 surfaces no longer use dark translucent panels", () => {
  assert.doesNotMatch(css, /rgba\(15,\s*23,\s*42,\s*0\.58\)/);
  assert.doesNotMatch(css, /rgba\(2,\s*6,\s*23,\s*0\.28\)/);
  assert.doesNotMatch(css, /\.(?:linux-v4-panel|config-editor|linux-v5-unification)[^{]*\{[^}]*rgba\(15,\s*23,\s*42/);
  assert.doesNotMatch(css, /\.(?:linux-v4-panel|config-editor|linux-v5-unification)[^{]*\{[^}]*rgba\(2,\s*6,\s*23/);
});
