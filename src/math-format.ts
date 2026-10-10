import katex from "katex"

type Expression = { tex: string; inner?: string }

/** Display-only parsing. MathCore source remains unchanged. */
export function toLatex(source: string): string {
  let raw = source.trim().replace(/^\$\$([\s\S]*)\$\$$/, "$1").replace(/^\$([\s\S]*)\$$/, "$1")
  if (!raw || raw === "—" || raw === "Unverified") throw new Error("No formula")
  if (/\\[a-zA-Z]+/.test(raw)) return raw
  raw = raw.replace(/[−–]/g, "-").replace(/[×·⋅]/g, "*").replace(/÷/g, "/").replace(/√/g, "sqrt")
  const excluded = raw.match(/^ℝ\s*\\\s*\{(.*)\}$/)
  if (excluded) return `\\mathbb{R} \\setminus \\left\\{${excluded[1].split(",").map(toLatex).join(",\\,")}\\right\\}`
  const interval = raw.match(/^([\[(])([^,]+),([^,]+)([\])])$/)
  if (interval) return `\\left${interval[1]}${toLatex(interval[2])},\\,${toLatex(interval[3])}\\right${interval[4]}`
  if (raw.includes("ℝ") || raw.includes("∅") || raw.includes("∞")) return raw.replace(/ℝ/g, "\\mathbb{R}").replace(/∅/g, "\\varnothing").replace(/∞/g, "\\infty")
  if (/^\{.*\}$/.test(raw)) return `\\left\\{${raw.slice(1, -1).split(",").map(value => toLatex(value)).join(",\\,")}\\right\\}`
  const tokens = raw.match(/[a-zA-Z_][a-zA-Z_0-9]*|(?:\d+(?:\.\d*)?|\.\d+)|>=|<=|!=|[+\-±∓*/^()=<>≥≤≠]/g) ?? []
  if (tokens.join("") !== raw.replace(/\s/g, "")) throw new Error("Unsupported formula notation")
  let index = 0
  const peek = () => tokens[index]
  const take = () => tokens[index++]
  const expect = (token: string) => { if (take() !== token) throw new Error("Incomplete formula") }
  const atom = (): Expression => {
    const token = take()
    if (token === "(") {
      const inside = expression()
      expect(")")
      return { tex: `\\left(${inside.tex}\\right)`, inner: inside.tex }
    }
    if (token === "sqrt") {
      const radicand = atom()
      return { tex: `\\sqrt{${radicand.inner ?? radicand.tex}}` }
    }
    if (["sin", "cos", "tan", "asin", "acos", "atan", "exp", "log", "ln", "abs"].includes(token)) {
      expect("(")
      const argument = expression().tex
      expect(")")
      if (token === "abs") return { tex: `\\left|${argument}\\right|` }
      const name = ({ asin: "arcsin", acos: "arccos", atan: "arctan" } as Record<string, string>)[token] ?? token
      return { tex: `\\${name}\\left(${argument}\\right)` }
    }
    if (token === "pi") return { tex: "\\pi" }
    if (token && /^(?:\d+(?:\.\d*)?|\.\d+|[a-zA-Z_][a-zA-Z_0-9]*)$/.test(token)) return { tex: token.replace(/_/g, "\\_") }
    throw new Error("Incomplete formula")
  }
  const power = (): Expression => {
    const base = atom()
    if (peek() !== "^") return base
    take()
    const exponent = unary()
    return { tex: `${base.tex}^{${exponent.inner ?? exponent.tex}}` }
  }
  const unary = (): Expression => {
    if (["-", "+", "±", "∓"].includes(peek())) { const sign = take(); return { tex: `${sign === "±" ? "\\pm " : sign === "∓" ? "\\mp " : sign}${unary().tex}` } }
    return power()
  }
  const product = (): Expression => {
    let left = unary()
    while (peek() === "*" || peek() === "/" || peek() === "(" || peek() === "sqrt" || /^[a-zA-Z_0-9.]/.test(peek() ?? "") && peek() !== "or") {
      const operation = peek() === "*" || peek() === "/" ? take() : "implicit"
      const right = unary()
      left = { tex: operation === "/" ? `\\frac{${left.inner ?? left.tex}}{${right.inner ?? right.tex}}` : `${left.tex}${operation === "*" ? " \\cdot " : "\\,"}${right.tex}` }
    }
    return left
  }
  const expression = (): Expression => {
    let left = product()
    while (["+", "-", "±", "∓"].includes(peek())) { const operation = take(); left = { tex: `${left.tex} ${operation === "±" ? "\\pm" : operation === "∓" ? "\\mp" : operation} ${product().tex}` } }
    return left
  }
  const relation = () => {
    let tex = expression().tex
    const operators: Record<string, string> = { "=": "=", "<": "<", ">": ">", ">=": "\\ge", "<=": "\\le", "!=": "\\ne", "≥": "\\ge", "≤": "\\le", "≠": "\\ne" }
    while (operators[peek()]) { const operator = take(); tex += ` ${operators[operator]} ${expression().tex}` }
    return tex
  }
  let tex = relation()
  while (peek() === "or") { take(); tex += ` \\quad\\text{or}\\quad ${relation()}` }
  if (index !== tokens.length) throw new Error("Incomplete formula")
  return tex
}
export function renderMath(source: string, displayMode = false) {
  try {
    const latex = toLatex(source)
    return { html: katex.renderToString(latex, { displayMode, output: "htmlAndMathml", throwOnError: true, trust: false, strict: "ignore", maxExpand: 100, maxSize: 20 }), latex, error: null }
  } catch (error) { return { html: null, latex: null, error: (error as Error).message } }
}
/** Convert the original XDLT MathML output for the same KaTeX visual renderer. */
export function mathmlToLatex(node: Element): string {
  const children = [...node.children]
  const parts = children.map(mathmlToLatex)
  const text = node.textContent ?? ""
  const safeText = text.replace(/[\\{}$%&#_^]/g, character => `\\${character}`)
  switch (node.localName) {
    case "math": case "mrow": return parts.join(" ")
    case "mn": return text
    case "mi": return /^(alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|phi|omega)$/.test(text) ? `\\${text}` : /^[a-zA-Z]$/.test(text) ? text : `\\operatorname{${safeText}}`
    case "mo": return ({ "−": "-", "⁢": "\\,", "∕": "/", "∑": "\\sum", "∏": "\\prod", "∫": "\\int", "≤": "\\le", "≥": "\\ge", "≠": "\\ne", "∞": "\\infty" } as Record<string, string>)[text] ?? text
    case "mtext": return `\\text{${safeText}}`
    case "mfrac": return `\\frac{${parts[0]}}{${parts[1]}}`
    case "msqrt": return `\\sqrt{${parts.join(" ")}}`
    case "mroot": return `\\sqrt[${parts[1]}]{${parts[0]}}`
    case "msup": return `${children[0]?.localName === "mrow" ? `\\left(${parts[0]}\\right)` : `{${parts[0]}}`}^{${parts[1]}}`
    case "msub": return `{${parts[0]}}_{${parts[1]}}`
    case "msubsup": case "munderover": return `{${parts[0]}}_{${parts[1]}}^{${parts[2]}}`
    case "munder": return `{${parts[0]}}_{${parts[1]}}`
    case "mover": return `\\overset{${parts[1]}}{${parts[0]}}`
    case "mfenced": return `\\left${node.getAttribute("open") ?? "("}${parts.join(", ")}\\right${node.getAttribute("close") ?? ")"}`
    default: throw new Error(`Unsupported MathML: ${node.localName}`)
  }
}
export function typesetXdlt(root: HTMLElement) {
  for (const math of root.querySelectorAll("math, .xdlt-math-opaque[data-latex]")) {
    if (math.closest(".katex")) continue
    try {
      const latex = math.getAttribute("data-latex") ?? mathmlToLatex(math)
      const result = renderMath(/\\[a-zA-Z]/.test(latex) ? latex : `\\displaystyle ${latex}`, !!math.closest(".xdlt-equation"))
      if (!result.html) continue
      const span = root.ownerDocument.createElement("span")
      span.className = "math-render"
      span.dataset.mathSource = latex
      span.innerHTML = result.html
      math.replaceWith(span)
    } catch { /* Preserve the backend's native MathML or source fallback. */ }
  }
}
