import test from "node:test"
import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { mkdtemp, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import path from "node:path"
import { once } from "node:events"
import { MathSession } from "../src/math-session.ts"
import { XdltSession } from "../src/xdlt-session.ts"
import {
  call,
  compareProbe,
  formatSet,
  resolveSource,
  validNotebook,
} from "../src/backend.ts"

test("original NeoMath gateway: trace, witnesses, errors and notebook persistence", async () => {
  const directory = await mkdtemp(path.join(tmpdir(), "neomath-darwin-test-"))
  const root = process.env.NEOMATH_ROOT || "D:/Development/NeoMath"
  const process_ = spawn(
    process.env.NEOMATH_PYTHON || "python",
    [
      "-u",
      "-c",
      "from neomath.server import create_server; s,b,url=create_server(port=0,serve_notebook=False); print(url,flush=True); s.serve_forever()",
    ],
    {
      env: {
        ...process.env,
        PYTHONPATH: path.join(root, "desktop/src"),
        NEOMATH_DATA_DIR: directory,
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  )
  let stderr = ""
  process_.stderr.on("data", (data) => {
    stderr += data
  })
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error(`Backend startup timeout: ${stderr}`)),
        10000,
      )
      process_.once("error", (error) => {
        clearTimeout(timeout)
        reject(error)
      })
      process_.once("exit", (code) => {
        clearTimeout(timeout)
        reject(new Error(`Backend exit ${code}: ${stderr}`))
      })
      process_.stdout.on("data", (data) => {
        const match = String(data).match(/http:\/\/127\.0\.0\.1:\d+/)
        if (match) {
          clearTimeout(timeout)
          resolve(`${match[0]}/api`)
        }
      })
    })
    const rpc = (method, payload) => call(method, payload, url)
    const capabilities = await rpc("getCapabilities")
    assert.equal(capabilities.core, "C++20")
    const source = "x*(x-1)=0\nx-1=0\nx=1"
    const trace = await rpc("runTrace", { document: { source } })
    assert.deepEqual(
      trace.diagnostics.map((d) => d.status),
      ["valid", "root_fault", "tainted"],
    )
    assert.equal(formatSet(trace.states[0].solutionSet), "{0, 1}")
    assert.deepEqual(trace.relations[0].lostSolutions, ["0"])
    assert.equal(trace.relations[0].probe.currentPredicateResult, false)
    const probe = await rpc("evaluateProbe", {
      document: { source: source.split("\n").slice(0, 2).join("\n") },
      probe: { value: "0" },
    })
    assert.equal(compareProbe(probe).previousPredicateResult, true)
    assert.equal(compareProbe(probe).currentPredicateResult, false)
    const squared = await rpc("runTrace", {
      document: { source: "sqrt(x)=x-2\nx=(x-2)^2" },
    })
    assert.ok(squared.relations[0].gainedSolutions.length)
    const equivalent = await rpc("runTrace", {
      document: { source: "x-1=0\nx=1" },
    })
    assert.equal(equivalent.relations[0].relation, "equivalent")
    const mathSession = new MathSession()
    const cells = source.split("\n").map((source, i) => ({ id: String(i), kind: "math", source }))
    const full = await mathSession.evaluate(cells, undefined, url)
    assert.equal(full.method, "runTrace")
    const edited = cells.map((c, i) => i === 2 ? { ...c, source: "x-1=0" } : c)
    const replayed = await mathSession.evaluate(edited, undefined, url)
    assert.equal(replayed.method, "replay")
    assert.equal(replayed.changedStep, 2)
    assert.equal(replayed.metrics.cacheHits, 2)
    const invalid = await mathSession.evaluate(edited.map((c, i) => i === 1 ? { ...c, source: "x=" } : c), undefined, url)
    assert.equal(invalid.parsed.steps[1].error.code, "EXPECTED_EXPRESSION")
    const fixed = await mathSession.evaluate(edited, undefined, url)
    assert.equal(fixed.parsed.steps[1].error, null)
    assert.equal(fixed.trace.diagnostics[1].status, "root_fault")
    const aborted = new AbortController(); aborted.abort()
    await assert.rejects(mathSession.evaluate(edited, aborted.signal, url), /abort|cancel/i)
    const afterCancel = await mathSession.evaluate(edited, undefined, url)
    assert.equal(afterCancel.metrics.cacheHits, 3)
    const xdltSession = new XdltSession(url)
    const writing = "# Writing\n\nParagraph one.\n\n#assert:valid(using=sympy) {\nclaim x + 0 == x\n}\n"
    const initialWriting = await xdltSession.update(writing, { verify: true, execute: false })
    assert.match(initialWriting.html, /Paragraph one/)
    const updatedWriting = await xdltSession.update(writing.replace("one", "two"), { verify: true, execute: false })
    assert.match(updatedWriting.html, /Paragraph two/)
    assert.equal(updatedWriting.stats.reusedVerification, 1)
    assert.equal(updatedWriting.stats.reusedParsing, false)
    assert.ok(updatedWriting.htmlPatches.length)
    assert.equal(updatedWriting.previousRevision, initialWriting.revision)
    const sameWriting = await xdltSession.update(writing.replace("one", "two"), { verify: true, execute: false })
    assert.equal(sameWriting.stats.reusedParsing, true)
    await xdltSession.dispose()
    await assert.rejects(xdltSession.update(writing, { verify: true, execute: false }), /closed/)
    const resolved = await resolveSource(
      [
        { kind: "math", source: "x^2-x=0" },
        { kind: "transform", source: "因式分解" },
      ],
      url,
    )
    const transformed = await rpc("runTrace", {
      document: { source: resolved },
    })
    assert.equal(transformed.relations[0].relation, "equivalent")
    const unknown = await rpc("runTrace", { document: { source: "x^3=2" } })
    assert.equal(unknown.diagnostics[0].status, "unverified")
    const document = {
      id: "test",
      title: "Integration",
      fileName: "test.nm",
      cells: [
        {
          id: "1",
          kind: "math",
          source: "x=1",
          executionState: "idle",
          outputCollapsed: false,
        },
      ],
      updatedAt: Date.now(),
      darwinInk: [
        [
          [1, 2],
          [3, 4],
        ],
      ],
    }
    assert.equal(validNotebook(document), true)
    assert.equal(validNotebook({ ...document, darwinInk: [[[NaN, 2]]] }), false)
    await rpc("saveNotebook", { name: "test.nm", document })
    assert.deepEqual(
      (await rpc("loadNotebook", { name: "test.nm" })).document,
      document,
    )
    assert.equal((await rpc("listNotebooks")).files[0].title, "Integration")
    await assert.rejects(
      rpc("loadNotebook", { name: "missing.nm" }),
      /notebook not found/,
    )
    await assert.rejects(
      rpc("saveNotebook", { name: "bad" }),
      /document object required/,
    )
  } finally {
    const stopped = once(process_, "exit")
    if (process_.exitCode === null) {
      process_.kill()
      await stopped
    }
    await rm(directory, { recursive: true, force: true })
  }
})
