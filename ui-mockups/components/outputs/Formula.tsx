"use client";

import katex from "katex";
import { toLatex, toPlainMath } from "@/lib/notebook/formula";

/**
 * Render a math formula with KaTeX. Accepts either already-converted TeX
 * (`latex`) or raw MathCore/editor source (`source`). Falls back to a
 * unicode plain form instead of dumping raw backslash commands on screen.
 */
export function Formula({
  latex,
  source,
  display = true,
  className = "",
}: {
  latex?: string;
  source?: string;
  display?: boolean;
  className?: string;
}) {
  const tex = latex && /\\[a-zA-Z]+/.test(latex)
    ? latex
    : latex
      ? toLatex(latex)
      : source
        ? toLatex(source)
        : "";
  const plain = toPlainMath(source || latex || tex);
  let html: string | null = null;

  if (tex) {
    try {
      html = katex.renderToString(tex, {
        displayMode: display,
        throwOnError: true,
        strict: "ignore",
        trust: false,
        output: "html",
      });
    } catch {
      // Retry once if the string was double-escaped (\\sqrt → \sqrt)
      try {
        const fixed = tex.replace(/\\\\([a-zA-Z]+)/g, "\\$1");
        if (fixed !== tex) {
          html = katex.renderToString(fixed, {
            displayMode: display,
            throwOnError: true,
            strict: "ignore",
            trust: false,
            output: "html",
          });
        }
      } catch {
        /* fall through */
      }
    }
  }

  if (html) {
    return (
      <div
        className={`formula-block ${display ? "" : "inline"} ${className}`.trim()}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }

  return (
    <div
      className={`formula-plain ${className}`.trim()}
      title={tex || undefined}
    >
      {plain || "—"}
    </div>
  );
}
