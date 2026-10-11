/**
 * Phase A/B product paths: empty-state entries, Witness→Probe apply,
 * insert-repair + completions. Loads shipped TypeScript modules via the
 * same transpile bridge as side-panel-mode tests (no re-implementation).
 */
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import path from "node:path";
import { readFileSync } from "node:fs";

const root = path.resolve(import.meta.dirname, "..");
const require = createRequire(import.meta.url);
const ts = require("typescript");

async function loadTsModule(relativePath, importMap = {}) {
  const sourcePath = path.join(root, relativePath);
  let source = readFileSync(sourcePath, "utf8");
  // Rewrite relative TS imports to absolute file paths after transpile.
  // For multi-file graphs we inline a minimal shim for ./types and ./demos.
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
    },
    fileName: sourcePath,
  });
  let rewritten = outputText;
  for (const [from, to] of Object.entries(importMap)) {
    rewritten = rewritten
      .replaceAll(`from "${from}"`, `from "${to}"`)
      .replaceAll(`from '${from}'`, `from '${to}'`);
  }
  const dataUrl =
    "data:text/javascript;charset=utf-8," + encodeURIComponent(rewritten);
  return import(dataUrl);
}

async function loadWitnessProbe() {
  const typesPath = path.join(root, "lib/notebook/types.ts");
  const typesJs = ts.transpileModule(readFileSync(typesPath, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: typesPath,
  }).outputText;

  let src = readFileSync(path.join(root, "lib/notebook/witnessProbe.ts"), "utf8");
  src = src.replace(`from "./types"`, `from "__types__"`);
  const js = ts
    .transpileModule(src, {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: path.join(root, "lib/notebook/witnessProbe.ts"),
    })
    .outputText.replace(
      `from "__types__"`,
      `from "data:text/javascript;charset=utf-8,${encodeURIComponent(typesJs)}"`,
    );
  return import("data:text/javascript;charset=utf-8," + encodeURIComponent(js));
}

async function loadRepairFlow() {
  const typesPath = path.join(root, "lib/notebook/types.ts");
  const typesJs = ts.transpileModule(readFileSync(typesPath, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: typesPath,
  }).outputText;

  let src = readFileSync(path.join(root, "lib/notebook/repairFlow.ts"), "utf8");
  src = src.replace(`from "./types"`, `from "__types__"`);
  const js = ts
    .transpileModule(src, {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: path.join(root, "lib/notebook/repairFlow.ts"),
    })
    .outputText.replace(
      `from "__types__"`,
      `from "data:text/javascript;charset=utf-8,${encodeURIComponent(typesJs)}"`,
    );
  return import("data:text/javascript;charset=utf-8," + encodeURIComponent(js));
}

test("applyWitnessToProbe drives shipped parse + evaluator path", async () => {
  const { parseWitnessValue, applyWitnessToProbe, summarizeProbeResult } =
    await loadWitnessProbe();

  assert.equal(parseWitnessValue("x = 0"), "0");
  assert.equal(parseWitnessValue("1/2"), "1/2");
  assert.equal(parseWitnessValue("—"), null);
  assert.equal(parseWitnessValue(""), null);

  const calls = [];
  const result = await applyWitnessToProbe(async (value) => {
    calls.push(value);
    return {
      value,
      previousHolds: true,
      currentHolds: false,
      previousEval: "0 = 0　成立",
      currentEval: "−1 = 0　不成立",
      reason: "solutions_lost",
    };
  }, "x = 0");

  assert.equal(result.ok, true);
  assert.equal(result.value, "0");
  assert.deepEqual(calls, ["0"]);
  assert.equal(result.result.previousHolds, true);
  assert.equal(result.result.currentHolds, false);
  assert.match(summarizeProbeResult(result.result), /前式成立.*后式不成立/);

  const missing = await applyWitnessToProbe(async () => null, "x = 1");
  assert.equal(missing.ok, false);
  assert.ok(missing.error.length > 0);
});

