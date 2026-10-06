import { useLayoutEffect, useRef, useState, type MutableRefObject } from "react"
import { stateMeta, type RelId } from "./data"
import { eraseAt, type Pt, type Strokes } from "./ink"
import { Glyph, M, toneText } from "./ui"
import { useWorkspace, traceState } from "./workspace"

export type Tool = "pen" | "eraser" | "select" | "equation"
const ROW = 112
const WORLD = { width: 1600, height: 1200 }
const toPath = (pts: Pt[]) =>
  pts.length === 1
    ? `M${pts[0][0]} ${pts[0][1]}l0.1 0.1`
    : pts
        .map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`)
        .join(" ")

export default function CanvasView({
  strongStep,
  weakStep,
  selectedRel,
  onSelectStep,
  onSelectRel,
  tool,
  zoom,
  showGrid,
  strokes,
  onCommit,
  onZoom,
  fitRequest,
  viewport,
}: {
  strongStep: number | null
  weakStep: number | null
  selectedRel: RelId | null
  onSelectStep: (n: number) => void
  onSelectRel: (id: RelId) => void
  tool: Tool
  zoom: number
  showGrid: boolean
  strokes: Strokes
  onCommit: (strokes: Strokes) => void
  onZoom: (zoom: number) => void
  fitRequest: number
  viewport: MutableRefObject<Pt>
}) {
  const { steps, relations, relationForStep, trace } = useWorkspace()
  const world = useRef<HTMLDivElement>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const gesture = useRef<{ id: number; strokes: Strokes } | null>(null)
  const [draft, setDraft] = useState<Strokes | null>(null)
  const touches = useRef(new Map<number, Pt>())
  const moved = useRef(false)
  const previousZoom = useRef(zoom)
  const pendingScroll = useRef<Pt | null>(null)
  const lastFit = useRef(fitRequest)
  const inking = tool === "pen" || tool === "eraser"

  useLayoutEffect(() => {
    scroller.current!.scrollTo(...viewport.current)
  }, [viewport])
  useLayoutEffect(() => {
    const el = scroller.current!
    if (previousZoom.current !== zoom || pendingScroll.current) {
      const ratio = zoom / previousZoom.current
      const next = pendingScroll.current ?? [
        (el.scrollLeft + el.clientWidth / 2) * ratio - el.clientWidth / 2,
        (el.scrollTop + el.clientHeight / 2) * ratio - el.clientHeight / 2,
      ]
      el.scrollTo(next[0], next[1])
      pendingScroll.current = null
      previousZoom.current = zoom
    }
  }, [zoom])
  useLayoutEffect(() => {
    if (lastFit.current === fitRequest) return
    lastFit.current = fitRequest
    const el = scroller.current!
    let right = 600,
      bottom = 56 + steps.length * ROW
    for (const stroke of strokes)
      for (const p of stroke) {
        right = Math.max(right, p[0] + 24)
        bottom = Math.max(bottom, p[1] + 24)
      }
    const next = Math.max(
      0.25,
      Math.min(
        4,
        (el.clientWidth - 32) / right,
        (el.clientHeight - 32) / bottom,
      ),
    )
    pendingScroll.current = [0, 0]
    el.scrollTo(0, 0)
    onZoom(next)
  }, [fitRequest, onZoom, strokes])

  const pt = (e: React.PointerEvent): Pt => {
    const r = world.current!.getBoundingClientRect()
    return [(e.clientX - r.left) / zoom, (e.clientY - r.top) / zoom]
  }
  const touchShape = () => {
    const points = [...touches.current.values()]
    const a = points[0],
      b = points[1] ?? a
    return {
      center: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] as Pt,
      distance: Math.hypot(a[0] - b[0], a[1] - b[1]),
    }
  }
  const down = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === "touch") {
      if (gesture.current) return
      if (!touches.current.size) moved.current = false
      touches.current.set(e.pointerId, [e.clientX, e.clientY])
      return
    }
    if (!inking || e.button !== 0 || gesture.current) return
    touches.current.clear()
    e.currentTarget.setPointerCapture(e.pointerId)
    const next =
      tool === "pen"
        ? [...strokes, [pt(e)]]
        : eraseAt(strokes, pt(e), 12 / zoom)
    gesture.current = { id: e.pointerId, strokes: next }
    setDraft(next)
  }
  const move = (e: React.PointerEvent<HTMLDivElement>) => {
    if (touches.current.has(e.pointerId)) {
      const oldPoint = touches.current.get(e.pointerId)!
      if (
        !moved.current &&
        Math.hypot(e.clientX - oldPoint[0], e.clientY - oldPoint[1]) < 4
      )
        return
      const before = touchShape()
      touches.current.set(e.pointerId, [e.clientX, e.clientY])
      const after = touchShape()
      moved.current = true
      e.currentTarget.setPointerCapture(e.pointerId)
      const el = scroller.current!
      const r = el.getBoundingClientRect()
      const nextZoom =
        before.distance && after.distance
          ? Math.max(
              0.25,
              Math.min(4, (zoom * after.distance) / before.distance),
            )
          : zoom
      const ratio = nextZoom / zoom
      const next: Pt = [
        (el.scrollLeft + before.center[0] - r.left) * ratio -
          after.center[0] +
          r.left,
        (el.scrollTop + before.center[1] - r.top) * ratio -
          after.center[1] +
          r.top,
      ]
      if (nextZoom !== zoom) {
        pendingScroll.current = next
        onZoom(nextZoom)
      } else el.scrollTo(...next)
      return
    }
    const active = gesture.current
    if (active?.id !== e.pointerId) return
    const p = pt(e)
    active.strokes =
      tool === "pen"
        ? [
            ...active.strokes.slice(0, -1),
            [...active.strokes[active.strokes.length - 1], p],
          ]
        : eraseAt(active.strokes, p, 12 / zoom)
    setDraft(active.strokes)
  }
  const finish = (e: React.PointerEvent, cancelled = false) => {
    touches.current.delete(e.pointerId)
    if (gesture.current?.id !== e.pointerId) return
    if (!cancelled) onCommit(gesture.current.strokes)
    gesture.current = null
    setDraft(null)
  }

  return (
    <div
      ref={scroller}
      className="canvas-viewport relative h-full w-full overflow-auto"
      style={{ touchAction: "none" }}
      onScroll={(e) => {
        viewport.current = [
          e.currentTarget.scrollLeft,
          e.currentTarget.scrollTop,
        ]
      }}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={(e) => finish(e)}
      onPointerCancel={(e) => finish(e, true)}
      onLostPointerCapture={(e) => finish(e, true)}
      onClickCapture={(e) => {
        if (moved.current) {
          e.stopPropagation()
          moved.current = false
        }
      }}
    >
      <div style={{ width: WORLD.width * zoom, height: WORLD.height * zoom }}>
        <div
          ref={world}
          role="group"
          aria-label="Canvas objects and ink"
          className={`relative origin-top-left ${showGrid ? "dotgrid" : ""}`}
          style={{
            width: WORLD.width,
            height: WORLD.height,
            transform: `scale(${zoom})`,
            backgroundSize: `${24 * Math.max(1, Math.ceil(0.5 / zoom))}px ${24 * Math.max(1, Math.ceil(0.5 / zoom))}px`,
          }}
        >
          <svg
            className="pointer-events-none absolute inset-0"
            width={WORLD.width}
            height={WORLD.height}
            role="img"
            aria-label={`${(draft ?? strokes).length} ink strokes, not recognized as equations`}
          >
            {(draft ?? strokes).map((s, i) => (
              <path
                key={i}
                d={toPath(s)}
                fill="none"
                stroke="var(--label-primary)"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}
          </svg>
          {steps.map((s, i) => {
            const strong = strongStep === s.n,
              weak = weakStep === s.n
            const state = traceState(trace, s.n - 1)
            return (
              <div
                key={s.n}
                className="absolute left-10 flex items-center"
                style={{ top: 56 + i * ROW }}
              >
                <span className="w-10 pr-3 text-right text-[12px] text-ink3 select-none">
                  {s.n}
                </span>
                <button
                  onClick={() => onSelectStep(s.n)}
                  aria-current={strong ? "step" : undefined}
                  aria-label={`Step ${s.n}: ${s.src}. ${stateMeta[state].en}`}
                  className="press relative flex min-h-14 items-center rounded-[10px] border-2 border-solid px-3 py-2.5"
                  style={{
                    borderColor:
                      strong || weak
                        ? "var(--accent-foreground)"
                        : "transparent",
                    background: strong
                      ? "color-mix(in srgb, var(--accent-foreground) 8%, transparent)"
                      : undefined,
                    opacity: weak ? 0.7 : 1,
                  }}
                >
                  <M className="text-[26px] leading-9 whitespace-nowrap">
                    {s.src}
                  </M>
                </button>
                {zoom >= 0.6 && state === "tainted" && (
                  <span className="ml-3 inline-flex items-center gap-1.5 text-[13px] font-medium text-warn">
                    <Glyph kind="tainted" size={16} />
                    {stateMeta[state].en}
                  </span>
                )}
              </div>
            )
          })}
          {Object.values(relations).map((rel) => {
            const meta = stateMeta[rel.state]
            return (
              <button
                key={rel.id}
                onClick={() => onSelectRel(rel.id)}
                aria-current={selectedRel === rel.id ? "true" : undefined}
                aria-label={`Relation Step ${rel.from} to ${rel.to}: ${meta.en}`}
                className={`press absolute left-20 flex min-h-11 items-center gap-2 rounded-[10px] px-2 ${toneText[meta.tone]} ${
                  selectedRel === rel.id ? "bg-subtle" : "hover:bg-subtle"
                }`}
                style={{
                  top: 116 + steps.findIndex((s) => s.n === rel.from) * ROW,
                }}
              >
                <span
                  className="h-8 w-0 border-l-2"
                  style={{
                    borderStyle: rel.state === "tainted" ? "dashed" : "solid",
                  }}
                />
                <Glyph kind={rel.state} />
                {zoom >= 0.6 && (
                  <span className="text-[13px] font-medium">{meta.en}</span>
                )}
              </button>
            )
          })}
          {inking && (
            <div
              className="absolute inset-0 z-10"
              role="group"
              aria-label={
                tool === "pen"
                  ? "Ink layer: draw with pen or mouse; touch to pan"
                  : "Ink layer: erase with pen or mouse; touch to pan"
              }
              style={{ cursor: tool === "pen" ? "crosshair" : "cell" }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
