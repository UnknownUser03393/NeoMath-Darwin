import { useLayoutEffect, useRef, type RefObject } from "react"
import { connectorPath, errorDependencies, type AnchorGeometry } from "./error-connectors"
import type { Trace } from "./backend"

export default function ErrorConnectors({ host, trace, visible, revision }: { host: RefObject<HTMLDivElement | null>; trace: Trace | null; visible: boolean; revision: string }) {
  const svg = useRef<SVGSVGElement>(null)
  const path = useRef<SVGPathElement>(null)
  useLayoutEffect(() => {
    // Child layout effects run before the parent's host ref is attached.
    const root = host.current ?? svg.current?.parentElement
    if (!root) return
    let frame: number | null = null
    let alive = true
    const edges = errorDependencies(trace?.diagnostics.map(item => item.status) ?? [])
    const measure = () => {
      frame = null
      const base = root.getBoundingClientRect()
      const geometry = new Map<number, AnchorGeometry>()
      for (const anchor of root.querySelectorAll<HTMLElement>("[data-error-step]")) {
        const rect = anchor.getBoundingClientRect()
        geometry.set(Number(anchor.dataset.errorStep), { cx: rect.left + rect.width / 2 - base.left, cy: rect.top + rect.height / 2 - base.top, left: rect.left - base.left })
      }
      svg.current?.setAttribute("width", String(base.width))
      svg.current?.setAttribute("height", String(base.height))
      const nextPath = visible ? connectorPath(edges, geometry) : ""
      path.current?.setAttribute("d", nextPath)
    }
    const schedule = () => { if (alive && frame === null) frame = requestAnimationFrame(measure) }
    const flush = () => {
      if (frame !== null) cancelAnimationFrame(frame)
      measure()
    }
    const resize = new ResizeObserver(schedule)
    resize.observe(root)
    const observed = new WeakSet<Element>()
    const observeContent = () => {
      for (const element of root.querySelectorAll(".cm-editor, .cm-scroller, .cm-content")) {
        if (!observed.has(element)) { observed.add(element); resize.observe(element) }
      }
    }
    // CodeMirror replaces decorations and virtualizes lines during editing/scrolling.
    const mutation = new MutationObserver(() => { observeContent(); schedule() })
    mutation.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "data-check"] })
    root.addEventListener("scroll", schedule, true)
    root.addEventListener("live-preview-layout", flush)
    window.addEventListener("resize", schedule)
    // Vite CSS updates move anchors without changing React props or the host size.
    const styles = new MutationObserver(schedule)
    styles.observe(document.head, { childList: true, subtree: true, characterData: true, attributes: true })
    document.fonts.addEventListener("loadingdone", schedule)
    observeContent()
    void document.fonts.ready.then(schedule)
    schedule()
    return () => { alive = false; resize.disconnect(); mutation.disconnect(); styles.disconnect(); document.fonts.removeEventListener("loadingdone", schedule); root.removeEventListener("scroll", schedule, true); root.removeEventListener("live-preview-layout", flush); window.removeEventListener("resize", schedule); if (frame !== null) cancelAnimationFrame(frame) }
  }, [host, trace, visible, revision])
  return <svg ref={svg} className="error-connectors" aria-hidden="true"><path ref={path} /></svg>
}
