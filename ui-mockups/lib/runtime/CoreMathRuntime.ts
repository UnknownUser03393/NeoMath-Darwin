import type {
  CompletionItem,
  DiagnosticResult,
  EquivalenceResult,
  ExecutionContext,
  ExecutionResult,
  KernelStatus,
  MathCell,
  MathResult,
  ProbeRequest,
  ProbeResult,
  UnsupportedResult,
} from "@/lib/notebook/types";
import { toLatex } from "@/lib/notebook/formula";
import {
  toCoreIntent,
  type TransformOp,
} from "@/lib/notebook/transforms";
import type { MathRuntime, StructuredTransformResult } from "./MathRuntime";

const DEFAULT_CORE_URL = "http://127.0.0.1:8765";

/**
 * Resolve the MathCore HTTP base URL.
 * - Desktop AOT notebook injects `window.__NEOMATH_CORE_URL__ = ""` for same-origin.
 * - Dev SPA can leave it unset and fall back to the local gateway.
 */
export const coreUrl = (): string => {
  if (typeof window === "undefined") {
    return DEFAULT_CORE_URL;
  }
  const injected = (window as unknown as { __NEOMATH_CORE_URL__?: string })
    .__NEOMATH_CORE_URL__;
  if (typeof injected === "string") {
    return injected;
  }
  if ((window as unknown as { __NEOMATH_EMBEDDED__?: boolean }).__NEOMATH_EMBEDDED__) {
    return "";
  }
  return DEFAULT_CORE_URL;
};

// --- C++ MathCore response shapes (see desktop/docs/PYBIND_API.md) ---

interface CoreSolutionSet {
  kind?: string;
  values?: string[];
  excluded?: string[];
  lower?: string | null;
  upper?: string | null;
}

interface CoreState {
  source?: string;
  canonical?: string;
  domain?: CoreSolutionSet;
  solutionSet?: CoreSolutionSet;
  trustLevel?: string;
  verificationStatus?: string;
}

interface CoreRelation {
  relation?: string;
  lostSolutions?: string[];
  gainedSolutions?: string[];
  domainExpanded?: boolean;
  domainShrunk?: boolean;
  reason?: string;
}

interface CoreDiagnostic {
  status?: string;
  title?: string;
  message?: string;
}

interface CoreProbe {
  value?: string;
  previousDefined?: boolean;
  currentDefined?: boolean;
  previousPredicateResult?: boolean;
  currentPredicateResult?: boolean;
  previousLeftValue?: string;
  previousRightValue?: string;
  currentLeftValue?: string;
  currentRightValue?: string;
  reason?: string;
}

interface CoreEnvelope<TResult> {
  ok: boolean;
  result?: TResult;
  metrics?: { durationMs?: number; cacheHits?: number };
  error?: { type?: string; code?: string; message?: string };
}

interface TraceResult {
  states?: CoreState[];
  relations?: CoreRelation[];
  diagnostics?: CoreDiagnostic[];
  activeProbe?: CoreProbe | null;
  breakpointStep?: number;
}

interface TransformationResult {
  applied?: boolean;
  source?: string;
  reason?: string;
}

const formatSet = (set?: CoreSolutionSet): string => {
  if (!set) return "—";
  switch (set.kind) {
    case "finite":
      return `{ ${(set.values ?? []).join(", ")} }`;
    case "empty":
      return "∅";
    case "all_real":
      return "ℝ";
    case "all_real_excluding_finite":
    case "real_excluding_finite":
      return `ℝ \\ { ${(set.excluded ?? []).join(", ")} }`;
    case "interval": {
      const lo = set.lower;
      const hi = set.upper;
      if (lo != null && hi == null) return `x ≥ ${lo}`;
      if (lo == null && hi != null) return `x ≤ ${hi}`;
      if (lo != null && hi != null) return `${lo} ≤ x ≤ ${hi}`;
      return "ℝ";
    }
    default:
      return "暂时无法验证";
  }
};

