import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { EditorState, StateEffect, StateField, Transaction, Prec } from "@codemirror/state"
import { Decoration, EditorView, WidgetType, keymap, drawSelection, type DecorationSet } from "@codemirror/view"
import { defaultKeymap, history, historyKeymap, undo, redo, isolateHistory } from "@codemirror/commands"
import { useWorkspace } from "./workspace"
import { sourceLines, editSource } from "./live-source"
import { renderMath } from "./math-format"
import MathTools from "./MathTools"
import type { Cell } from "./backend"
import ErrorConnectors from "./ErrorConnectors"

const focusEffect = StateEffect.define<boolean>()
const diagnosticsEffect = StateEffect.define<Record<number, string>>()
const transformsEffect = StateEffect.define<Record<number, string | null>>()
class CheckMarker extends WidgetType {
  constructor(readonly status: string, readonly label: string) { super() }
  eq(other: CheckMarker) { return this.status === other.status && this.label === other.label }
  toDOM() {
    const button = document.createElement("button")
    button.className = "live-check-marker"
    button.dataset.check = this.status
    button.textContent = this.label
    button.setAttribute("aria-label", `Inspect step: ${this.status} · ${this.label}`)
    button.title = `查看详情：${this.label}`
    return button
  }
  ignoreEvent() { return true }
}
class Slot extends WidgetType {
  constructor(readonly position: number) { super() }
  eq(other: Slot) { return this.position === other.position }
  toDOM() {
    const element = document.createElement("span")
    element.className = "live-slot"
    element.dataset.placeholder = String(this.position)
    element.textContent = "□"
    element.setAttribute("aria-label", "公式待输入位置")
    return element
  }
  ignoreEvent() { return true }
}
const labelsEffect = StateEffect.define<Record<number, string>>()
class ErrorAnchor extends WidgetType {
  constructor(readonly step: number) { super() }
  eq(other: ErrorAnchor) { return this.step === other.step }
  toDOM() {
    const anchor = document.createElement("span")
    anchor.className = "error-dependency-anchor"
    anchor.dataset.errorStep = String(this.step)
    anchor.setAttribute("aria-hidden", "true")
    return anchor
  }
  ignoreEvent() { return true }
}
class Formula extends WidgetType {
  constructor(readonly source: string) { super() }
  eq(other: Formula) { return this.source === other.source }
  toDOM() {
    const element = document.createElement("span")
    element.className = "live-formula math-render"
    element.dataset.mathSource = this.source
    element.innerHTML = renderMath(this.source).html ?? ""
    return element
  }
  ignoreEvent() { return false }
}
const previewState = StateField.define<{ focused: boolean; diagnostics: Record<number, string>; labels: Record<number, string>; transforms: Record<number, string | null>; decorations: DecorationSet }>({
  create: () => ({ focused: false, diagnostics: {}, labels: {}, transforms: {}, decorations: Decoration.none }),
  update(value, tr) {
    let focused = value.focused, diagnostics = value.diagnostics, transforms = value.transforms, labels = value.labels
    for (const effect of tr.effects) {
      if (effect.is(focusEffect)) focused = effect.value
      if (effect.is(diagnosticsEffect)) diagnostics = effect.value
      if (effect.is(transformsEffect)) transforms = effect.value
      if (effect.is(labelsEffect)) labels = effect.value
    }
    const ranges = []
    let step = -1
    for (let i = 1; i <= tr.state.doc.lines; i++) {
      const line = tr.state.doc.line(i)
      const prose = /^\s*#/.test(line.text) || !line.text.trim()
      if (!prose) step++
      const active = focused && tr.state.selection.ranges.some(range => range.from <= line.to && range.to >= line.from)
      const status = prose ? "" : diagnostics[step] ?? "pending"
      ranges.push(Decoration.line({ attributes: { class: `live-line ${active ? "live-active" : ""}`, "data-check": status, "data-source-line": String(i) } }).range(line.from))
      if (["root_fault", "parse_error", "tainted"].includes(status)) ranges.push(Decoration.widget({ widget: new ErrorAnchor(step), side: -1 }).range(line.from))
      if (!prose && labels[step]) {
        const fault = status === "root_fault" || status === "parse_error"
        ranges.push(Decoration.widget({ widget: new CheckMarker(status, labels[step]), side: fault ? -2 : 1 }).range(fault ? line.from : line.to))
      }
      if (active && !prose) {
        const slots = new Set<number>()
        if (/[=+\-±∓*/^,(]\s*$/.test(line.text)) slots.add(line.to)
        for (const match of line.text.matchAll(/\(\s*\)/g)) slots.add(line.from + match.index! + 1)
        for (const position of slots) ranges.push(Decoration.widget({ widget: new Slot(position), side: 1 }).range(position))
      }
      if (active || !line.length) continue
      if (prose) {
        const prefix = line.text.match(/^\s*# ?/)?.[0].length ?? 0
        if (prefix) ranges.push(Decoration.replace({}).range(line.from, line.from + prefix))
      } else {
        const formula = i in transforms ? transforms[i] : line.text
        if (formula && renderMath(formula).html) ranges.push(Decoration.replace({ widget: new Formula(formula) }).range(line.from, line.to))
      }
    }
    return { focused, diagnostics, labels, transforms, decorations: Decoration.set(ranges, true) }
  },
  provide: field => EditorView.decorations.from(field, value => value.decorations),
})

export default function LiveEditor({ visible, onSelectStep }: { visible: boolean; onSelectStep: (step: number, inspect?: boolean) => void }) {
  const workspace = useWorkspace()
  const latest = useRef(workspace)
  latest.current = workspace
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const projected = useRef<string | null>(null)
  const [cellId, setCellId] = useState<string | null>(null)
  const [completion, setCompletion] = useState(0)
  const [tools, setTools] = useState(false)
  const [popupTop, setPopupTop] = useState(52)
  const [popupLeft, setPopupLeft] = useState(16)
  const canonical = sourceLines(workspace.document?.cells ?? []).map(line => line.text).join("\n")
  useLayoutEffect(() => {
    if (!host.current) return
    const select = (editor: EditorView, cells: Cell[] = latest.current.document?.cells ?? []) => {
      const index = editor.state.doc.lineAt(editor.state.selection.main.head).number - 1
      const line = sourceLines(cells)[index]
      setCellId(line?.cell.kind === "markdown" ? null : line?.cell.id ?? null)
    }
    const editor = new EditorView({ parent: host.current, state: EditorState.create({ doc: canonical, extensions: [
      history(), drawSelection(), EditorView.lineWrapping, previewState,
      EditorView.contentAttributes.of({ "aria-label": "Live Preview source", spellcheck: "false" }),
      keymap.of([
        { key: "Escape", run: () => { setTools(false); setCompletion(0); return true } },
        { key: "Space", run: editor => {
          if (editor.composing || !editor.state.selection.main.empty) return false
          const head = editor.state.selection.main.head
          const match = editor.state.sliceDoc(Math.max(0, head - 12), head).match(/\\(times|cdot|div|leq|geq)$/)
          if (!match) return false
          const symbols: Record<string, string> = { times: "×", cdot: "·", div: "÷", leq: "≤", geq: "≥" }
          editor.dispatch({ changes: { from: head - match[0].length, to: head, insert: symbols[match[1]] }, selection: { anchor: head - match[0].length + 1 }, annotations: Transaction.userEvent.of("input") })
          return true
        } },
        { key: "Mod-Shift-z", run: redo },
        { key: "Mod-Enter", run: () => { void latest.current.check(); return true } },
        { key: "Mod-s", run: () => { void latest.current.save().catch(() => {}); return true } },
        { key: "Ctrl-Space", run: editor => {
          const caret = editor.coordsAtPos(editor.state.selection.main.head)
          const root = host.current?.parentElement?.getBoundingClientRect()
          if (caret && root) {
            setPopupTop(Math.max(8, Math.min(caret.bottom - root.top + 8, root.height - Math.min(root.height * .45, 360))))
            setPopupLeft(Math.max(8, Math.min(caret.left - root.left, root.width - Math.min(420, root.width - 16) - 8)))
          }
          setCompletion(value => value + 1); return true
        } },
        ...historyKeymap, ...defaultKeymap,
      ]),
      Prec.highest(EditorView.domEventHandlers({
        keydown: (event, editor) => {
          if (!event.isComposing && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
            event.preventDefault(); event.stopPropagation()
            if (event.shiftKey) redo(editor); else undo(editor)
            return true
          }
          return false
        },
        focus: (_event, editor) => { editor.dispatch({ effects: focusEffect.of(true) }); return false },
        blur: (_event, editor) => { if (!editor.composing) editor.dispatch({ effects: focusEffect.of(false) }); return false },
        compositionstart: () => { latest.current.setComposing(true); return false },
        compositionend: () => { latest.current.setComposing(false); return false },
        mousedown: (event, editor) => {
          const formula = (event.target as Element).closest(".live-formula")
          if (!formula || event.shiftKey || event.detail > 1) return false
          const position = editor.posAtDOM(formula)
          editor.dispatch({ selection: { anchor: position }, effects: focusEffect.of(true) })
          editor.focus()
          return false
        },
      })),
      EditorView.updateListener.of(update => {
        let cells = latest.current.document?.cells ?? []
        if (update.docChanged) {
          cells = editSource(cells, update.state.doc.toString())
          projected.current = sourceLines(cells).map(line => line.text).join("\n")
          latest.current.update({ cells })
        }
        if (update.docChanged || update.selectionSet || update.focusChanged) select(update.view, cells)
      }),
    ] }) })
    view.current = editor
    editor.dispatch({ effects: focusEffect.of(false) })
    return () => { latest.current.setComposing(false); editor.destroy(); view.current = null }
  }, [workspace.openVersion])
  useEffect(() => {
    const editor = view.current
    if (!editor || editor.state.doc.toString() === canonical || projected.current === canonical) return
    const old = editor.state.doc.toString()
    projected.current = null
    let from = 0, suffix = 0
    while (from < Math.min(old.length, canonical.length) && old[from] === canonical[from]) from++
    while (suffix < Math.min(old.length, canonical.length) - from && old[old.length - suffix - 1] === canonical[canonical.length - suffix - 1]) suffix++
    editor.dispatch({ changes: { from, to: old.length - suffix, insert: canonical.slice(from, canonical.length - suffix) }, annotations: [Transaction.userEvent.of("input.transform"), isolateHistory.of("full")] })
  }, [canonical])
  useLayoutEffect(() => {
    const diagnostics: Record<number, string> = {}
    const labels: Record<number, string> = {}
    const transforms: Record<number, string | null> = {}
    let step = -1
    sourceLines(workspace.document?.cells ?? []).forEach((line, index) => {
      if (line.cell.kind !== "markdown") step++
      if (line.cell.kind === "transform") transforms[index + 1] = workspace.trace?.states[step]?.source ?? null
      const state = workspace.trace?.states[step]
      if (line.cell.kind !== "markdown" && state?.latex && state.source === line.text && !renderMath(line.text).html) transforms[index + 1] = `\\displaystyle ${state.latex}`
    })
    workspace.trace?.diagnostics.forEach((item, index) => { diagnostics[index] = item.status })
    workspace.analysis?.parsed.steps.forEach((item, index) => { if (item.error) diagnostics[index] = "parse_error" })
    workspace.trace?.diagnostics.forEach((item, index) => {
      const relation = workspace.trace?.relations[index - 1]
      const changes = [relation?.lostSolutions?.length ? `丢根：${relation.lostSolutions.join(", ")}` : "", relation?.gainedSolutions?.length ? `增根：${relation.gainedSolutions.join(", ")}` : "", relation?.domainExpanded ? "定义域扩大" : relation?.domainShrunk ? "定义域缩小" : ""].filter(Boolean)
      labels[index] = item.status === "root_fault" ? changes.join(" · ") || "定义域改变" : item.status === "tainted" ? "受前序错误影响" : ["unverified", "unsupported"].includes(item.status) ? item.message || "当前 Core 无法验证此式" : ""
    })
    workspace.analysis?.parsed.steps.forEach((item, index) => { if (item.error) labels[index] = `语法：${item.error.message}` })
    view.current?.dispatch({ effects: [diagnosticsEffect.of(diagnostics), labelsEffect.of(labels), transformsEffect.of(transforms)] })
    host.current?.dispatchEvent(new Event("live-preview-layout"))
  }, [workspace.trace, workspace.analysis, canonical])
  useEffect(() => { if (visible) view.current?.requestMeasure() }, [visible])
  return <section aria-label="Live Preview" className="live-preview relative flex h-full min-h-0 flex-col" hidden={!visible}>
    {(tools || completion > 0) && <div role="dialog" aria-label={tools ? "Math transformations" : "Math completions"} style={{ top: popupTop, left: popupLeft }} className="absolute z-40 max-h-[45dvh] w-[min(420px,calc(100%-16px))] overflow-auto rounded-[10px] border hairline bg-panel shadow-lg"><MathTools cellId={cellId} compact completionRequest={completion} showOperations={tools} onInsert={(source, afterId) => {
      const editor = view.current
      if (!editor) return
      const rows = sourceLines(latest.current.document?.cells ?? [])
      const index = rows.findIndex(row => row.cell.id === afterId)
      if (index < 0) return
      const end = editor.state.doc.line(index + 1).to
      editor.dispatch({ changes: { from: end, insert: `\n${source}` }, selection: { anchor: end + 1 + source.length }, annotations: [Transaction.userEvent.of("input.transform"), isolateHistory.of("full")], scrollIntoView: true })
      setTools(false); setCompletion(0); editor.focus()
    }} onDismiss={() => { setTools(false); setCompletion(0); view.current?.focus() }} /></div>}
    <div ref={host} className="live-editor-host min-h-0 flex-1" onMouseDownCapture={event => {
      const line = (event.target as Element).closest<HTMLElement>("[data-source-line]")
      if (!line) return
      const rows = sourceLines(latest.current.document?.cells ?? []).slice(0, Number(line.dataset.sourceLine))
      if (rows.at(-1)?.cell.kind !== "markdown") onSelectStep(rows.filter(row => row.cell.kind !== "markdown").length, false)
    }} onClick={event => {
      const slot = (event.target as Element).closest<HTMLElement>("[data-placeholder]")
      if (slot && view.current) { view.current.dispatch({ selection: { anchor: Number(slot.dataset.placeholder) }, effects: focusEffect.of(true) }); view.current.focus(); return }
      const line = (event.target as Element).closest<HTMLElement>("[data-source-line]")
      if (!line) return
      const index = Number(line.dataset.sourceLine) - 1
      const rows = sourceLines(latest.current.document?.cells ?? []).slice(0, index + 1)
      if (rows.at(-1)?.cell.kind !== "markdown") onSelectStep(rows.filter(row => row.cell.kind !== "markdown").length, !!(event.target as Element).closest(".live-check-marker"))
    }}><ErrorConnectors host={host} trace={workspace.trace} visible={visible} revision={canonical} /></div>
    <footer className="flex shrink-0 items-center gap-3 border-t hairline px-4 py-2 text-[12px] text-ink2">
      <span className="mr-auto" role="status">{workspace.checkStatus === "Pending" && workspace.autoCheck ? "正在检查…" : workspace.checkStatus} · {workspace.trace?.engine === "sympy" ? "SymPy CAS" : "MathCore"} · {workspace.saving}</span>
      <button className="text-accent" onMouseDown={event => event.preventDefault()} onClick={() => { setTools(value => !value); setPopupLeft(8); setPopupTop(Math.max(8, (host.current?.parentElement?.clientHeight ?? 360) - 320)) }}>变形…</button>
      <button className="text-accent" onMouseDown={event => event.preventDefault()} onClick={() => {
        const editor = view.current
        if (!editor) return
        editor.focus(); editor.dispatch({ selection: editor.state.selection }); setCompletion(value => value + 1)
        const caret = editor.coordsAtPos(editor.state.selection.main.head), root = host.current?.parentElement?.getBoundingClientRect()
        if (caret && root) { setPopupTop(Math.max(8, Math.min(caret.bottom - root.top + 8, root.height - 300))); setPopupLeft(Math.max(8, Math.min(caret.left - root.left, root.width - 428))) }
      }}>补全 · Ctrl+Space</button>
    </footer>
  </section>
}
