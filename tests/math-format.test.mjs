import test from "node:test"
import assert from "node:assert/strict"
import { toLatex, renderMath } from "../src/math-format.ts"
import { formatSet } from "../src/backend.ts"

test("display conversion preserves nested fractions, roots, powers and disjunctions", () => {
  assert.equal(toLatex("(x^2-1)/(x-1)=2"), "\\frac{x^{2} - 1}{x - 1} = 2")
  assert.equal(toLatex("sqrt(x+(1/2))=x-2"), "\\sqrt{x + \\left(\\frac{1}{2}\\right)} = x - 2")
  assert.equal(toLatex("x^(12)=1 or x=-1/2"), "x^{12} = 1 \\quad\\text{or}\\quad x = \\frac{-1}{2}")
  assert.equal(toLatex("-x^2"), "-x^{2}")
  assert.equal(toLatex("(-x)^2"), "\\left(-x\\right)^{2}")
  assert.equal(formatSet({ kind: "interval", lower: "0", upper: null, lowerInclusive: true, upperInclusive: true }), "[0, ∞)")
  for (const source of ["x(x − 1) = 0", "sqrt(sqrt(x)+1)=2", "x^(-12)=1", "{0, 1/2}", "ℝ \\ {0, 1}", "[0, 1]", "(−∞, ∞)", "∅", String.raw`\frac{x^2-1}{x-1}=2`]) {
    assert.equal(renderMath(source).error, null, source)
    assert.match(renderMath(source).html, /class="katex"/)
    assert.match(renderMath(source).html, /<math/)
  }
})
test("invalid editing input falls back and untrusted TeX cannot produce active HTML", () => {
  for (const source of ["x=", "sqrt(", "<script>alert(1)</script>", String.raw`\def\loop{\loop}\loop`]) assert.equal(renderMath(source).html, null, source)
  const unsafe = renderMath(String.raw`\href{javascript:alert(1)}{x}`)
  assert.ok(!unsafe.html || !unsafe.html.includes("href="))
})
