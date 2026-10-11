/**
 * XDLT RenderPatch protocol tests: replace / insert / remove /
 * replace-document, atomic fallback on missing target / bad index, and the
 * patched-DOM == full-render invariant. Uses a minimal DOM shim, no browser.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import path from "node:path";
import { readFileSync } from "node:fs";
import { fakeDom, element } from "./fakeDom.mjs";

const root = path.resolve(import.meta.dirname, "..");
const require = createRequire(import.meta.url);
const ts = require("typescript");

async function loadPatchRuntime() {
  const sourcePath = path.join(root, "lib/xdlt/patchRuntime.ts");
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

const dom = fakeDom();

const INITIAL = (
  '<article class="xdlt-document" data-xdlt-render-id="render:document">' +
  '<section data-xdlt-render-id="render:section:s1"><h1>标题</h1></section>' +
  '<div class="xdlt-equation" data-xdlt-id="eq:a"><math><mn>1</mn></math>' +
  '<span class="xdlt-equation-number">(1)</span></div>' +
  '<p data-xdlt-render-id="render:paragraph:aaa">一段</p>' +
  "</article>"
);

test("replace patch swaps the matching node in place", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const result = applyXdltPatches(
    root,
    [
      {
        op: "replace",
        renderId: "eq:a",
        html: '<div class="xdlt-equation" data-xdlt-id="eq:a"><math><mn>2</mn></math></div>',
      },
    ],
    {},
    dom,
  );
  assert.equal(result.ok, true);
  assert.equal(root.querySelectorAll('[data-xdlt-id="eq:a"]').length, 1);
  assert.match(root.innerHTML, /<mn>2<\/mn>/);
  assert.doesNotMatch(root.innerHTML, /<mn>1<\/mn>/);
});

test("remove patch deletes the target", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const result = applyXdltPatches(
    root,
    [{ op: "remove", renderId: "render:paragraph:aaa" }],
    {},
    dom,
  );
  assert.equal(result.ok, true);
  assert.equal(
    root.querySelectorAll('[data-xdlt-render-id="render:paragraph:aaa"]')
      .length,
    0,
  );
  assert.equal(root.querySelectorAll("[data-xdlt-render-id=\"render:paragraph:aaa\"]").length, 0);
});

test("insert patch appends at end when index == children length", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const section = root.children[0].children[0];
  const count = section.children.length;
  const result = applyXdltPatches(
    root,
    [
      {
        op: "insert",
        parentRenderId: "render:section:s1",
        index: count,
        html: '<p data-xdlt-render-id="render:paragraph:tail">末尾</p>',
      },
    ],
    {},
    dom,
  );
  assert.equal(result.ok, true);
  assert.equal(section.children.length, count + 1);
  assert.equal(
    section.children[count].getAttribute("data-xdlt-render-id"),
    "render:paragraph:tail",
  );
});

test("insert patch places node at the given index", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const section = root.children[0].children[0];
  const result = applyXdltPatches(
    root,
    [
      {
        op: "insert",
        parentRenderId: "render:section:s1",
        index: 0,
        html: '<p data-xdlt-render-id="render:paragraph:head">头部</p>',
      },
    ],
    {},
    dom,
  );
  assert.equal(result.ok, true);
  assert.equal(
    section.children[0].getAttribute("data-xdlt-render-id"),
    "render:paragraph:head",
  );
});

test("replace-document rebuilds the preview", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const full = '<article class="xdlt-document"><p>全新</p></article>';
  const result = applyXdltPatches(
    root,
    [{ op: "replace-document", html: full }],
    {},
    dom,
  );
  assert.equal(result.ok, true);
  assert.equal(root.innerHTML, full);
});

test("missing target triggers fallback with full render", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const full = '<article class="xdlt-document"><p>fallback</p></article>';
  let fallbackReason;
  const result = applyXdltPatches(
    root,
    [
      { op: "replace", renderId: "eq:missing", html: "<div></div>" },
      { op: "remove", renderId: "render:paragraph:aaa" },
    ],
    { fullHtml: full, onFallback: (reason) => (fallbackReason = reason) },
    dom,
  );
  assert.equal(result.ok, false);
  assert.equal(result.fallback, true);
  assert.ok(fallbackReason);
  // Atomic: recovered to the full render, not a half-updated state.
  assert.equal(root.innerHTML, full);
});

test("bad insert index triggers fallback", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const full = '<article class="xdlt-document"><p>fallback</p></article>';
  const result = applyXdltPatches(
    root,
    [
      {
        op: "insert",
        parentRenderId: "render:section:s1",
        index: 99,
        html: "<p></p>",
      },
    ],
    { fullHtml: full },
    dom,
  );
  assert.equal(result.ok, false);
  assert.equal(root.innerHTML, full);
});

test("empty patch set leaves the DOM untouched", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const before = root.innerHTML;
  const result = applyXdltPatches(root, [], {}, dom);
  assert.equal(result.ok, true);
  assert.equal(root.innerHTML, before);
});

test("top insertion patches only, never full DOM replacement", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const result = applyXdltPatches(
    root,
    [
      {
        op: "insert",
        parentRenderId: "render:document",
        index: 0,
        html: '<p data-xdlt-render-id="render:paragraph:new">插入</p>',
      },
    ],
    {},
    dom,
  );
  assert.equal(result.ok, true);
  // Existing anonymous nodes keep their identity (no avalanche).
  assert.equal(
    root.querySelectorAll('[data-xdlt-render-id="render:paragraph:aaa"]')
      .length,
    1,
  );
  assert.equal(
    root.querySelectorAll('[data-xdlt-id="eq:a"]').length,
    1,
  );
});

test("patched DOM equals a full render of the new document", async () => {
  const { applyXdltPatches } = await loadPatchRuntime();
  const root = element(INITIAL);
  const patches = [
    {
      op: "replace",
      renderId: "eq:a",
      html: '<div class="xdlt-equation" data-xdlt-id="eq:a"><math><mn>2</mn></math></div>',
    },
    {
      op: "remove",
      renderId: "render:paragraph:aaa",
    },
    {
      op: "insert",
      parentRenderId: "render:section:s1",
      index: 1,
      html: '<p data-xdlt-render-id="render:paragraph:new">新段</p>',
    },
  ];
  const result = applyXdltPatches(root, patches, {}, dom);
  assert.equal(result.ok, true);

  // Full render of the "new" document.
  const full = element(
    '<article class="xdlt-document" data-xdlt-render-id="render:document">' +
      '<section data-xdlt-render-id="render:section:s1"><h1>标题</h1>' +
      '<p data-xdlt-render-id="render:paragraph:new">新段</p></section>' +
      '<div class="xdlt-equation" data-xdlt-id="eq:a"><math><mn>2</mn></math></div>' +
      "</article>",
  );
  assert.equal(root.innerHTML, full.innerHTML);
});
