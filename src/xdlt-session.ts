import { call, callEnvelope } from "./backend.ts"
export interface HtmlPatch {
  op: "replace" | "remove" | "insert" | "replace-document"
  renderId?: string
  parentRenderId?: string
  index?: number
  html?: string
}
export interface XdltResult {
  revision?: number
  previousRevision?: number
  html: string
  diagnostics: { code?: string; message: string; severity?: string }[]
  graph: unknown
  semanticDocument: unknown
  sourceMap: { renderId: string; sourceRange: { start: number; end: number } }[]
  htmlPatches?: HtmlPatch[]
  invalidatedSemanticIds?: string[]
  stats?: { reusedVerification: number; recomputedVerification: number; reusedExecution: number; recomputedExecution: number; reusedParsing: boolean; patchFallback: boolean }
}
export class XdltSession {
  private sessionId: string | null = null
  private queue: Promise<unknown> = Promise.resolve()
  private disposed = false
  private revision = 0
  private base?: string
  constructor(base?: string) { this.base = base }
  update(content: string, options: { verify: boolean; execute: boolean }) {
    const task = this.queue.then(async () => {
      if (this.disposed) throw new Error("Session closed")
      const create = async () => {
        const result = await callEnvelope<XdltResult>("createXdltSession", { content, mode: "fragment", ...options }, this.base)
        if (!result.sessionId) throw new Error("Missing XDLT session ID")
        this.sessionId = result.sessionId
        return { ...result.result, revision: ++this.revision }
      }
      if (!this.sessionId) return create()
      try {
        const result = await call<XdltResult>("updateXdltSession", { sessionId: this.sessionId, content, ...options }, this.base)
        const previousRevision = this.revision
        return { ...result, previousRevision, revision: ++this.revision }
      }
      catch (error) {
        if (/unknown session/i.test((error as Error).message)) { this.sessionId = null; return create() }
        throw error
      }
    })
    this.queue = task.catch(() => {})
    return task
  }
  async dispose() {
    this.disposed = true
    await this.queue
    if (this.sessionId) await call("destroyXdltSession", { sessionId: this.sessionId }, this.base)
    this.sessionId = null
  }
}
export function applyHtmlPatches(root: HTMLElement, result: XdltResult): boolean {
  if (!result.htmlPatches) { root.innerHTML = result.html; return false }
  const find = (id?: string) => [...root.querySelectorAll<HTMLElement>("[data-xdlt-render-id], [data-xdlt-id]")].find(e => e.dataset.xdltRenderId === id || e.dataset.xdltId === id)
  try {
    for (const patch of result.htmlPatches) {
      if (patch.op === "replace-document") { root.innerHTML = patch.html ?? result.html; continue }
      const target = find(patch.op === "insert" ? patch.parentRenderId : patch.renderId)
      if (!target) throw new Error("Patch target missing")
      if (patch.op === "remove") { target.remove(); continue }
      const template = root.ownerDocument.createElement("template")
      template.innerHTML = patch.html ?? ""
      const nodes = [...template.content.childNodes]
      if (!nodes.length) throw new Error("Empty patch")
      if (patch.op === "replace") target.replaceWith(...nodes)
      else {
        const index = patch.index ?? -1
        if (index < 0 || index > target.children.length) throw new Error("Invalid patch index")
        const before = target.children[index] ?? null
        nodes.forEach(node => target.insertBefore(node, before))
      }
    }
    return true
  } catch { root.innerHTML = result.html; return false }
}
