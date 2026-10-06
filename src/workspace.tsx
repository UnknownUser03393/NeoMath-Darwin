import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import {
  call,
  formatSet,
  resolveSource,
  type FileMeta,
  type Notebook,
  type Trace,
} from "./backend"
import { type Relation, type StateKey, type Step } from "./data"
import { MathSession, mathSignature, mathCells } from "./math-session"

export function traceState(trace: Trace | null, index: number): StateKey {
  if (!trace) return "unchecked"
  const status = trace.diagnostics[index]?.status
  const rel = trace.relations[index - 1]
  if (status === "tainted") return "tainted"
  if (status === "root_fault")
    return rel?.lostSolutions?.length
      ? "lostSolution"
      : rel?.gainedSolutions?.length
        ? "gainedSolution"
        : "domainShift"
  if (status !== "valid") return "unverified"
  return index === 0 ? "initial" : "equivalent"
}
function useStore() {
  const [document, setDocument] = useState<Notebook | null>(null)
  const [openVersion, setOpenVersion] = useState(0)
  const [files, setFiles] = useState<FileMeta[]>([])
  const [trace, setTrace] = useState<Trace | null>(null)
  const [error, setError] = useState("")
  const [connected, setConnected] = useState(false)
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState("Saved")
  const [autoCheck, setAutoCheck] = useState(() => {
    try { return localStorage.getItem("neomath-auto-check") !== "false" } catch { return true }
  })
  const [composing, setComposing] = useState(false)
  const [analysis, setAnalysis] = useState<Awaited<ReturnType<MathSession["evaluate"]>> | null>(null)
  const [checkStatus, setCheckStatus] = useState("Not checked")
  const session = useRef(new MathSession())
  const checkedSignature = useRef<string | null>(null)
  const active = useRef<AbortController | null>(null)
  const autoTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latest = useRef(document)
  latest.current = document
  const generation = useRef(0)
  const saveQueue = useRef(Promise.resolve())
  const refresh = async () => {
    try {
      const result = await call<{ files: FileMeta[] }>("listNotebooks")
      await call("getCapabilities")
      setFiles(result.files)
      setConnected(true)
      setError("")
    } catch (e) {
      setConnected(false)
      setError((e as Error).message)
    }
  }
  useEffect(() => {
    void refresh()
  }, [])
  const signature = mathSignature(document?.cells ?? [])
  useEffect(() => {
    if (checkedSignature.current === signature) return
    active.current?.abort()
    checkedSignature.current = null
    generation.current++
    setTrace(null)
    setAnalysis(null)
    setBusy(false)
    setCheckStatus(mathCells(document?.cells ?? []).length ? "Pending" : "No equations")
  }, [signature, openVersion])
  const check = useCallback(async () => {
    if (autoTimer.current) { clearTimeout(autoTimer.current); autoTimer.current = null }
    const snapshot = latest.current
    if (!snapshot || !mathCells(snapshot.cells).length) return
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    const token = ++generation.current
    setBusy(true)
    setCheckStatus("Checking…")
    setError("")
    setTrace(null)
    try {
      const result = await session.current.evaluate(snapshot.cells, controller.signal)
      if (token === generation.current) {
        setTrace(result.trace)
        setAnalysis(result)
        checkedSignature.current = mathSignature(snapshot.cells)
        setCheckStatus(result.parsed.steps.some(s => s.error) ? "Syntax error" : "Checked")
        setConnected(true)
      }
    } catch (e) {
      if (token === generation.current && !controller.signal.aborted) {
        setError((e as Error).message); setCheckStatus("Check failed")
      }
    } finally {
      if (token === generation.current) setBusy(false)
    }
  }, [])
  useEffect(() => {
    try { localStorage.setItem("neomath-auto-check", String(autoCheck)) } catch {}
    if (!autoCheck || composing || !document || !mathCells(document.cells).length || checkedSignature.current === signature) return
    autoTimer.current = setTimeout(() => { void check() }, 250)
    return () => { if (autoTimer.current) clearTimeout(autoTimer.current) }
  }, [signature, openVersion, autoCheck, composing, check])
  useEffect(() => () => { active.current?.abort() }, [])
  const cancelCheck = () => {
    if (autoTimer.current) clearTimeout(autoTimer.current)
    active.current?.abort(); generation.current++; setBusy(false); setCheckStatus("Cancelled")
  }
  const save = async (doc = latest.current) => {
    if (!doc) return
    setSaving("Saving…")
    const task = saveQueue.current.then(async () => {
      await call("saveNotebook", { name: doc.fileName, document: doc })
      if (latest.current === doc) setSaving("Saved")
    })
    saveQueue.current = task.catch(() => {})
    try {
      await task
    } catch (e) {
      setSaving("Save failed")
      setError((e as Error).message)
      throw e
    }
  }
  useEffect(() => {
    if (!document) return
    setSaving("Unsaved")
    const timer = setTimeout(() => {
      void save(document).catch(() => {})
    }, 700)
    return () => clearTimeout(timer)
  }, [document])
  const update = (patch: Partial<Notebook>) => {
    if (patch.cells && mathSignature(patch.cells) !== mathSignature(latest.current?.cells ?? [])) {
      active.current?.abort(); generation.current++
    }
    setDocument(previous => previous ? { ...previous, ...patch, updatedAt: Date.now() } : previous)
  }
  const open = async (doc: Notebook) => {
    if (autoTimer.current) { clearTimeout(autoTimer.current); autoTimer.current = null }
    checkedSignature.current = null
    active.current?.abort()
    const token = ++generation.current
    const controller = new AbortController()
    active.current = controller
    const preparedSession = new MathSession()
    let prepared: Awaited<ReturnType<MathSession["evaluate"]>> | null = null
    let failure = ""
    if (autoCheck && mathCells(doc.cells).length) {
      try { prepared = await preparedSession.evaluate(doc.cells, controller.signal) }
      catch (e) {
        if (controller.signal.aborted || token !== generation.current) return false
        failure = (e as Error).message
      }
    }
    if (token !== generation.current) return false
    session.current = preparedSession
    // Publish the document and its diagnostics together, before entering its view.
    checkedSignature.current = prepared || failure ? mathSignature(doc.cells) : null
    latest.current = doc
    setDocument(doc)
    setOpenVersion((value) => value + 1)
    setTrace(prepared?.trace ?? null)
    setAnalysis(prepared)
    setBusy(false)
    setCheckStatus(prepared ? prepared.parsed.steps.some(step => step.error) ? "Syntax error" : "Checked" : failure ? "Check failed" : mathCells(doc.cells).length ? "Not checked" : "No equations")
    setError(failure)
    return true
  }
  const steps: Step[] = useMemo(
    () =>
      document?.cells
        .filter((c) => c.kind !== "markdown")
        .map((c, i) => ({
          n: i + 1,
          src: trace?.states[i]?.source ?? c.source,
          solutions: formatSet(trace?.states[i]?.solutionSet),
          evaluate: () => {
            throw new Error("Use the MathCore evaluateProbe API")
          },
        })) ?? [],
    [document, trace],
  )
  const relations: Record<number, Relation> = Object.fromEntries(
    steps.slice(1).map((s, i) => [
      s.n,
      {
        id: s.n,
        from: s.n - 1,
        to: s.n,
        state: traceState(trace, i + 1),
        explanation:
          trace?.relations[i]?.reason ?? "Run Check to verify this relation.",
        witnessX: null,
      },
    ]),
  )
  const relationForStep = (n: number) => relations[n] ?? null
  return {
    document,
    openVersion,
    files,
    trace,
    error,
    connected,
    busy,
    autoCheck,
    setAutoCheck,
    setComposing,
    analysis,
    checkStatus,
    cancelCheck,
    saving,
    steps,
    relations,
    relationForStep,
    refresh,
    check,
    save,
    update,
    open,
    setError,
  }
}
type Store = ReturnType<typeof useStore>
const Context = createContext<Store | null>(null)
export function useWorkspace() {
  return useContext(Context)!
}
export default function WorkspaceProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const value = useStore()
  return <Context.Provider value={value}>{children}</Context.Provider>
}
