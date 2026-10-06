export interface Cell {
  id: string
  kind: "markdown" | "math" | "transform"
  source: string
  executionState: string
  outputCollapsed: boolean
  [key: string]: unknown
}
export interface Notebook {
  id: string
  title: string
  fileName: string
  cells: Cell[]
  updatedAt: number
  darwinInk?: [number, number][][]
  [key: string]: unknown
}
export interface FileMeta {
  name: string
  fileName: string
  title: string
  updatedAt?: number
}
export interface MathSet {
  kind: string
  values?: string[]
  excluded?: string[]
  lower?: string
  upper?: string
  lowerInclusive?: boolean
  upperInclusive?: boolean
}
export interface Probe {
  value: string
  previousDefined?: boolean
  currentDefined?: boolean
  previousPredicateResult?: boolean
  currentPredicateResult?: boolean
  previousLeftValue?: string
  previousRightValue?: string
  currentLeftValue?: string
  currentRightValue?: string
  reason?: string
}
export interface ProbeTrace {
  value: string
  steps: {
    defined?: boolean
    predicateResult?: boolean
    leftValue?: string
    rightValue?: string
    reason?: string
  }[]
}
export function compareProbe(result: ProbeTrace): Probe {
  const current = result.steps.at(-1)
  const previous = result.steps.at(-2)
  return {
    value: result.value,
    previousDefined: previous?.defined,
    currentDefined: current?.defined,
    previousPredicateResult: previous?.predicateResult,
    currentPredicateResult: current?.predicateResult,
    previousLeftValue: previous?.leftValue,
    previousRightValue: previous?.rightValue,
    currentLeftValue: current?.leftValue,
    currentRightValue: current?.rightValue,
    reason: current?.reason,
  }
}
export interface Trace {
  states: {
    source: string
    canonical?: string
    solutionSet?: MathSet
    domain?: MathSet
    trustLevel?: string
  }[]
  relations: {
    reason: string
    relation: string
    lostSolutions?: string[]
    gainedSolutions?: string[]
    domainExpanded?: boolean
    domainShrunk?: boolean
    probe?: Probe
  }[]
  diagnostics: { status: string; title?: string; message?: string }[]
  breakpointStep?: number
}
export interface Envelope<T> {
  ok: boolean
  result: T
  metrics?: { durationMs: number; cacheHits: number }
  sessionId?: string
  text?: string
  source?: string
  error?: { code?: string; message?: string }
}
export function backendUrl() {
  return (import.meta.env?.VITE_NEOMATH_API_URL ?? "/api").replace(/\/$/, "")
}
export async function call<T>(
  method: string,
  payload: object = {},
  base = backendUrl(),
): Promise<T> {
  const envelope = await callEnvelope<T>(method, payload, base)
  if (envelope.result === undefined) throw new Error("Invalid NeoMath response")
  return envelope.result
}
export async function callEnvelope<T>(
  method: string,
  payload: object = {},
  base = backendUrl(),
  signal?: AbortSignal,
): Promise<Envelope<T>> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener("abort", abort, { once: true })
  if (signal?.aborted) controller.abort()
  const timer = setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetch(`${base}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    const envelope: Envelope<T> = await response.json()
    if (!response.ok || !envelope.ok)
      throw new Error(envelope.error?.message || `HTTP ${response.status}`)
    return envelope
  } catch (error) {
    throw new Error(
      error instanceof Error ? error.message : "NeoMath connection failed",
    )
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener("abort", abort)
  }
}
export function formatSet(set?: MathSet): string {
  if (!set) return "—"
  if (set.kind === "finite") return `{${(set.values ?? []).join(", ")}}`
  if (set.kind === "empty") return "∅"
  if (set.kind === "all_real") return "ℝ"
  if (set.kind.includes("excluding_finite"))
    return `ℝ \\ {${(set.excluded ?? []).join(", ")}}`
  if (set.kind === "interval")
    return `${
      set.lower == null || set.lowerInclusive === false ? "(" : "["
    }${set.lower ?? "−∞"}, ${set.upper ?? "∞"}${
      set.upper == null || set.upperInclusive === false ? ")" : "]"
    }`
  return "Unverified"
}
export function newNotebook(
  title: string,
  sources: string[],
  writing = false,
): Notebook {
  const id = crypto.randomUUID()
  return {
    id,
    title,
    fileName: `${id}.nm`,
    updatedAt: Date.now(),
    cells: sources.map((source) => ({
      id: crypto.randomUUID(),
      kind: writing ? "markdown" : "math",
      source,
      executionState: "idle",
      outputCollapsed: false,
    })),
  }
}
export function validNotebook(value: unknown): value is Notebook {
  if (!value || typeof value !== "object") return false
  const doc = value as Notebook
  const validInk =
    doc.darwinInk === undefined ||
    (Array.isArray(doc.darwinInk) &&
      doc.darwinInk.every(
        (stroke) =>
          Array.isArray(stroke) &&
          stroke.length > 0 &&
          stroke.every(
            (point) =>
              Array.isArray(point) &&
              point.length === 2 &&
              point.every(Number.isFinite),
          ),
      ))
  return (
    validInk &&
    typeof doc.title === "string" &&
    Array.isArray(doc.cells) &&
    doc.cells.every(
      (c) =>
        c &&
        typeof c.id === "string" &&
        typeof c.source === "string" &&
        ["math", "transform", "markdown"].includes(c.kind),
    )
  )
}
export function legacyIntent(
  source: string,
): { intent: string; arguments: Record<string, string>; confidence: number } {
  const command = source.trim()
  const argument = command.match(
    /(?:除以|divide(?:\s+by)?|乘以|multiply(?:\s+by)?)\s*(.+)$/i,
  )
  const intent = /因式|factor/i.test(command)
    ? "factor"
    : /展开|expand/i.test(command)
      ? "expand"
      : /平方|square/i.test(command)
        ? "square_both_sides"
        : /移项|move/i.test(command)
          ? "move_terms"
          : /求解|solve/i.test(command)
            ? "solve"
            : /除以|divide/i.test(command) && argument
              ? "divide"
              : /乘以|multiply/i.test(command) && argument
                ? "multiply"
                : ""
  if (!intent) throw new Error(`Unsupported transform command: ${command}`)
  return {
    intent,
    arguments: argument ? { expression: argument[1].trim() } : {},
    confidence: 1,
  }
}
export async function resolveSource(
  cells: Cell[],
  base?: string,
): Promise<string> {
  const lines: string[] = []
  for (const cell of cells) {
    if (cell.kind === "markdown") continue
    if (cell.kind === "math") {
      if (!cell.source.trim() || /[\r\n]/.test(cell.source.trim()))
        throw new Error("Enter one non-empty equation per cell")
      lines.push(cell.source.trim())
      continue
    }
    if (!lines.length)
      throw new Error("A transformation needs a previous equation")
    const result = await call<{
      applied: boolean
      source?: string
      reason?: string
    }>(
      "executeTransformation",
      {
        document: { source: lines[lines.length - 1] },
        step: 0,
        intent: legacyIntent(cell.source),
      },
      base,
    )
    if (!result.applied || !result.source)
      throw new Error(result.reason || "MathCore rejected the transformation")
    lines.push(result.source)
  }
  return lines.join("\n")
}