const REASON_MESSAGES: Record<string, string> = {
  solutions_lost: "这一步丢失了原来成立的解。",
  solutions_gained: "这一步加入了原方程不成立的新解。",
  domain_expanded: "这一步把原来没有定义的值纳入了范围。",
  domain_shrunk: "这一步排除了原来有定义的值。",
  solution_set_and_domain_preserved: "解集和定义域保持不变。",
  one_or_both_steps_unverified: "当前版本暂时无法证明这两步的关系。",
  solver_supports_degree_at_most_two: "当前版本只验证一次和二次方程。",
  square_root_form_not_supported: "当前版本暂不支持这种根式结构。",
  parse_error: "这一步需要先修正输入格式。",
  INTEGER_OVERFLOW:
    "精确有理数运算超出 64 位整数范围（INTEGER_OVERFLOW）。请改用更小的中间量，或把推导拆成多步。",
  DIVISION_BY_ZERO: "出现了除以零（DIVISION_BY_ZERO），该步在当前定义下无意义。",
};

const friendlyReason = (code?: string) =>
  (code && REASON_MESSAGES[code]) || code || "当前步骤已检查";

const unsupported = (title: string, message: string): UnsupportedResult => ({
  type: "unsupported",
  title,
  message,
});

/** Best-effort map from old short keywords → structured op (not free prose). */
function mapLegacyCommand(
  command: string,
): { op: TransformOp; arg?: string } | null {
  const raw = command.trim();
  const lowered = raw.toLowerCase();
  if (/因式|factor/i.test(raw)) return { op: "factor" };
  if (/展开|expand/i.test(raw)) return { op: "expand" };
  if (/平方|square/i.test(raw)) return { op: "square_both_sides" };
  if (/移项|move/i.test(raw)) return { op: "move_terms" };
  if (/求解|solve/i.test(raw)) return { op: "solve" };
  const div = raw.match(/(?:除以|divide(?:\s+by)?)\s*(.+)$/i);
  if (div) return { op: "divide", arg: div[1].trim() };
  if (lowered === "/x" || lowered === "÷x") return { op: "divide", arg: "x" };
  const mul = raw.match(/(?:乘以|multiply(?:\s+by)?)\s*(.+)$/i);
  if (mul) return { op: "multiply", arg: mul[1].trim() };
  return null;
}

const evaluation = (
  defined: boolean | undefined,
  holds: boolean | undefined,
  left?: string | null,
  right?: string | null,
) => {
  const equation = left != null && right != null ? `${left} = ${right}　` : "";
  if (defined === false) return `${equation}未定义`;
  return `${equation}${holds ? "成立" : "不成立"}`;
};

const repairHintFor = (
  code: DiagnosticResult["code"],
  relation?: CoreRelation,
): string | undefined => {
  if (code === "LOST ROOT") {
    return "检查是否除以了可能为 0 的式子，或删掉了合法因式";
  }
  if (code === "EXTRANEOUS ROOT") {
    return "把候选解代回原方程，剔除增根";
  }
  if (code === "DOMAIN SHIFT" || relation?.domainExpanded) {
    return "约分/化简后显式保留原定义域约束";
  }
  if (code === "TAINTED") {
    return "先回到标为「根本问题」的那一步修复";
  }
  return undefined;
};

/**
 * Talks to the real C++ MathCore through the local HTTP gateway
 * (`python -m neomath --serve`). Each cell execution re-runs the whole
 * derivation prefix so the verdict for the current cell is always computed
 * against the true previous steps.
 */
export class CoreMathRuntime implements MathRuntime {
  /** cell.id → the equation line the core produced for that cell. */
  private resolved = new Map<string, { source: string; base: string; line: string }>();

