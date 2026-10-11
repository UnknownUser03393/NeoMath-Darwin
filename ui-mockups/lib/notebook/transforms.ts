/**
 * Structured algebraic operations — the only safe way to *apply* a transform.
 * Free Chinese like「两边除以10」is display copy at most, never the source of truth.
 */

export type TransformOp =
  | "factor"
  | "expand"
  | "move_terms"
  | "divide"
  | "multiply"
  | "square_both_sides"
  | "solve";

export interface TransformSpec {
  op: TransformOp;
  /** Short chip label */
  label: string;
  /** Whether the op needs a math expression argument (ASCII/rational) */
  needsArg: boolean;
  /** Placeholder for the argument field */
  argPlaceholder?: string;
  /** Hint under the chip */
  hint: string;
}

export const TRANSFORM_CATALOG: TransformSpec[] = [
  {
    op: "factor",
    label: "因式分解",
    needsArg: false,
    hint: "把多项式写成乘积形式",
  },
  {
    op: "expand",
    label: "展开",
    needsArg: false,
    hint: "展开括号",
  },
  {
    op: "square_both_sides",
    label: "平方",
    needsArg: false,
    hint: "对等式两边同时平方（可能增根）",
  },
  {
    op: "divide",
    label: "除以",
    needsArg: true,
    argPlaceholder: "x 或 10 或 x-1",
    hint: "参数必须是数学式，不是中文",
  },
  {
    op: "multiply",
    label: "乘以",
    needsArg: true,
    argPlaceholder: "x 或 2",
    hint: "参数必须是数学式，不是中文",
  },
  {
    op: "move_terms",
    label: "移项整理",
    needsArg: false,
    hint: "移项并整理为一边为零",
  },
  {
    op: "solve",
    label: "求解",
    needsArg: false,
    hint: "在当前能力内解方程",
  },
];

/** Human-readable badge for a step, e.g. 「两边 ÷ x」 */
export function formatTransformLabel(op: TransformOp, arg?: string): string {
  const trimmed = arg?.trim();
  switch (op) {
    case "factor":
      return "操作 · 因式分解";
    case "expand":
      return "操作 · 展开";
    case "move_terms":
      return "操作 · 移项";
    case "square_both_sides":
      return "操作 · 平方";
    case "solve":
      return "操作 · 求解";
    case "divide":
      return trimmed ? `操作 · 除以 (${trimmed})` : "操作 · 除以";
    case "multiply":
      return trimmed ? `操作 · 乘以 (${trimmed})` : "操作 · 乘以";
  }
}

/** Intent payload for MathCore executeTransformation — no NLP. */
export function toCoreIntent(
  op: TransformOp,
  arg?: string,
): { intent: string; confidence: number; arguments: Record<string, string> } {
  const arguments_: Record<string, string> = {};
  if ((op === "divide" || op === "multiply") && arg?.trim()) {
    arguments_.expression = arg.trim();
  }
  return {
    intent: op,
    confidence: 1,
    arguments: arguments_,
  };
}

/** Normalize user arg: strip Chinese wrappers, keep math. */
export function normalizeTransformArg(raw: string): string {
  return raw
    .trim()
    .replace(/^[两边同]*[除乘以×÷\/\*]+/u, "")
    .replace(/[。.!！\s]+$/u, "")
    .trim();
}
