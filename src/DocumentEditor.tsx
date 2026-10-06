import { useWorkspace } from "./workspace"
import MathTools from "./MathTools"
import { M } from "./ui"
import { useState } from "react"
export default function DocumentEditor({ onClose }: { onClose: () => void }) {
  const { document, update, setError, setComposing, check, analysis } = useWorkspace()
  const [focused, setFocused] = useState<string | null>(null)
  if (!document) return null
  const change = (id: string, source: string) =>
    update({
      cells: document.cells.map((c) => ({
        ...c,
        source: c.id === id ? source : c.source,
        executionState: "idle",
        result: undefined,
      })),
    })
  return (
    <section
      className="max-h-[50dvh] shrink-0 space-y-3 overflow-auto border-b hairline bg-panel p-4"
      aria-label="Document editor"
    >
      <div className="flex items-center gap-3">
        <label className="flex min-w-0 flex-1 items-center gap-3 text-[13px]">
          Title
          <input
            className="min-h-11 min-w-0 flex-1 rounded-[10px] bg-subtle px-3"
            value={document.title}
            onChange={(e) => update({ title: e.target.value })}
          />
        </label>
        <button className="press min-h-11 px-3 text-accent" onClick={onClose}>
          Done
        </button>
      </div>
      {document.cells.map((c, i) => (
        <div key={c.id} className="space-y-2"><div className="flex items-center gap-2">
          <span className="w-6 shrink-0 text-[12px] text-ink2">{i + 1}</span>
          <textarea
            aria-label={`${
              c.kind === "markdown" ? "Text" : c.kind === "transform" ? "Transform" : "Equation"
            } ${i + 1}`}
            rows={c.kind === "markdown" ? 3 : 1}
            value={c.source}
            onFocus={() => setFocused(c.id)}
            onCompositionStart={() => setComposing(true)}
            onCompositionEnd={() => setComposing(false)}
            onKeyDown={e => {
              if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); void check() }
            }}
            onChange={(e) => change(c.id, e.target.value)}
            className="min-h-11 min-w-0 flex-1 rounded-[10px] bg-subtle p-3 font-mono text-[14px]"
          />
          <button
            aria-label={`Delete cell ${i + 1}`}
            className="press min-h-11 px-3 text-bad"
            onClick={() =>
              update({
                cells: document.cells.filter((cell) => cell.id !== c.id),
              })
            }
          >
            ×
          </button>
        </div>{c.kind === "math" && <div className="overflow-x-auto pl-8 pb-2" aria-label={`Equation preview ${i + 1}`}><M className="text-[22px]">{c.source}</M></div>}</div>
      ))}
      {analysis?.parsed.steps.map((step, i) => step.error && <p role="alert" key={i} className="text-[13px] text-bad">Step {i + 1}: {step.error.message}{step.error.expected?.length ? ` · expected ${step.error.expected.join(", ")}` : ""}</p>)}
      <MathTools cellId={focused} />
      {(["math", "markdown"] as const).map((kind) => (
        <button
          key={kind}
          className="press mr-2 min-h-11 rounded-full bg-subtle px-4 text-accent"
          onClick={() => {
            setError("")
            update({
              cells: [
                ...document.cells,
                {
                  id: crypto.randomUUID(),
                  kind,
                  source: kind === "math" ? "x = 1" : "",
                  executionState: "idle",
                  outputCollapsed: false,
                },
              ],
            })
          }}
        >
          + {kind === "math" ? "Equation" : "Text"}
        </button>
      ))}
    </section>
  )
}
