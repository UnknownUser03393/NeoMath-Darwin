/**
 * Convert MathCore / editor source into KaTeX input and plain-text fallbacks.
 * Keep this pure — no DOM — so runtime + UI can share it.
 */

/** ASCII / MathCore source → KaTeX math mode string (single backslashes). */
export function toLatex(source: string): string {
  let s = source.trim();
  if (!s) return "";

  // Already looks like TeX commands — don't double-escape.
  if (/\\[a-zA-Z]+/.test(s)) {
    return s;
  }

  s = s
    .replace(/−/g, "-")
    .replace(/×/g, "*")
    .replace(/·/g, "*")
    .replace(/√\s*\(/g, "sqrt(")
    .replace(/√([a-zA-Z0-9]+)/g, "sqrt($1)");

  // Named functions BEFORE implicit multiplication (else sqrt( becomes sqr·().
  s = s.replace(/sqrt\(([^()]*)\)/gi, "\\sqrt{$1}");

  // x(y) → x \cdot (y) for display; skip if already a TeX command boundary.
  s = s.replace(/([0-9a-zA-Z)}\]])\s*\(/g, "$1 \\cdot (");

  s = s
    .replace(/\*/g, " \\cdot ")
    .replace(/\^\(([^()]*)\)/g, "^{$1}")
    .replace(/\^(-?\d+)/g, "^{$1}")
    .replace(/\bor\b/gi, "\\;\\text{或}\\;")
    .replace(/\s+/g, " ")
    .trim();

  return s;
}

/** Human-readable fallback when KaTeX cannot render. Never shows raw `\command`. */
export function toPlainMath(source: string): string {
  const supers: Record<string, string> = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "-": "⁻",
  };

  return source
    .trim()
    .replace(/\\cdot\s*/g, "·")
    .replace(/\\sqrt\{([^}]*)\}/g, "√($1)")
    .replace(/\\dfrac\{([^}]*)\}\{([^}]*)\}/g, "($1)/($2)")
    .replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, "($1)/($2)")
    .replace(/\\quad/g, "  ")
    .replace(/\\;\\text\{或\}\\;/g, " 或 ")
    .replace(/\\text\{([^}]*)\}/g, "$1")
    .replace(/\\/g, "")
    .replace(/\*/g, "·")
    .replace(/sqrt\(([^()]*)\)/gi, "√($1)")
    .replace(/\^(-?\d+)/g, (_, digits: string) =>
      [...digits].map((d) => supers[d] ?? d).join(""),
    )
    .replace(/\bor\b/gi, "或")
    .replace(/\s+/g, " ")
    .trim();
}
