import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react"
import CanvasView, { type Tool } from "./CanvasView"
import StepsView from "./StepsView"
import Inspector from "./BackendInspector"
import type { Target } from "./Inspector"
import { stateMeta, type RelId } from "./data"
import WorkspaceProvider, { useWorkspace } from "./workspace"
import DocumentEditor from "./DocumentEditor"
import LiveEditor from "./LiveEditor"
import BackendSettings from "./BackendSettings"
import WritingWorkspace from "./WritingWorkspace"
import { inkReducer, type InkHistory, type Pt } from "./ink"
import { StatusLine } from "./ui"
import Documents from "./Documents"
import { transitionPage } from "./motion"

type Sel = { kind: "step"; n: number } | { kind: "rel"; id: RelId }
type Mode = "system" | "light" | "dark"

function useLayoutTier() {
  const initial = (w: number) =>
    w >= 1180 ? 3 : w >= 900 ? 2 : w >= 600 ? 1 : 0
  const [size, setSize] = useState(() => ({
    width: window.innerWidth,
    tier: initial(window.innerWidth),
  }))
  useEffect(() => {
    const on = () =>
      setSize((previous) => {
        const width = window.innerWidth
        let tier = previous.tier
        const boundaries = [600, 900, 1180]
        while (tier < 3 && width >= boundaries[tier] + 12) tier++
        while (tier > 0 && width < boundaries[tier - 1] - 12) tier--
        return { width, tier }
      })
    window.addEventListener("resize", on)
    return () => window.removeEventListener("resize", on)
  }, [])
  return {
    width: size.width,
    tier: ["compact", "narrow", "regular", "wide"][size.tier],
  }
}

function Btn({
  children,
  onClick,
  pressed,
  disabled,
  title,
  label,
  className = "",
}: {
  children: React.ReactNode
  onClick?: () => void
  pressed?: boolean
  disabled?: boolean
  title?: string
  label?: string
  className?: string
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={pressed}
      disabled={disabled}
      title={title}
      aria-label={label}
      className={`press inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-full px-3 font-medium disabled:text-ink3 ${
        pressed ? "bg-accent/12 text-accent" : "text-accent"
      } ${className}`}
    >
      {children}
    </button>
  )
}

const icon = {
  width: 20,
  height: 20,
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
}
const Icons: Record<Tool | "plus", React.ReactNode> = {
  pen: (
    <svg {...icon}>
      <path d="M3 17l1-4L14 3l3 3L7 16z M12 5l3 3" />
    </svg>
  ),
  eraser: (
    <svg {...icon}>
      <path d="M8 16h8M5 13l7-8 5 5-5 6H8z" />
    </svg>
  ),
  select: (
    <svg {...icon}>
      <path d="M4 4l5 12 2-5 5-2z" />
    </svg>
  ),
  equation: (
    <svg {...icon}>
      <path d="M4 7h12M4 13h12" />
    </svg>
  ),
  plus: (
    <svg {...icon}>
      <path d="M10 4v12M4 10h12" />
    </svg>
  ),
}