test("buildRepairInsert surfaces completion preview as repair source", async () => {
  const { buildRepairInsert, selectRepairSuggestion } = await loadRepairFlow();

  const empty = buildRepairInsert([]);
  assert.equal(empty.source, "");
  assert.equal(empty.label, "修复推导");
  assert.equal(empty.suggestion, null);

  const completions = [
    { label: "因式分解", command: "factor" },
    {
      label: "因式分解",
      command: "factor",
      preview: "(x - 2)(x + 2) = 0",
    },
  ];
  const picked = selectRepairSuggestion(completions);
  assert.equal(picked?.preview, "(x - 2)(x + 2) = 0");

  const repair = buildRepairInsert(completions);
  assert.equal(repair.source, "(x - 2)(x + 2) = 0");
  assert.match(repair.label, /因式分解/);
  assert.equal(repair.suggestions.length, 2);
});

test("MockMathRuntime completions are used by repair selection (shipped offline path)", async () => {
  // Drive the real offline runtime getCompletions for the semantic-completion demo.
  const runtimePath = path.join(root, "lib/runtime/MockMathRuntime.ts");
  const typesPath = path.join(root, "lib/notebook/types.ts");
  const formulaPath = path.join(root, "lib/notebook/formula.ts");
  const transformsPath = path.join(root, "lib/notebook/transforms.ts");

  const typesJs = ts.transpileModule(readFileSync(typesPath, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: typesPath,
  }).outputText;

  const formulaJs = ts.transpileModule(readFileSync(formulaPath, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: formulaPath,
  }).outputText;

  let transformsSrc = readFileSync(transformsPath, "utf8");
  const transformsJs = ts.transpileModule(transformsSrc, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: transformsPath,
  }).outputText;

  let mockSrc = readFileSync(runtimePath, "utf8");
  mockSrc = mockSrc
    .replace(`from "@/lib/notebook/types"`, `from "__types__"`)
    .replace(`from "@/lib/notebook/formula"`, `from "__formula__"`)
    .replace(`from "@/lib/notebook/transforms"`, `from "__transforms__"`)
    .replace(`from "./MathRuntime"`, `from "__mathruntime__"`);

  // MathRuntime is types-only interface file — provide empty module.
  const mathRuntimeShim = "export {};";

  const mockJs = ts
    .transpileModule(mockSrc, {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: runtimePath,
    })
    .outputText.replace(
      `from "__types__"`,
      `from "data:text/javascript;charset=utf-8,${encodeURIComponent(typesJs)}"`,
    )
    .replace(
      `from "__formula__"`,
      `from "data:text/javascript;charset=utf-8,${encodeURIComponent(formulaJs)}"`,
    )
    .replace(
      `from "__transforms__"`,
      `from "data:text/javascript;charset=utf-8,${encodeURIComponent(transformsJs)}"`,
    )
    .replace(
      `from "__mathruntime__"`,
      `from "data:text/javascript;charset=utf-8,${encodeURIComponent(mathRuntimeShim)}"`,
    );

  const { MockMathRuntime } = await import(
    "data:text/javascript;charset=utf-8," + encodeURIComponent(mockJs)
  );
  const { buildRepairInsert } = await loadRepairFlow();

  const runtime = new MockMathRuntime();
  const completions = await runtime.getCompletions("x^2 - 4 = 0", 0);
  assert.ok(completions.length >= 1, "offline mock must offer factor completion");
  const repair = buildRepairInsert(completions);
  assert.ok(
    repair.source.includes("x") || repair.suggestion,
    "repair insert surfaces a suggested next step from shipped mock completions",
  );
  assert.ok(repair.suggestions.length >= 1);
});

test("UI source wires witness apply and insert repair", () => {
  const mathCell = readFileSync(
    path.join(root, "components/notebook/MathCell.tsx"),
    "utf8",
  );
  assert.match(mathCell, /applyWitnessProbe/);
  assert.match(mathCell, /一键代回/);
  assert.match(mathCell, /insertRepairCell/);

  const commands = readFileSync(
    path.join(root, "lib/notebook/commands.tsx"),
    "utf8",
  );
  assert.match(commands, /buildRepairInsert/);
  assert.match(commands, /applyWitnessToProbe/);
  assert.match(commands, /mathRuntime\.getCompletions/);
});
