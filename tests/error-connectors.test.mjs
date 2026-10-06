import { test } from "node:test"
import assert from "node:assert/strict"
import { connectorPath, errorDependencies } from "../src/error-connectors.ts"

test("tainted steps belong to their fault source; clean steps break propagation", () => {
  assert.deepEqual(errorDependencies(["valid", "root_fault", "tainted", "tainted", "valid", "tainted", "parse_error", "tainted"]), [{ parent: 1, child: 2 }, { parent: 1, child: 3 }, { parent: 6, child: 7 }])
})
test("one parent trunk ends at the last rounded branch; intermediate children only own branches", () => {
  const geometry = new Map([[0, { cx: 10, cy: 10, left: 8 }], [1, { cx: 60, cy: 40, left: 56 }], [2, { cx: 60, cy: 80, left: 56 }]])
  assert.equal(connectorPath([{ parent: 0, child: 2 }, { parent: 0, child: 1 }], geometry), "M 22 10 H 10 V 68 Q 10 80 22 80 H 48 M 10 28 Q 10 40 22 40 H 48")
})
test("tight spacing limits radius and missing/reversed anchors cannot generate loops", () => {
  const geometry = new Map([[0, { cx: 10, cy: 10, left: 8 }], [1, { cx: 26, cy: 13, left: 24 }], [2, { cx: 8, cy: 20, left: 6 }], [3, { cx: 30, cy: 5, left: 28 }]])
  assert.equal(connectorPath([{ parent: 0, child: 1 }, { parent: 0, child: 2 }, { parent: 0, child: 3 }, { parent: 0, child: 4 }], geometry), "M 16 10 H 10 V 10 Q 10 13 13 13 H 16")
})