  async ping(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 1500);
      const response = await fetch(`${coreUrl()}/api/health`, {
        signal: controller.signal,
      });
      clearTimeout(timer);
      return response.ok;
    } catch {
      return false;
    }
  }

  async getKernelStatus(): Promise<KernelStatus> {
    return (await this.ping()) ? "core" : "offline";
  }

  private async call<TResult>(
    method: string,
    payload?: unknown,
  ): Promise<CoreEnvelope<TResult>> {
    const response = await fetch(`${coreUrl()}/api/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    });
    if (!response.ok) throw new Error(`MathCore HTTP ${response.status}`);
    return (await response.json()) as CoreEnvelope<TResult>;
  }

  async evaluateProbe(request: ProbeRequest): Promise<ProbeResult | null> {
    try {
      const envelope = await this.call<CoreProbe>("evaluateProbe", {
        document: { source: request.source },
        probe: { value: request.value },
      });
      if (!envelope.ok || !envelope.result?.value) return null;
      const probe = envelope.result;
      return {
        value: probe.value ?? request.value,
        previousDefined: probe.previousDefined,
        currentDefined: probe.currentDefined,
        previousHolds: probe.previousPredicateResult,
        currentHolds: probe.currentPredicateResult,
        previousEval: evaluation(
          probe.previousDefined,
          probe.previousPredicateResult,
          probe.previousLeftValue,
          probe.previousRightValue,
        ),
        currentEval: evaluation(
          probe.currentDefined,
          probe.currentPredicateResult,
          probe.currentLeftValue,
          probe.currentRightValue,
        ),
        reason: probe.reason,
      };
    } catch {
      return null;
    }
  }

  async getCompletions(source: string, step: number): Promise<CompletionItem[]> {
    try {
      const envelope = await this.call<{
        items?: Array<{ label?: string; title?: string; command?: string; preview?: string; source?: string }>;
        completions?: Array<{ label?: string; title?: string; command?: string; preview?: string; source?: string }>;
      }>("getCompletions", {
        document: { source },
        step,
      });
      if (!envelope.ok || !envelope.result) return [];
      const raw =
        envelope.result.items ?? envelope.result.completions ?? [];
      return raw.map((item) => ({
        label: item.label || item.title || item.command || "补全",
        command: item.command || item.label || item.title || "",
        preview: item.preview || item.source,
      })).filter((item) => item.command);
    } catch {
      return [];
    }
  }

  async execute(
    cell: MathCell,
    context: ExecutionContext,
  ): Promise<ExecutionResult> {
    const lines = context.previousMathCells.map((previous) => {
      const cached = this.resolved.get(previous.id);
      return cached && cached.source === previous.source
        ? cached.line
        : previous.source;
    });

    if (cell.kind === "transform") {
      const base = lines[lines.length - 1];
      if (!base) {
        return unsupported(
          "缺少上一步",
          "变形指令需要作用在一个已有的方程上，请先运行前面的单元格。",
        );
      }
      const transformed = await this.applyTransformation(base, cell.source);
      if (transformed.type === "unsupported") return transformed;
      lines.push(transformed.line);
      this.resolved.set(cell.id, { source: cell.source, base, line: transformed.line });
    } else {
      lines.push(cell.source);
      this.resolved.set(cell.id, {
        source: cell.source,
        base: "",
        line: cell.source,
      });
    }

    let trace: CoreEnvelope<TraceResult>;
    try {
      trace = await this.call<TraceResult>("runTrace", {
        document: { source: lines.join("\n") },
      });
    } catch (error) {
      return unsupported(
        "内核连接中断",
        `请求 MathCore 失败：${error instanceof Error ? error.message : String(error)}`,
      );
    }
    if (!trace.ok || !trace.result) {
      return unsupported(
        "无法运行",
        trace.error?.message || "MathCore 未返回结果",
      );
    }
    return this.mapTrace(cell, trace);
  }

  /**
   * Structured op → next equation line. This is the supported path.
   * Free Chinese is not accepted here.
   */
  async applyStructuredTransform(
    baseLine: string,
    op: TransformOp,
    arg?: string,
  ): Promise<StructuredTransformResult> {
    if (!baseLine.trim()) {
      return { ok: false, message: "没有可变形的上一步方程。" };
    }
    if ((op === "divide" || op === "multiply") && !arg?.trim()) {
      return {
        ok: false,
        message: op === "divide" ? "请填写除数（数学式，如 x 或 10）" : "请填写乘数（数学式）",
      };
    }
    try {
      const executed = await this.call<TransformationResult>(
        "executeTransformation",
        {
          document: { source: baseLine },
          step: 0,
          intent: toCoreIntent(op, arg),
        },
      );
      if (!executed.ok || !executed.result?.applied || !executed.result.source) {
        return {
          ok: false,
          message:
            executed.result?.reason ||
            executed.error?.message ||
            "MathCore 拒绝了这个变形。",
        };
      }
      return { ok: true, line: executed.result.source };
    } catch (error) {
      return {
        ok: false,
        message: error instanceof Error ? error.message : String(error),
      };
    }
  }

  /**
   * Legacy transform cells may still carry short offline keywords
   * (因式分解 / 除以 x). Prefer structured palette for new input.
   */
  private async applyTransformation(
    baseLine: string,
    command: string,
  ): Promise<{ type: "ok"; line: string } | UnsupportedResult> {
    const mapped = mapLegacyCommand(command);
    if (mapped) {
      const result = await this.applyStructuredTransform(
        baseLine,
        mapped.op,
        mapped.arg,
      );
      if (result.ok) return { type: "ok", line: result.line };
      return unsupported("变形未应用", result.message);
    }
    return unsupported(
      "请使用结构化操作",
      "不要写「两边除以10」这类句子。请点工具栏操作，除法/乘法在输入框里填数学式（如 10 或 x）。",
    );
  }

  private mapTrace(
    cell: MathCell,
    trace: CoreEnvelope<TraceResult>,
  ): ExecutionResult {
    const result = trace.result ?? {};
    const states = result.states ?? [];
    const index = states.length - 1;
    const state = states[index];
    if (!state) return unsupported("无法运行", "MathCore 返回了空的推导状态。");

    const relation = index > 0 ? result.relations?.[index - 1] : undefined;
    const diagnostic = result.diagnostics?.[index];
    const status = diagnostic?.status ?? "unverified";
    const duration = `${(trace.metrics?.durationMs ?? 0).toFixed(1)} ms`;
    const solutionSet = formatSet(state.solutionSet);
    const domain = formatSet(state.domain);
    const formulaLatex = toLatex(state.canonical || cell.source);
    const trustLevel = state.trustLevel ?? "exact";

    if (status === "unverified" || status === "parse_error") {
      return unsupported(
        diagnostic?.title || "暂时无法验证",
        friendlyReason(relation?.reason ?? diagnostic?.message),
      );
    }

    if (status === "root_fault" || status === "tainted") {
      const lost = relation?.lostSolutions ?? [];
      const gained = relation?.gainedSolutions ?? [];
      const code: DiagnosticResult["code"] = lost.length
        ? "LOST ROOT"
        : gained.length
          ? "EXTRANEOUS ROOT"
          : relation?.domainExpanded || relation?.domainShrunk
            ? "DOMAIN SHIFT"
            : status === "tainted"
              ? "TAINTED"
              : "NOT EQUIVALENT";
      const probe = result.activeProbe;
      return {
        type: "diagnostic",
        code,
        title: diagnostic?.title || "这一步不等价",
        previousSet: formatSet(states[index - 1]?.solutionSet),
        currentSet: solutionSet,
        domain,
        lost,
        gained,
        summary: diagnostic?.message || friendlyReason(relation?.reason),
        witness: probe?.value
          ? {
              value: `x = ${probe.value}`,
              original: evaluation(
                probe.previousDefined,
                probe.previousPredicateResult,
                probe.previousLeftValue,
                probe.previousRightValue,
              ),
              transformed: evaluation(
                probe.currentDefined,
                probe.currentPredicateResult,
                probe.currentLeftValue,
                probe.currentRightValue,
              ),
            }
          : { value: "—", original: "—", transformed: "—" },
        details:
          friendlyReason(relation?.reason) +
          (status === "tainted"
            ? " 当前步骤本身等价，但它建立在前面已经改变的数学状态上。"
            : ""),
        repairHint: repairHintFor(code, relation),
        duration,
        trustLevel,
      } satisfies DiagnosticResult;
    }

    // status === "valid"
    if (
      index > 0 &&
      (relation?.relation === "equivalent" ||
        relation?.reason === "solution_set_and_domain_preserved")
    ) {
      const values = state.solutionSet?.values ?? [];
      return {
        type: "equivalence",
        title: "等价变换",
        latex: values.length
          ? values.map((value) => `x = ${toLatex(value)}`).join("\\quad\\text{或}\\quad")
          : formulaLatex,
        solutionSet: "解集保持不变",
        domain,
        duration,
        trustLevel,
      } satisfies EquivalenceResult;
    }

    return {
      type: "math",
      latex: formulaLatex,
      solutionSet,
      domain,
      method: trustLevel,
      duration,
      trustLevel,
    } satisfies MathResult;
  }
}
