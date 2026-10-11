export type CellKind = "markdown" | "math" | "transform";

export type CellExecutionState =
  | "idle"
  | "queued"
  | "running"
  | "success"
  | "error";

export type KernelStatus = "checking" | "core" | "offline";

export interface NotebookDocument {
  id: string;
  title: string;
  fileName: string;
  cells: NotebookCell[];
  updatedAt: number;
}

export interface BaseCell {
  id: string;
  kind: CellKind;
  source: string;
  label?: string;
  executionCount?: number;
  executionState: CellExecutionState;
  outputCollapsed: boolean;
}

export interface MarkdownCell extends BaseCell {
  kind: "markdown";
}

export interface MathCell extends BaseCell {
  kind: "math" | "transform";
  result?: ExecutionResult;
}

export interface WitnessInfo {
  value: string;
  original: string;
  transformed: string;
}

/** Shared analysis fields available after a successful MathCore run. */
export interface AnalysisFields {
  domain?: string;
  duration?: string;
  trustLevel?: string;
}

export interface MathResult extends AnalysisFields {
  type: "math";
  latex: string;
  solutionSet: string;
  method: string;
  duration: string;
}

export interface DiagnosticResult extends AnalysisFields {
  type: "diagnostic";
  code:
    | "LOST ROOT"
    | "EXTRANEOUS ROOT"
    | "DOMAIN SHIFT"
    | "NOT EQUIVALENT"
    | "TAINTED";
  title: string;
  previousSet: string;
  currentSet: string;
  lost: string[];
  gained?: string[];
  summary: string;
  witness: WitnessInfo;
  details: string;
  /** Soft hint for a repair path (product copy, not a solver claim). */
  repairHint?: string;
}

export interface EquivalenceResult extends AnalysisFields {
  type: "equivalence";
  title: string;
  latex: string;
  solutionSet: string;
}

export interface UnsupportedResult {
  type: "unsupported";
  title: string;
  message: string;
}

export type ExecutionResult =
  | MathResult
  | DiagnosticResult
  | EquivalenceResult
  | UnsupportedResult;

export type NotebookCell = MarkdownCell | MathCell;

export interface ExecutionContext {
  previousMathCells: MathCell[];
}

export interface ProbeRequest {
  /** Full derivation source (newline-separated equations). */
  source: string;
  /** Rational value string, e.g. "0" or "1/2". */
  value: string;
}

export interface ProbeResult {
  value: string;
  previousDefined?: boolean;
  currentDefined?: boolean;
  previousHolds?: boolean;
  currentHolds?: boolean;
  previousEval: string;
  currentEval: string;
  reason?: string;
}

export interface CompletionItem {
  label: string;
  command: string;
  preview?: string;
}

export const isMathCell = (cell: NotebookCell): cell is MathCell =>
  cell.kind === "math" || cell.kind === "transform";

export const isRootFault = (result: ExecutionResult | undefined): boolean =>
  result?.type === "diagnostic" &&
  (result.code === "LOST ROOT" ||
    result.code === "EXTRANEOUS ROOT" ||
    result.code === "DOMAIN SHIFT" ||
    result.code === "NOT EQUIVALENT");

export function analysisFromResult(result: ExecutionResult | undefined): {
  solutionSet: string;
  domain: string;
  status: string;
  duration: string;
  trustLevel: string;
} | null {
  if (!result) return null;
  if (result.type === "unsupported") {
    return {
      solutionSet: "—",
      domain: "—",
      status: result.title,
      duration: "—",
      trustLevel: "—",
    };
  }
  if (result.type === "math") {
    return {
      solutionSet: result.solutionSet,
      domain: result.domain ?? "—",
      status: "有效",
      duration: result.duration,
      trustLevel: result.trustLevel ?? result.method,
    };
  }
  if (result.type === "equivalence") {
    return {
      solutionSet: result.solutionSet,
      domain: result.domain ?? "—",
      status: "等价",
      duration: result.duration ?? "—",
      trustLevel: result.trustLevel ?? "exact",
    };
  }
  return {
    solutionSet: result.currentSet,
    domain: result.domain ?? "—",
    status: result.code,
    duration: result.duration ?? "—",
    trustLevel: result.trustLevel ?? "exact",
  };
}
