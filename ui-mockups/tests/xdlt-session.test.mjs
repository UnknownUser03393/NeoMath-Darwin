/**
 * XDLT session manager tests: debounced updates, stale-response discarding,
 * and lifecycle (create/destroy). Uses an injectable mock bridge; no server.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import path from "node:path";
import { readFileSync } from "node:fs";

const root = path.resolve(import.meta.dirname, "..");
const require = createRequire(import.meta.url);
const ts = require("typescript");

async function loadSession() {
  const sourcePath = path.join(root, "lib/xdlt/session.ts");
  const source = readFileSync(sourcePath, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
    },
    fileName: sourcePath,
  });
  // Rewrite the default bridge import to a stub; tests inject their own.
  const stub =
    "data:text/javascript;charset=utf-8," + encodeURIComponent("export const xdltBridge = {};");
  let rewritten = outputText.replaceAll('from "./bridge"', `from "${stub}"`);
  rewritten = rewritten.replaceAll("from './bridge'", `from '${stub}'`);
  const dataUrl =
    "data:text/javascript;charset=utf-8," + encodeURIComponent(rewritten);
  return import(dataUrl);
}

function deferred() {
  let resolve;
  const promise = new Promise((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

const EMPTY_RESULT = {
  html: "<article></article>",
  diagnostics: [],
  sourceMap: [],
  renderDocument: {},
  graph: {},
};
const EMPTY_INCREMENTAL = {
  ...EMPTY_RESULT,
  patches: [],
  htmlPatches: [],
  invalidatedSemanticIds: [],
  stats: {
    reusedVerification: 0,
    recomputedVerification: 0,
    reusedExecution: 0,
    recomputedExecution: 0,
    reusedParsing: true,
    patchFallback: false,
  },
};

function makeBridge() {
  const calls = [];
  const gates = [];
  const bridge = {
    calls,
    gates,
    async createSession() {
      calls.push(["create"]);
      return { sessionId: "s1", result: EMPTY_RESULT };
    },
    updateSession(_sessionId, content) {
      calls.push(["update", content]);
      const gate = deferred();
      gates.push(gate);
      return gate.promise.then(() => ({
        sessionId: "s1",
        result: EMPTY_INCREMENTAL,
      }));
    },
    async destroySession() {
      calls.push(["destroy"]);
    },
  };
  return bridge;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test("open creates a session and reports a full compile", async () => {
  const { XdltSessionManager } = await loadSession();
  const bridge = makeBridge();
  let compiled = false;
  const manager = new XdltSessionManager(
    { onCompile: () => (compiled = true), onUpdate: () => {}, onError: () => {} },
    0,
    bridge,
  );
  await manager.open("a");
  assert.equal(manager.isOpen, true);
  assert.equal(manager.id, "s1");
  assert.deepEqual(bridge.calls[0], ["create"]);
  assert.equal(compiled, true);
  await manager.close();
  assert.equal(bridge.calls.at(-1)[0], "destroy");
  assert.equal(manager.isOpen, false);
});

test("rapid edits collapse to a single debounced update", async () => {
  const { XdltSessionManager } = await loadSession();
  const bridge = makeBridge();
  const updates = [];
  const manager = new XdltSessionManager(
    { onCompile: () => {}, onUpdate: (_r, meta) => updates.push(meta.revision), onError: () => {} },
    5,
    bridge,
  );
  await manager.open("a");
  manager.edit("b");
  manager.edit("c");
  manager.edit("d");
  await sleep(40);
  await bridge.gates[0].resolve();
  await sleep(5);
  assert.equal(bridge.calls.filter(([kind]) => kind === "update").length, 1);
  assert.deepEqual(bridge.calls.at(-1), ["update", "d"]);
  assert.deepEqual(updates, [5]);
  await manager.close();
});

test("stale response is discarded when a newer edit supersedes it", async () => {
  const { XdltSessionManager } = await loadSession();
  const bridge = makeBridge();
  const updates = [];
  const manager = new XdltSessionManager(
    { onCompile: () => {}, onUpdate: (_r, meta) => updates.push(meta.revision), onError: () => {} },
    0,
    bridge,
  );
  await manager.open("a");
  manager.edit("b"); // rev 1, fires quickly
  await sleep(15);
  manager.edit("c"); // rev 2
  await sleep(15);
  assert.equal(bridge.gates.length, 2);
  // Resolve the OLD update (rev 1) late: it must be discarded.
  bridge.gates[0].resolve();
  await sleep(5);
  assert.deepEqual(updates, []);
  // Resolve the new update (rev 2): it is delivered.
  bridge.gates[1].resolve();
  await sleep(5);
  assert.deepEqual(updates, [4]);
  await manager.close();
});

test("identical content update reports zero patches", async () => {
  const { XdltSessionManager } = await loadSession();
  const bridge = makeBridge();
  let lastPatches = null;
  const manager = new XdltSessionManager(
    {
      onCompile: () => {},
      onUpdate: (result) => (lastPatches = result.htmlPatches),
      onError: () => {},
    },
    0,
    bridge,
  );
  await manager.open("a");
  manager.edit("a");
  await sleep(15);
  bridge.gates[0].resolve();
  await sleep(5);
  assert.deepEqual(lastPatches, []);
  await manager.close();
});

test("flush forces an update immediately", async () => {
  const { XdltSessionManager } = await loadSession();
  const bridge = makeBridge();
  const manager = new XdltSessionManager(
    { onCompile: () => {}, onUpdate: () => {}, onError: () => {} },
    5_000,
    bridge,
  );
  await manager.open("a");
  const flushing = manager.flush("b");
  assert.equal(bridge.calls.filter(([kind]) => kind === "update").length, 1);
  bridge.gates[0].resolve();
  await flushing;
  assert.deepEqual(bridge.calls.at(-1), ["update", "b"]);
  await manager.close();
});

test("open routes a failed create through onError (no unhandled rejection)", async () => {
  const { XdltSessionManager } = await loadSession();
  const bridge = {
    async createSession() {
      throw new Error("offline");
    },
    async updateSession() {
      throw new Error("offline");
    },
    async destroySession() {},
  };
  let errored = null;
  let compiled = false;
  const manager = new XdltSessionManager(
    {
      onCompile: () => (compiled = true),
      onUpdate: () => {},
      onError: (error) => (errored = error),
    },
    0,
    bridge,
  );
  await manager.open("a");
  assert.equal(compiled, false, "no compile when the session cannot be created");
  assert.equal(manager.isOpen, false, "session stays closed after a failed open");
  assert.ok(errored, "the failure reaches onError instead of rejecting");
  assert.equal(errored.message, "offline");
  await manager.close();
});