export default function App() {
  return (
    <WorkspaceProvider>
      <Workspace />
    </WorkspaceProvider>
  )
}
function Workspace() {
  const backend = useWorkspace()
  const { document: notebook, relations, relationForStep } = backend
  const [editing, setEditing] = useState(false)
  const { width, tier } = useLayoutTier()
  const docked = tier === "wide" || tier === "regular"

  const [mode, setMode] = useState<Mode>(() => {
    try {
      const saved = localStorage.getItem("neomath-appearance")
      return saved === "light" || saved === "dark" ? saved : "system"
    } catch {
      return "system"
    }
  })
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = () => {
      const dark = mode === "dark" || (mode === "system" && mq.matches)
      document.documentElement.dataset.theme = dark ? "dark" : "light"
    }
    apply()
    try {
      localStorage.setItem("neomath-appearance", mode)
    } catch {
      /* Appearance still applies for this session. */
    }
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [mode])

  const [writingFile, setWritingFile] = useState("")
  const [screen, setScreen] = useState<"documents" | "document" | "settings" | "writing">(
    "documents",
  )
  const [settingsBack, setSettingsBack] = useState<"documents" | "document">(
    "documents",
  )
  const [view, setView] = useState<"live" | "canvas" | "steps">("live")
  const [actionsExpanded, setActionsExpanded] = useState(true)
  const [sel, setSel] = useState<Sel | null>(null)
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [pinned, setPinned] = useState<Target | null>(null)
  const [tool, setTool] = useState<Tool>("select")
  const [zoom, setZoom] = useState(1)
  const [grid, setGrid] = useState(false)
  const [fitRequest, setFitRequest] = useState(0)
  const [ink, dispatchInk] = useReducer(inkReducer, {
    past: [],
    present: [],
    future: [],
  })
  const viewport = useRef<Pt>([0, 0])
  const content = useRef<HTMLDivElement>(null)
  const canvasFooter = useRef<HTMLDivElement>(null)
  const canvasTools = useRef<HTMLDivElement>(null)
  const [toolIndicator, setToolIndicator] = useState({ left: 0, width: 0 })
  const [contentHeight, setContentHeight] = useState(window.innerHeight - 160)
  const [footerHeight, setFooterHeight] = useState(148)
  useLayoutEffect(() => {
    if (!content.current) return
    const observer = new ResizeObserver(([entry]) =>
      setContentHeight(entry.contentRect.height),
    )
    observer.observe(content.current)
    return () => observer.disconnect()
  }, [screen])
  useLayoutEffect(() => {
    if (!canvasFooter.current) return
    const observer = new ResizeObserver(([entry]) =>
      setFooterHeight(entry.target.getBoundingClientRect().height),
    )
    observer.observe(canvasFooter.current)
    return () => observer.disconnect()
  }, [screen, view, open, tier])
  useEffect(() => {
    dispatchInk({ type: "reset", strokes: notebook?.darwinInk ?? [] })
    setSel(null)
    setPinned(null)
    setOpen(false)
    setEditing(false)
    setView("live")
    viewport.current = [0, 0]
  }, [backend.openVersion])
  const commitInk = (strokes: InkHistory["present"]) => {
    dispatchInk({ type: "commit", strokes })
    backend.update({ darwinInk: strokes })
  }
  useEffect(() => {
    if (
      notebook &&
      ink.present !== notebook.darwinInk &&
      (ink.past.length || ink.future.length)
    )
      backend.update({ darwinInk: ink.present })
  }, [ink.present])

  const liveTarget: Target = useMemo(() => {
    if (!sel) return "idle"
    if (sel.kind === "rel") return sel.id
    return relationForStep(sel.n)?.id ?? "initial"
  }, [sel, relations])
  const target = pinned ?? liveTarget

  const strongStep = !sel
    ? null
    : sel.kind === "step"
      ? sel.n
      : (relations[sel.id]?.to ?? null)
  const weakStep =
    sel?.kind === "rel" ? (relations[sel.id]?.from ?? null) : null
  const selectedRel = sel?.kind === "rel" ? sel.id : null

  const selectStep = (n: number) => {
    setSel({ kind: "step", n })
    setOpen(true)
  }
  const selectRel = (id: RelId) => {
    setSel({ kind: "rel", id })
    setOpen(true)
  }
  const go = (t: Target) => typeof t === "number" && selectRel(t)

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (
        screen !== "document" ||
        e.isComposing ||
        e.keyCode === 229 ||
        e.defaultPrevented
      )
        return
      if ((e.metaKey || e.ctrlKey) && (e.key === "Enter" || e.key.toLowerCase() === "r")) {
        e.preventDefault()
        void backend.check()
        return
      }
      if (
        e.target instanceof HTMLElement &&
        e.target.closest('input, textarea, select, [contenteditable="true"]')
      )
        return
      if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === "i"
      ) {
        e.preventDefault()
        setOpen((o) => !o)
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
        e.preventDefault()
        dispatchInk({ type: e.shiftKey ? "redo" : "undo" })
      } else if (e.key === "Escape") {
        const menu = document.querySelector<HTMLDetailsElement>("details[open]")
        if (menu) menu.open = false
        else setOpen(false)
      }
    }
    window.addEventListener("keydown", k)
    return () => window.removeEventListener("keydown", k)
  }, [screen])

  const fullInspect =
    tier === "compact" ||
    (tier === "narrow" &&
      expanded &&
      contentHeight * 0.55 - (view === "canvas" ? footerHeight : 0) < 280)
  const compactInspect = fullInspect && open
  const bottomPanel = tier === "narrow" && !fullInspect
  useLayoutEffect(() => {
    const toolbar = canvasTools.current
    if (!toolbar) return
    const measure = () => {
      const selected = toolbar.querySelector<HTMLButtonElement>(
        'button[aria-pressed="true"]',
      )
      if (!selected) return
      const next = { left: selected.offsetLeft, width: selected.offsetWidth }
      setToolIndicator((previous) =>
        previous.left === next.left && previous.width === next.width
          ? previous
          : next,
      )
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(toolbar)
    toolbar
      .querySelectorAll("button")
      .forEach((button) => observer.observe(button))
    return () => observer.disconnect()
  }, [tool, screen, compactInspect])
  const inspectorEl = (
    <Inspector
      target={target}
      pinned={pinned !== null}
      onPin={() => setPinned((p) => (p ? null : liveTarget))}
      onClose={() => setOpen(false)}
      onGo={go}
      compact={!docked}
    />
  )

  const tools: { id: Tool; label: string }[] = [
    { id: "pen", label: "Pen" },
    { id: "eraser", label: "Eraser" },
    { id: "select", label: "Select" },
    { id: "equation", label: "Equation" },
  ]

  const liveState =
    typeof target !== "number"
      ? backend.trace
        ? "initial"
        : "unchecked"
      : (relations[target]?.state ?? "unchecked")
  const title =
    target === "idle"
      ? "Inspect"
      : target === "initial"
        ? "Step 1"
        : `Step ${relations[target]?.from} → ${relations[target]?.to}`

  const showSettings = (back: "documents" | "document") => {
    setSettingsBack(back)
    transitionPage(() => setScreen("settings"))
  }
  if (screen === "documents")
    return (
      <Documents
        onWriting={fileName => { setWritingFile(fileName); transitionPage(() => setScreen("writing")) }}
        onOpen={() => transitionPage(() => setScreen("document"))}
        onSettings={() => showSettings("documents")}
      />
    )
  if (screen === "writing") return <WritingWorkspace key={writingFile} fileName={writingFile} onBack={() => transitionPage(() => setScreen("documents"), "back")} />
  if (screen === "settings")
    return (
      <div className="flex h-dvh flex-col bg-canvas text-ink">
        <header className="material flex shrink-0 items-center border-b hairline px-3 py-1.5">
          <Btn
            onClick={() =>
              transitionPage(() => setScreen(settingsBack), "back")
            }
          >
            ‹ Back
          </Btn>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-6">
          <div className="mx-auto max-w-xl space-y-8 pb-12 pt-8 sm:pt-10">
            <div className="space-y-2">
              <h1 className="text-[28px] leading-[34px] font-semibold tracking-[-0.02em]">
                Settings
              </h1>
              <p className="text-[14px] text-ink2">
                Make NeoMath feel at home.
              </p>
            </div>
            <section aria-labelledby="appearance-heading" className="space-y-3">
              <h2
                id="appearance-heading"
                className="px-1 text-[17px] font-semibold"
              >
                Appearance
              </h2>
              <div className="rounded-[18px] bg-panel p-5">
                <div className="mb-4 space-y-1">
                  <p className="font-medium">Theme</p>
                  <p className="text-[13px] leading-[18px] text-ink2">
                    Choose a look, or follow your device.
                  </p>
                </div>
                <fieldset>
                  <legend className="sr-only">Theme</legend>
                  <div className="relative grid grid-cols-3 rounded-[12px] bg-subtle p-1">
                    <span
                      aria-hidden="true"
                      className="theme-slider pointer-events-none absolute bottom-1 left-1 top-1 rounded-[9px] bg-elevated"
                      style={{
                        width: "calc((100% - 8px) / 3)",
                        transform: `translateX(${["system", "light", "dark"].indexOf(mode) * 100}%)`,
                      }}
                    />
                    {(["system", "light", "dark"] as const).map((m) => (
                      <label
                        key={m}
                        className="relative min-w-0 cursor-pointer"
                      >
                        <input
                          type="radio"
                          name="appearance"
                          value={m}
                          className="peer sr-only"
                          checked={mode === m}
                          onChange={() => setMode(m)}
                        />
                        <span
                          className={`flex min-h-11 items-center justify-center gap-2 rounded-[9px] px-2 text-[13px] font-medium capitalize transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-accent ${
                            mode === m ? "text-ink" : "text-ink2 hover:text-ink"
                          }`}
                        >
                          <svg {...icon}>
                            {m === "system" ? (
                              <>
                                <rect
                                  x="2"
                                  y="3"
                                  width="16"
                                  height="11"
                                  rx="2"
                                />
                                <path d="M7 18h6M10 14v4" />
                              </>
                            ) : m === "light" ? (
                              <>
                                <circle cx="10" cy="10" r="3.5" />
                                <path d="M10 1v2M10 17v2M1 10h2M17 10h2M3.6 3.6L5 5M15 15l1.4 1.4M3.6 16.4L5 15M15 5l1.4-1.4" />
                              </>
                            ) : (
                              <path d="M17 12.5A7.5 7.5 0 0 1 7.5 3 7.5 7.5 0 1 0 17 12.5Z" />
                            )}
                          </svg>
                          {m}
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              </div>
            </section>
            <BackendSettings />
            <section aria-labelledby="input-heading" className="space-y-3">
              <h2 id="input-heading" className="px-1 text-[17px] font-semibold">
                Input and capabilities
              </h2>
              <dl className="space-y-5 rounded-[18px] bg-panel p-5 text-[13px] leading-5">
                <div>
                  <dt className="mb-1 text-[14px] font-medium">
                    Write and navigate
                  </dt>
                  <dd className="text-ink2">
                    Write with a pen or mouse. Drag with one or two fingers to
                    pan; pinch to zoom.
                  </dd>
                </div>
                <div>
                  <dt className="mb-1 text-[14px] font-medium">Workspace</dt>
                  <dd className="text-ink2">
                    Documents and ink annotations are saved by the original
                    NeoMath backend.
                  </dd>
                </div>
                <div>
                  <dt className="mb-1 text-[14px] font-medium">MathCore</dt>
                  <dd className="text-ink2">
                    {backend.connected
                      ? "Connected to NeoMath C++ MathCore."
                      : "Backend unavailable."}{" "}
                    Check computes real results; unsupported expressions remain
                    unverified.
                  </dd>
                </div>
              </dl>
            </section>
          </div>
        </main>
      </div>
    )

  return (
    <div className="flex h-dvh flex-col bg-canvas text-ink">
      <header className="material sticky top-0 z-30 flex flex-wrap items-center gap-x-1 border-b hairline px-3 py-1.5">
        <Btn
          onClick={() => {
            void backend
              .save()
              .then(() => transitionPage(() => setScreen("documents"), "back"))
              .catch(() => {})
          }}
          label="Documents"
          className="!px-2"
        >
          <span aria-hidden>‹</span>
          {tier !== "compact" && "Documents"}
        </Btn>
        <div className="min-w-[180px] flex-1 px-1">
          <div className="flex items-center gap-2">
            <details className="document-menu relative">
              <summary className="flex min-h-11 cursor-pointer items-center whitespace-nowrap text-[17px] font-semibold">
                {notebook?.title} ▾
              </summary>
              <div className="document-menu-content absolute left-0 top-full z-40 w-64 rounded-[14px] bg-elevated p-2">
                <Btn onClick={() => {
                  if (!notebook) return
                  const url = URL.createObjectURL(new Blob([JSON.stringify(notebook, null, 2)], { type: "application/json" }))
                  const link = document.createElement("a"); link.href = url; link.download = notebook.fileName; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
                }}>Export notebook</Btn>
                <Btn
                  onClick={() => {
                    setEditing(true)
                    ;(document.querySelector(
                      "details[open]",
                    ) as HTMLDetailsElement).open = false
                  }}
                >
                  Edit document
                </Btn>
                <Btn onClick={() => showSettings("document")}>Settings</Btn>
              </div>
            </details>
          </div>
        </div>
        <div
          id="document-actions"
          className="header-actions grid min-w-0 max-w-full"
          data-expanded={actionsExpanded}
          aria-hidden={!actionsExpanded}
          inert={!actionsExpanded}
        >
          <div className="min-w-0 overflow-x-auto overflow-y-hidden">
            <div className="flex w-max items-center gap-1">
              <div
                className="flex items-center rounded-[10px] bg-subtle p-0.5 mx-1"
                role="group"
                aria-label="View"
              >
                <select aria-label="View" value={view} onChange={event => { setEditing(false); setView(event.target.value as "live" | "canvas" | "steps") }} className="min-h-11 bg-transparent px-2 text-[13px]"><option value="live">Live Preview</option><option value="canvas">Canvas</option><option value="steps">Steps</option></select>
              </div>
              {view === "canvas" && <Btn
                disabled={!ink.past.length}
                onClick={() => dispatchInk({ type: "undo" })}
              >
                Undo
              </Btn>}
              {view === "canvas" && <Btn
                disabled={!ink.future.length}
                onClick={() => dispatchInk({ type: "redo" })}
              >
                Redo
              </Btn>}
              <Btn
                disabled={backend.busy || !backend.steps.length}
                onClick={() => {
                  void backend.check()
                }}
              >
                {backend.busy ? "Checking…" : "Check"}
              </Btn>
              <details className="relative"><summary className="press flex min-h-11 cursor-pointer items-center rounded-full px-3 text-accent">More</summary><div className="absolute right-0 top-full z-50 flex w-52 flex-col rounded-[12px] border hairline bg-panel p-2 shadow-lg">
                <Btn pressed={backend.autoCheck} onClick={() => backend.setAutoCheck(value => !value)}>Auto check</Btn>
                {backend.busy && <Btn onClick={backend.cancelCheck}>Cancel check</Btn>}
                {backend.trace?.breakpointStep !== undefined && backend.trace.diagnostics[backend.trace.breakpointStep]?.status === "root_fault" && <Btn onClick={() => selectStep(backend.trace!.breakpointStep! + 1)}>First fault</Btn>}
                <Btn onClick={() => setEditing(value => !value)}>Edit</Btn>
                <Btn onClick={() => { void backend.save().catch(() => {}) }}>{backend.saving}</Btn>
              </div></details>
              <Btn
                onClick={() => setOpen((o) => !o)}
                pressed={open}
                title="Inspect (⇧⌘I)"
              >
                Inspect
              </Btn>
            </div>
          </div>
        </div>
        <button
          className="press inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full text-accent"
          aria-expanded={actionsExpanded}
          aria-controls="document-actions"
          aria-label={
            actionsExpanded
              ? "Collapse document actions"
              : "Expand document actions"
          }
          title={actionsExpanded ? "Collapse actions" : "Expand actions"}
          onClick={() => setActionsExpanded((value) => !value)}
        >
          <svg
            {...icon}
            className="action-chevron"
            style={{
              transform: actionsExpanded ? "rotate(0deg)" : "rotate(180deg)",
            }}
          >
            <path d="m7 5 5 5-5 5" />
          </svg>
        </button>
      </header>
      {view !== "live" && <div role="status" className="shrink-0 border-b hairline px-4 py-1.5 text-[12px] text-ink2">
        {backend.checkStatus}{backend.analysis && ` · ${backend.analysis.method === "replay" ? "Replay" : "Full check"} · reused ${backend.analysis.metrics?.cacheHits ?? 0} steps · ${(backend.analysis.metrics?.durationMs ?? 0).toFixed(2)} ms`}
      </div>}
      {backend.error && (
        <div
          role="alert"
          className="flex shrink-0 items-center gap-3 bg-panel px-4 py-2 text-[13px] text-bad"
        >
          <span className="min-w-0 flex-1">{backend.error}</span>
          <button
            className="min-h-11 px-3 text-accent"
            onClick={() => {
              void backend.refresh()
            }}
          >
            Retry connection
          </button>
        </div>
      )}
      {editing && <DocumentEditor onClose={() => setEditing(false)} />}
      {view !== "live" && !!notebook?.cells.some((c) => c.kind === "markdown") && (
        <div className="max-h-[30dvh] shrink-0 space-y-3 overflow-auto border-b hairline p-4">
          {notebook.cells
            .filter((c) => c.kind === "markdown")
            .map((c) => (
              <p className="whitespace-pre-wrap" key={c.id}>
                {c.source}
              </p>
            ))}
        </div>
      )}

      <div ref={content} className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1">
            <main
              hidden={compactInspect}
              className="relative flex min-w-0 flex-1 flex-col bg-canvas"
              aria-label={view === "live" ? "Document" : view === "canvas" ? "Canvas" : "Steps"}
            >
              <div className="min-h-0 flex-1" hidden={view !== "live"}><LiveEditor visible={view === "live"} onSelectStep={selectStep} /></div>
              <div
                hidden={view === "live"}
                key={view}
                className="view-content content-enter min-h-0 flex-1 bg-canvas"
              >
                {view === "canvas" ? (
                  <CanvasView
                    strongStep={strongStep}
                    weakStep={weakStep}
                    selectedRel={selectedRel}
                    onSelectStep={selectStep}
                    onSelectRel={selectRel}
                    tool={tool}
                    zoom={zoom}
                    showGrid={grid}
                    strokes={ink.present}
                    onCommit={commitInk}
                    onZoom={setZoom}
                    fitRequest={fitRequest}
                    viewport={viewport}
                  />
                ) : (
                  <div className="h-full overflow-y-auto">
                    <StepsView
                      strongStep={strongStep}
                      onSelectStep={selectStep}
                    />
                  </div>
                )}
              </div>

              <div
                className="canvas-footer grid shrink-0"
                data-visible={view === "canvas"}
                aria-hidden={view !== "canvas"}
                inert={view !== "canvas"}
              >
                <div className="min-h-0 overflow-hidden">
                  <div
                    ref={canvasFooter}
                    className="flex shrink-0 flex-col items-center gap-1 px-2 pb-2 pt-1"
                  >
                    <div
                      ref={canvasTools}
                      className="relative flex max-w-full items-center gap-0.5 rounded-[22px] material p-1"
                      role="toolbar"
                      aria-label="Canvas tools"
                    >
                      <span
                        aria-hidden="true"
                        className="tool-selector pointer-events-none absolute bottom-1 left-0 top-1 rounded-full bg-accent/12"
                        style={{
                          width: toolIndicator.width,
                          transform: `translateX(${toolIndicator.left}px)`,
                        }}
                      />
                      {tools.map((t) => (
                        <Btn
                          key={t.id}
                          pressed={tool === t.id}
                          onClick={() =>
                            t.id === "equation"
                              ? setEditing(true)
                              : setTool(t.id)
                          }
                          label={t.label}
                          title={
                            t.id === "equation" ? "Edit equations" : t.label
                          }
                          className="relative rounded-full !bg-transparent"
                        >
                          {Icons[t.id]}
                          <span
                            className="tool-label grid text-[13px]"
                            aria-hidden="true"
                            style={{
                              gridTemplateColumns:
                                width - (docked && open ? 344 : 0) >= 640
                                  ? "1fr"
                                  : "0fr",
                              opacity:
                                width - (docked && open ? 344 : 0) >= 640
                                  ? 1
                                  : 0,
                            }}
                          >
                            <span className="min-w-0 overflow-hidden whitespace-nowrap">
                              {t.label}
                            </span>
                          </span>
                        </Btn>
                      ))}
                      <Btn
                        label="New object"
                        onClick={() => setEditing(true)}
                        title="Add equation or text"
                        className="rounded-full"
                      >
                        {Icons.plus}
                      </Btn>
                    </div>
                    <div
                      className="flex items-center gap-1 rounded-[22px] material p-1 text-[13px]"
                      role="group"
                      aria-label="Canvas zoom"
                    >
                      <Btn
                        label="Zoom out"
                        onClick={() =>
                          setZoom((z) => Math.max(0.25, +(z - 0.25).toFixed(2)))
                        }
                      >
                        −
                      </Btn>
                      <span className="w-11 text-center tabular-nums">
                        {Math.round(zoom * 100)}%
                      </span>
                      <Btn
                        label="Zoom in"
                        onClick={() =>
                          setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)))
                        }
                      >
                        +
                      </Btn>
                      <Btn onClick={() => setFitRequest((f) => f + 1)}>Fit</Btn>
                      <Btn
                        pressed={grid}
                        onClick={() => setGrid((g) => !g)}
                        title="Dot grid"
                      >
                        Grid
                      </Btn>
                    </div>
                  </div>
                </div>
              </div>
            </main>

          {docked && (
            <aside
              className="t-panel shrink-0 overflow-hidden hairline"
              style={{ width: open ? 344 : 0, borderLeftWidth: open ? 1 : 0 }}
              inert={!open}
              aria-hidden={!open}
              aria-label="Inspector"
            >
              <div className="h-full w-[343px]">{inspectorEl}</div>
            </aside>
          )}
          {compactInspect && (
            <aside className="min-w-0 flex-1" aria-label="Inspector">
              <button
                onClick={() => setOpen(false)}
                className="press min-h-11 w-full border-b hairline bg-panel px-4 text-left font-medium text-accent"
              >
                ‹ Back to canvas
              </button>
              <div className="h-[calc(100%-44px)]">{inspectorEl}</div>
            </aside>
          )}
        </div>

        {bottomPanel && (
          <aside
            className="t-panel flex shrink-0 flex-col overflow-hidden hairline bg-canvas"
            style={{
              height: open ? (expanded ? contentHeight * 0.45 : 72) : 0,
              borderTopWidth: open ? 1 : 0,
            }}
            inert={!open}
            aria-hidden={!open}
            aria-label="Inspector"
          >
            {expanded ? (
              <div className="min-h-0 flex-1">
                <div className="flex justify-end border-b hairline px-2">
                  <Btn onClick={() => setExpanded(false)}>Collapse ▾</Btn>
                </div>
                <div className="h-[calc(100%-45px)]">{inspectorEl}</div>
              </div>
            ) : (
              <button
                onClick={() => setExpanded(true)}
                className="flex h-[72px] items-center justify-between gap-3 px-4 text-left"
              >
                <div>
                  <div className="text-[17px] leading-[22px] font-semibold">
                    {title}
                  </div>
                  {target === "idle" ? (
                    <span className="text-[13px] text-ink2">
                      Select a step or relation
                    </span>
                  ) : (
                    <StatusLine state={liveState} className="text-[13px]" />
                  )}
                  <span className="sr-only">{stateMeta[liveState].zh}</span>
                </div>
                <span className="text-accent font-medium">Details ▴</span>
              </button>
            )}
          </aside>
        )}
      </div>
    </div>
  )
}
