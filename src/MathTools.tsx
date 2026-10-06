import { useEffect, useRef, useState } from "react"
import { call, callEnvelope, resolveSource } from "./backend"
import { mathSignature } from "./math-session"
import { useWorkspace } from "./workspace"
import { M } from "./ui"
interface Completion { id: string; label: string; available: boolean; risk?: string; preview?: string }
const operations = ["factor", "expand", "move_terms", "divide", "multiply", "square_both_sides", "solve"]
export default function MathTools({ cellId, compact = false, completionRequest = 0, showOperations = true, onDismiss, onInsert }: { cellId: string | null; compact?: boolean; completionRequest?: number; showOperations?: boolean; onDismiss?: () => void; onInsert?: (source: string, afterId: string) => void }) {
  const workspace = useWorkspace()
  const { document, update, setError } = workspace
  const [items, setItems] = useState<Completion[]>([])
  const [operation, setOperation] = useState("factor")
  const [argument, setArgument] = useState("2")
  const [busy, setBusy] = useState(false)
  const [explanation, setExplanation] = useState("")
  const list = useRef<HTMLDivElement>(null)
  const request = useRef(0)
  const latest = useRef(workspace)
  latest.current = workspace
  const signature = mathSignature(document?.cells ?? [])
  useEffect(() => { request.current++; setItems([]); setExplanation(""); setBusy(false) }, [signature, cellId, document?.id])
  const selected = document?.cells.find(c => c.id === cellId && c.kind !== "markdown") ?? (compact ? undefined : document?.cells.filter(c => c.kind !== "markdown").at(-1))
  const prefix = document?.cells.slice(0, (document?.cells.findIndex(c => c.id === selected?.id) ?? -1) + 1) ?? []
  const run = async (action: (token: number) => Promise<void>) => {
    const token = ++request.current
    setBusy(true); setError("")
    try { await action(token) } catch (e) { if (token === request.current) setError((e as Error).message) }
    finally { if (token === request.current) setBusy(false) }
  }
  const complete = () => run(async token => {
    if (!selected) return
    const source = await resolveSource(prefix)
    const result = await call<Completion[]>("getCompletions", { document: { source }, step: source.split("\n").length - 1 })
    if (token === request.current) setItems(result)
  })
  useEffect(() => { if (compact && completionRequest > 0) void complete() }, [completionRequest])
  useEffect(() => { if (compact && items.some(item => item.available)) list.current?.querySelector<HTMLButtonElement>("button[data-completion]")?.focus() }, [items, compact])
  useEffect(() => {
    if (compact) return
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.code === "Space" && !e.isComposing) { e.preventDefault(); void complete() }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [signature, cellId])
  const apply = (intent: string) => run(async token => {
    const source = await resolveSource(prefix)
    const result = await call<{ applied: boolean; source?: string; reason?: string }>("executeTransformation", {
      document: { source }, step: source.split("\n").length - 1,
      intent: { intent, confidence: 1, arguments: ["divide", "multiply"].includes(intent) ? { expression: argument } : {} },
    })
    if (!result.applied || !result.source) throw new Error(result.reason || "Transformation rejected")
    if (token !== request.current || latest.current.document?.id !== document?.id || mathSignature(latest.current.document?.cells ?? []) !== signature) return
    if (onInsert && selected) { onInsert(result.source, selected.id); return }
    const cells = [...latest.current.document!.cells]
    const index = cells.findIndex(c => c.id === selected?.id)
    cells.splice(index + 1, 0, { id: crypto.randomUUID(), kind: "math", source: result.source, executionState: "idle", outputCollapsed: false })
    update({ cells })
    onDismiss?.()
  })
  if (compact && !showOperations) return <div className="completion-list" ref={list} onKeyDown={event => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onDismiss?.() }
    if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault()
      const buttons = [...(list.current?.querySelectorAll<HTMLButtonElement>('button[data-completion]') ?? [])]
      const active = buttons.indexOf(window.document.activeElement as HTMLButtonElement)
      buttons[(active + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus()
    }
  }}>
    <div className="flex items-center justify-between px-3 py-2 text-[12px] text-ink2"><span>下一步 · ↑↓ 选择，Enter 插入</span><button onClick={onDismiss} aria-label="Close completion">Esc</button></div>
    {busy && <p className="p-3 text-ink2">正在计算可用变形…</p>}
    {!busy && !items.some(item => item.available) && <p className="p-3 text-ink2">{selected ? "当前步骤没有可用建议" : "把光标放在公式行，再按 Ctrl+Space"}</p>}
    {items.filter(item => item.available).map(item => <button data-completion key={item.id} disabled={busy} onClick={() => void apply(item.id)} className="completion-option block w-full border-t hairline px-3 py-2 text-left focus:bg-accent/10 focus:outline-none">
      <span className="flex justify-between gap-3 text-[13px]"><strong>{item.label}</strong><span className="text-ink2">{item.risk === "safe" ? "等价" : item.risk === "may_add_solutions" ? "可能增根" : item.risk === "may_lose_solutions" ? "可能丢根" : item.risk}</span></span>
      <M className="mt-1 block text-[18px]">{item.preview ?? ""}</M>
    </button>)}
  </div>
  return <div className="space-y-3 border-t hairline pt-3 text-[13px]">
    <div className="flex flex-wrap items-center gap-2"><span className="mr-auto min-w-0 text-ink2">Selected equation: <M>{selected?.source ?? "Select an equation"}</M></span>{!compact && <button disabled={busy || !selected} onClick={() => void complete()} className="press min-h-11 rounded-full bg-subtle px-4 text-accent">Complete · Ctrl+Space</button>}{compact && <button onClick={onDismiss} className="min-h-9 px-3 text-accent">Close</button>}</div>
    {!!items.length && <div className="flex flex-wrap gap-2">{items.map(item => <button key={item.id} disabled={busy || !item.available} title={`${item.risk ?? ""}: ${item.preview ?? ""}`} onClick={() => void apply(item.id)} className="press rounded-[12px] bg-subtle p-3 text-left"><span className="font-medium">{item.label}</span><M className="block text-[18px] text-ink2">{item.preview ?? ""}</M><p className="text-[12px] text-ink2">{item.risk}</p></button>)}</div>}
    {showOperations && <div className="flex flex-wrap gap-2"><select aria-label="Transformation" value={operation} onChange={e => setOperation(e.target.value)} className="min-h-11 rounded-[10px] bg-subtle px-3">{operations.map(op => <option key={op}>{op}</option>)}</select>
      {["divide", "multiply"].includes(operation) && <input aria-label="Transformation argument" value={argument} onChange={e => setArgument(e.target.value)} className="min-h-11 w-28 rounded-[10px] bg-subtle px-3" />}
      <button disabled={busy || !selected} onClick={() => void apply(operation)} className="press min-h-11 rounded-full bg-accent/10 px-4 text-accent">Apply transformation</button>
      <button disabled={busy || !workspace.trace} onClick={() => void run(async token => {
        const result = await callEnvelope("requestAiExplanation", { document: { source: workspace.analysis?.source }, trace: { ok: true, result: workspace.trace } })
        if (token === request.current) setExplanation(`${result.text ?? "No explanation returned"}${result.source ? ` (${result.source})` : ""}`)
      })} className="press min-h-11 rounded-full bg-subtle px-4 text-accent">Explain</button>
    </div>}
    {explanation && <p role="status" className="rounded-[12px] bg-subtle p-3">{explanation}</p>}
  </div>
}
