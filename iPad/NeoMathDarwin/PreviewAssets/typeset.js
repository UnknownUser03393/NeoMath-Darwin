function mathmlToLatex(node) {
  const children = [...node.children]
  const parts = children.map(mathmlToLatex)
  const text = node.textContent ?? ""
  const safeText = text.replace(/[\\{}$%&#_^]/g, character => `\\${character}`)
  switch (node.localName) {
    case "math": case "mrow": return parts.join(" ")
    case "mn": return text
    case "mi": return /^(alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|phi|omega)$/.test(text) ? `\\${text}` : /^[a-zA-Z]$/.test(text) ? text : `\\operatorname{${safeText}}`
    case "mo": return ({ "−": "-", "⁢": "\\,", "∕": "/", "∑": "\\sum", "∏": "\\prod", "∫": "\\int", "≤": "\\le", "≥": "\\ge", "≠": "\\ne", "∞": "\\infty" })[text] ?? text
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

window.neomathTypeset = function(root) {
  for (const math of root.querySelectorAll("math, .xdlt-math-opaque[data-latex]")) {
    if (math.closest(".katex")) continue;
    try {
      const latex = math.getAttribute("data-latex") || mathmlToLatex(math);
      const span = document.createElement("span"); span.className = "math-render";
      span.innerHTML = katex.renderToString(latex, { displayMode: !!math.closest(".xdlt-equation"), output: "htmlAndMathml", throwOnError: true, trust: false, strict: "ignore", maxExpand: 100, maxSize: 20 });
      math.replaceWith(span);
    } catch (_) { }
  }
};
window.neomathTypeset(document);
