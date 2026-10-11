import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import path from "node:path";
import { readFileSync } from "node:fs";

const root = path.resolve(import.meta.dirname, "..");

/**
 * Load the shipped TypeScript module via a small Node transpile bridge:
 * strip types with the project's TypeScript API so tests exercise real
 * resolvePanelToggle / SIDE_PANEL_META without re-implementing them.
 */
async function loadSidePanelMode() {
  const require = createRequire(import.meta.url);
  const ts = require("typescript");
  const sourcePath = path.join(root, "lib/shell/sidePanelMode.ts");
  const source = readFileSync(sourcePath, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
    },
    fileName: sourcePath,
  });
  const dataUrl =
    "data:text/javascript;charset=utf-8," + encodeURIComponent(outputText);
  return import(dataUrl);
}

test("SIDE_PANEL_META exposes product panels without search skeleton", async () => {
  const mod = await loadSidePanelMode();
  const { SIDE_PANEL_META, FEATURE_PANEL_MODES } = mod;

  assert.equal(SIDE_PANEL_META.variables.label, "变量");
  assert.equal(SIDE_PANEL_META.variables.heading, "变量");
  assert.match(SIDE_PANEL_META.variables.ariaLabel, /变量/);

  assert.equal(SIDE_PANEL_META.help.label, "帮助");
  assert.equal(SIDE_PANEL_META.help.heading, "帮助");
  assert.match(SIDE_PANEL_META.help.ariaLabel, /帮助/);

  assert.equal(SIDE_PANEL_META.settings.label, "设置");
  assert.equal(SIDE_PANEL_META.settings.heading, "设置");
  assert.match(SIDE_PANEL_META.settings.ariaLabel, /设置/);

  assert.equal(SIDE_PANEL_META.search, undefined);
  assert.deepEqual(FEATURE_PANEL_MODES, ["variables", "help", "settings"]);
});

test("resolvePanelToggle opens, switches, and collapses like VS Code", async () => {
  const { resolvePanelToggle, resolvePanelVisibility } =
    await loadSidePanelMode();

  const initial = { open: true, mode: "notebook" };

  assert.deepEqual(resolvePanelToggle(initial, "notebook"), {
    open: false,
    mode: "notebook",
  });

  assert.deepEqual(
    resolvePanelToggle({ open: false, mode: "notebook" }, "variables"),
    { open: true, mode: "variables" },
  );

  assert.deepEqual(resolvePanelToggle(initial, "variables"), {
    open: true,
    mode: "variables",
  });

  assert.deepEqual(
    resolvePanelToggle({ open: true, mode: "help" }, "settings"),
    { open: true, mode: "settings" },
  );

  assert.deepEqual(
    resolvePanelVisibility({ open: true, mode: "variables" }, false),
    { open: false, mode: "variables" },
  );
});

test("shell source wires activity modes to real panel UI (no unfinished copy)", () => {
  const activityBar = readFileSync(
    path.join(root, "components/shell/ActivityBar.tsx"),
    "utf8",
  );
  const sidebar = readFileSync(
    path.join(root, "components/shell/NotebookSidebar.tsx"),
    "utf8",
  );
  const panels = readFileSync(
    path.join(root, "components/shell/panelSkeletons.tsx"),
    "utf8",
  );
  const statusBar = readFileSync(
    path.join(root, "components/shell/StatusBar.tsx"),
    "utf8",
  );
  const app = readFileSync(
    path.join(root, "components/NeoMathApp.tsx"),
    "utf8",
  );
  const canvas = readFileSync(
    path.join(root, "components/notebook/NotebookCanvas.tsx"),
    "utf8",
  );
  const demos = readFileSync(path.join(root, "lib/notebook/demos.ts"), "utf8");

  assert.doesNotMatch(activityBar, /showPending|后续版本提供|搜索/);
  assert.match(activityBar, /onSelectMode/);
  assert.match(activityBar, /变量/);
  assert.match(activityBar, /帮助/);
  assert.match(activityBar, /设置/);
  assert.match(activityBar, /data-activity/);

  assert.match(sidebar, /data-side-panel/);
  assert.match(sidebar, /SIDE_PANEL_META/);
  assert.match(sidebar, /openFile/);
  assert.match(sidebar, /createNewDerivation/);
  assert.match(sidebar, /工作区/);
  assert.match(sidebar, /VariablesPanel|HelpPanel|SettingsPanel/);
  assert.doesNotMatch(sidebar, /尚未实现/);

  assert.match(panels, /data-panel="variables"/);
  assert.match(panels, /data-panel="help"/);
  assert.match(panels, /data-panel="settings"/);
  assert.match(panels, /手动 Probe|四个演示|重新检测连接/);
  assert.doesNotMatch(panels, /后续版本|界面骨架|不会执行实际检索/);

  assert.doesNotMatch(canvas, /Mock Runtime/);
  // Kernel status chrome lives on the status bar (single place), not the canvas.
  assert.match(statusBar, /MathCore|离线演示/);
  // The demo catalog lives in the sidebar workspace, not a canvas wizard.
  assert.doesNotMatch(canvas, /empty-state-guide|data-empty-guide|listEmptyStateEntries/);

  assert.match(demos, /lost-root/);
  assert.match(demos, /extraneous-root/);
  assert.match(demos, /domain-expansion/);
  assert.match(demos, /semantic-completion/);

  assert.match(app, /resolvePanelToggle/);
  assert.match(app, /activeMode=\{panel\.mode\}/);
});
