import { callEnvelope, legacyIntent, type Cell, type Trace } from "./backend.ts"
export interface ParsedDocument {
  steps: { source: string; error?: { message: string; code: string; start?: number; end?: number; expected?: string[] } | null }[]
}
export const mathCells = (cells: Cell[]) => cells.filter(cell => cell.kind !== "markdown")
export const mathSignature = (cells: Cell[]) => JSON.stringify(mathCells(cells).map(c => [c.id, c.kind, c.source]))
export function firstChangedStep(previous: Cell[], next: Cell[]): number {
  const limit = Math.min(previous.length, next.length)
  let index = 0
  while (index < limit && previous[index].id === next[index].id && previous[index].kind === next[index].kind && previous[index].source === next[index].source) index++
  return index
}
export class MathSession {
  private previous: Cell[] = []
  private lines: string[] = []
  private initialized = false
  async evaluate(cells: Cell[], signal?: AbortSignal, base?: string) {
    const next = mathCells(cells)
    const changedStep = firstChangedStep(this.previous, next)
    const lines = this.lines.slice(0, changedStep)
    for (const cell of next.slice(changedStep)) {
      if (signal?.aborted) throw new Error("Cancelled")
      if (cell.kind === "math") {
        if (!cell.source.trim() || /[\r\n]/.test(cell.source.trim())) throw new Error("Enter one non-empty equation per cell")
        lines.push(cell.source.trim())
      } else {
        if (!lines.length) throw new Error("A transformation needs a previous equation")
        const transformed = await callEnvelope<{ applied: boolean; source?: string; reason?: string }>("executeTransformation", {
          document: { source: lines.at(-1) }, step: 0, intent: legacyIntent(cell.source),
        }, base, signal)
        if (!transformed.result.applied || !transformed.result.source) throw new Error(transformed.result.reason || "Transformation rejected")
        lines.push(transformed.result.source)
      }
    }
    const source = lines.join("\n")
    const parsed = await callEnvelope<ParsedDocument>("parseDocument", { document: { source } }, base, signal)
    const method = this.initialized ? "replay" : "runTrace"
    const result = await callEnvelope<Trace>(method, { document: { source }, changedStep }, base, signal)
    if (signal?.aborted) throw new Error("Cancelled")
    this.previous = next.map(c => ({ ...c }))
    this.lines = lines
    this.initialized = true
    return { trace: result.result, parsed: parsed.result, source, method, changedStep, metrics: result.metrics, parseDurationMs: parsed.metrics?.durationMs }
  }
}
