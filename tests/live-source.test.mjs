import { test } from "node:test"
import assert from "node:assert/strict"
import { editSource, sourceLines } from "../src/live-source.ts"

const cell = (id, source, kind = "math") => ({ id, source, kind, executionState: "success", outputCollapsed: false })
test("live source preserves equation IDs across inserted comments and changed suffix", () => {
  const original = [cell("a", "x*(x-1)=0"), cell("b", "x-1=0"), cell("c", "x=1")]
  const next = editSource(original, "x*(x-1)=0\n# divide\nx-1=0\nx=1")
  assert.equal(next[0].id, "a")
  assert.equal(next[2].id, "b")
  assert.equal(next[3].id, "c")
  assert.equal(next[1].kind, "markdown")
  assert.equal(next[1].source, "divide")
  assert.equal(new Set(next.map(c => c.id)).size, next.length)
  const changed = editSource(next, "x*(x-1)=0\n# divide\nx-1=0\nx=2")
  assert.equal(changed[3].id, "c")
  assert.equal(changed[3].executionState, "idle")
})
test("live source keeps multiline prose, blank rows and unchanged transform commands", () => {
  const original = [cell("intro", "intro\nsecond", "markdown"), cell("cmd", "factor", "transform")]
  const source = sourceLines(original).map(line => line.text).join("\n")
  const next = editSource(original, source + "\n\nx=1")
  assert.equal(sourceLines(next).map(line => line.text).join("\n"), source + "\n\nx=1")
  assert.equal(next[0].source, "intro\nsecond")
  assert.equal(next[0].id, "intro")
  assert.equal(next[1].kind, "transform")
  assert.equal(next[1].id, "cmd")
  assert.equal(new Set(next.map(c => c.id)).size, next.length)
})
test("rendering and unrelated edits retain original cell objects and metadata", () => {
  const original = [{ ...cell("a", "x=1"), custom: { preserved: true }, result: { old: true } }, cell("text", "first\nsecond", "markdown")]
  const source = sourceLines(original).map(line => line.text).join("\n")
  assert.equal(editSource(original, source), original)
  const next = editSource(original, source + "\nx=2")
  assert.equal(next[0], original[0])
  assert.deepEqual(next[1], original[1])
})
