import test from "node:test"
import assert from "node:assert/strict"
import { parseRational, frStr, steps, relationForStep } from "../src/data.ts"
import { inkReducer, eraseAt } from "../src/ink.ts"
import { readFileSync } from "node:fs"

test("Probe preserves exact integers beyond IEEE-754 precision", () => {
  const x = parseRational("99999999999")
  assert.equal(frStr(steps[0].evaluate(x).left), "9999999999700000000002")
  assert.equal(frStr(steps[1].evaluate(x).left), "99999999998")
  assert.equal(frStr(parseRational("9007199254740993")), "9007199254740993")
})

test("rational normalization and witness evaluation", () => {
  assert.equal(frStr(parseRational(" −12/24 ")), "−1/2")
  assert.equal(frStr(steps[0].evaluate(parseRational("−1/2")).left), "3/4")
  assert.equal(parseRational("1/0"), null)
  assert.equal(parseRational("1.5"), null)
  assert.equal(steps[0].evaluate(parseRational("0")).holds, true)
  assert.equal(steps[1].evaluate(parseRational("0")).holds, false)
  assert.equal(relationForStep(1), null)
  assert.equal(relationForStep(3).id, 23)
})

test("stroke and erase are separate undoable transactions; new edits discard redo", () => {
  const stroke = [
    [
      [0, 0],
      [100, 0],
    ],
  ]
  let history = inkReducer({ past: [], present: [], future: [] }, {
    type: "commit",
    strokes: stroke,
  })
  const erased = eraseAt(history.present, [50, 3], 5)
  assert.deepEqual(erased, []) // Segment intersection, not only sampled points.
  history = inkReducer(history, { type: "commit", strokes: erased })
  history = inkReducer(history, { type: "undo" })
  assert.deepEqual(history.present, stroke)
  history = inkReducer(history, { type: "redo" })
  assert.deepEqual(history.present, [])
  history = inkReducer(history, { type: "undo" })
  history = inkReducer(history, {
    type: "commit",
    strokes: [...stroke, [[20, 30]]],
  })
  assert.deepEqual(history.future, [])
  assert.equal(eraseAt(history.present, [1000, 1000], 5), history.present)
})

test("semantic text tokens meet 4.5:1 on reading surfaces in both themes", () => {
  const css = readFileSync(new URL("../src/index.css", import.meta.url), "utf8")
  const luminance = (hex) => {
    const rgb = hex
      .match(/[a-f0-9]{2}/gi)
      .map((h) => parseInt(h, 16) / 255)
      .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
  }
  for (const selector of [":root", "[data-theme='dark']"]) {
    const block = css.slice(css.indexOf(selector)).split("}")[0]
    const tokens = Object.fromEntries(
      [...block.matchAll(/--([\w-]+):\s*(#[a-f0-9]{6})/gi)].map((m) => [
        m[1],
        m[2],
      ]),
    )
    for (const name of [
      "label-primary",
      "label-secondary",
      "label-tertiary",
      "status-verified",
      "status-caution",
      "status-fault",
      "status-neutral",
    ]) {
      for (const surface of [
        "surface-canvas",
        "surface-panel",
        "surface-subtle",
      ]) {
        const a = luminance(tokens[name]),
          b = luminance(tokens[surface])
        const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
        assert.ok(ratio >= 4.5, `${selector}: ${name} on ${surface}: ${ratio}`)
      }
    }
  }
})
