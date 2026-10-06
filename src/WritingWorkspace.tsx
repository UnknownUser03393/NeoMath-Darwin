import { useCallback, useEffect, useRef, useState } from "react"
import { call } from "./backend"
import { XdltSession, applyHtmlPatches, type XdltResult } from "./xdlt-session"
import { typesetXdlt } from "./math-format"
import katexCss from "katex/dist/katex.min.css?inline"
export default function WritingWorkspace({ fileName, onBack }: { fileName: string; onBack: () => void }) {
  const [source, setSource] = useState<string | null>(null)
  const [result, setResult] = useState<XdltResult | null>(null)
  const [error, setError] = useState("")
  const [status, setStatus] = useState("Loading…")
  const [saved, setSaved] = useState("Saved")
  const [automatic, setAutomatic] = useState(true)
  const [verify, setVerify] = useState(true)
  const [execute, setExecute] = useState(true)
  const [composing, setComposing] = useState(false)
  const [debug, setDebug] = useState(false)
  const session = useRef<XdltSession | null>(null)
  const generation = useRef(0)
  const latest = useRef(source)
  latest.current = source
  const mounted = useRef(true)
  const options = useRef({ verify, execute })
  options.current = { verify, execute }
  const saveQueue = useRef(Promise.resolve())
  const frame = useRef<HTMLIFrameElement>(null)
  const editor = useRef<HTMLTextAreaElement>(null)
  const latestResult = useRef(result)
  latestResult.current = result
  const [css, setCss] = useState("")
  useEffect(() => {
    mounted.current = true
    session.current = new XdltSession()
    void call<{ source: string }>("loadXdltDocument", { name: fileName }).then(r => { if (mounted.current) setSource(r.source) }).catch(e => { if (mounted.current) setError(e.message) })
    void call<{ css: string }>("getXdltReferenceCss").then(r => { if (mounted.current) setCss(r.css) }).catch(() => {})
    return () => { mounted.current = false; generation.current++; void session.current?.dispose().catch(() => {}) }
  }, [fileName])
  const compile = useCallback(async () => {
    if (latest.current === null || !session.current) return
    const content = latest.current
    const token = ++generation.current
    setStatus("Compiling…"); setError("")
    try {
      const next = await session.current.update(content, options.current)
      if (token !== generation.current || !mounted.current) return
      // A skipped reply means the DOM missed a patch; recover from the complete HTML.
      const root = frame.current?.contentDocument?.getElementById("preview")
      const canPatch = applied.current?.revision !== undefined && applied.current.revision === next.previousRevision
      const patched = root && canPatch ? applyHtmlPatches(root, next) : false
      if (root && !canPatch) root.innerHTML = next.html
      if (root) typesetXdlt(root)
      applied.current = next
      setResult(next)
      setStatus(next.stats ? `Updated · ${patched ? "preview patched" : "preview refreshed"} · ${next.stats.reusedVerification} checks reused · ${next.stats.recomputedVerification} recomputed` : "Compiled")
    } catch (e) { if (token === generation.current && mounted.current) { setError((e as Error).message); setStatus("Compile failed") } }
  }, [])
  const applied = useRef<XdltResult | null>(null)
  useEffect(() => {
    generation.current++
    if (source === null) return
    setStatus("Preview pending")
    // Until the new result arrives, old preview remains explicitly pending.
    if (!automatic || composing) return
    const timer = setTimeout(() => { void compile() }, 250)
    return () => clearTimeout(timer)
  }, [source, automatic, composing, verify, execute, compile])
  const save = (content = latest.current) => {
    if (content === null) return Promise.resolve()
    setSaved("Saving…")
    const task = saveQueue.current.then(async () => {
      await call("saveXdltDocument", { name: fileName, source: content })
      if (mounted.current && content === latest.current) setSaved("Saved")
    })
    saveQueue.current = task.catch(() => {})
    return task.catch(e => { if (mounted.current) { setSaved("Save failed"); setError(e.message) } throw e })
  }
  useEffect(() => {
    if (source === null) return
    setSaved("Unsaved")
    const timer = setTimeout(() => { void save(source).catch(() => {}) }, 700)
    return () => clearTimeout(timer)
  }, [source])
  const render = () => {
    const dom = frame.current?.contentDocument
    const root = dom?.getElementById("preview")
    if (!root) return
    root.innerHTML = latestResult.current?.html ?? ""
    typesetXdlt(root)
    applied.current = latestResult.current
    root.onclick = event => {
      const target = (event.target as Element).closest("[data-xdlt-render-id], [data-xdlt-id]") as HTMLElement | null
      const id = target?.dataset.xdltRenderId ?? target?.dataset.xdltId
      const range = latestResult.current?.sourceMap.find(entry => entry.renderId === id)?.sourceRange
      if (!range || !editor.current) return
      const characters = Array.from(latest.current ?? "")
      editor.current.focus()
      editor.current.setSelectionRange(characters.slice(0, range.start).join("").length, characters.slice(0, range.end).join("").length)
    }
  }
  return <div className="flex h-dvh flex-col bg-canvas text-ink">
    <header className="material flex shrink-0 flex-wrap items-center gap-2 border-b hairline p-3">
      <button className="press min-h-11 px-3 text-accent" onClick={() => void save().then(onBack).catch(() => {})}>‹ Documents</button>
      <h1 className="mr-auto truncate font-semibold">{fileName}</h1>
      <button className="press min-h-11 px-3 text-accent" onClick={() => void compile()}>Compile</button>
      <button aria-pressed={automatic} className="press min-h-11 px-3 text-accent" onClick={() => setAutomatic(v => !v)}>Auto compile</button>
      <label className="flex min-h-11 items-center gap-2 text-[13px]"><input type="checkbox" checked={verify} onChange={e => setVerify(e.target.checked)} />Verify assertions</label>
      <label className="flex min-h-11 items-center gap-2 text-[13px]"><input type="checkbox" checked={execute} onChange={e => setExecute(e.target.checked)} />Run executable blocks</label>
      <button className="press min-h-11 px-3 text-accent" onClick={() => void save().catch(() => {})}>{saved}</button>
      <button aria-pressed={debug} className="press min-h-11 px-3 text-accent" onClick={() => setDebug(v => !v)}>Debug</button>
    </header>
    <p role="status" className="shrink-0 px-4 py-2 text-[12px] text-ink2">{status}{result?.stats && ` · parsing ${result.stats.reusedParsing ? "reused" : "recomputed"}`}</p>
    {error && <p role="alert" className="shrink-0 px-4 py-2 text-[13px] text-bad">{error}</p>}
    <main className="grid min-h-0 flex-1 grid-rows-2 md:grid-cols-2 md:grid-rows-1">
      <textarea ref={editor} aria-label="XDLT source" spellCheck={false} value={source ?? ""} disabled={source === null} className="min-h-0 resize-none border hairline bg-panel p-4 font-mono text-[14px] outline-none" onChange={e => { generation.current++; setSource(e.target.value) }} onCompositionStart={() => setComposing(true)} onCompositionEnd={() => setComposing(false)} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); void compile() } }} />
      <iframe ref={frame} title="XDLT preview" sandbox="allow-same-origin" className="h-full min-h-0 w-full border-0 bg-white" srcDoc={`<!doctype html><html><head><meta charset="utf-8"><style>${katexCss}\n${css}\n.katex-display { margin: .6em 0; }</style></head><body><div id="preview"></div></body></html>`} onLoad={render} />
    </main>
    {!!result?.diagnostics.length && <div className="max-h-36 shrink-0 overflow-auto border-t hairline p-3 text-[13px]">{result.diagnostics.map((d, i) => <p key={i} className={d.severity === "error" ? "text-bad" : "text-ink2"}>{d.code}: {d.message}</p>)}</div>}
    {debug && <pre className="max-h-[35dvh] shrink-0 overflow-auto border-t hairline p-3 text-[12px]">{JSON.stringify({ stats: result?.stats, invalidated: result?.invalidatedSemanticIds, graph: result?.graph, semanticDocument: result?.semanticDocument }, null, 2)}</pre>}
  </div>
}
