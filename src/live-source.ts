import type { Cell } from "./backend.ts"

export function sourceLines(cells: Cell[]) {
  return cells.flatMap(cell => cell.source.split("\n").map(text => ({
    text: cell.kind === "markdown" && text ? `# ${text}` : text,
    cell,
  })))
}

// Retain stable IDs on both sides of an insertion so replay can reuse the prefix.
export function editSource(cells: Cell[], source: string): Cell[] {
  const previous = sourceLines(cells)
  const lines = source.replace(/\r\n/g, "\n").split("\n")
  if (lines.join("\n") === previous.map(line => line.text).join("\n")) return cells
  let prefix = 0
  while (prefix < Math.min(previous.length, lines.length) && previous[prefix].text === lines[prefix]) prefix++
  let suffix = 0
  while (suffix < Math.min(previous.length, lines.length) - prefix && previous[previous.length - 1 - suffix].text === lines[lines.length - 1 - suffix]) suffix++
  const used = new Set<string>()
  const result: Cell[] = []
  let previousGroup: string | undefined
  lines.forEach((text, index) => {
    const oldIndex = index < prefix ? index : index >= lines.length - suffix ? previous.length - (lines.length - index) : index < previous.length - suffix ? index : -1
    const old = previous[oldIndex]
    const comment = /^\s*#/.test(text)
    const kind = comment || !text.trim() ? "markdown" : old?.text === text && old.cell.kind === "transform" ? "transform" : "math"
    const body = comment ? text.replace(/^\s*# ?/, "") : text
    if (kind === "markdown" && old?.cell.kind === "markdown" && previousGroup === old.cell.id && result.at(-1)?.kind === "markdown") {
      result[result.length - 1] = { ...result.at(-1)!, source: `${result.at(-1)!.source}\n${body}` }
      return
    }
    const id = old && !used.has(old.cell.id) ? old.cell.id : crypto.randomUUID()
    used.add(id)
    previousGroup = kind === "markdown" ? old?.cell.id : undefined
    result.push(old?.cell.source === body && old.cell.kind === kind ? old.cell : { ...(old?.cell ?? {}), id, kind, source: body, executionState: "idle", outputCollapsed: old?.cell.outputCollapsed ?? false, result: undefined })
  })
  return result.map(cell => {
    const old = cells.find(previous => previous.id === cell.id)
    return old?.kind === cell.kind && old.source === cell.source ? old : cell
  })
}
