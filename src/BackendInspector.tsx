import { useEffect, useRef, useState } from "react"
import {
  call,
  compareProbe,
  formatSet,
  resolveSource,
  type Probe,
  type ProbeTrace,
} from "./backend"
import { stateMeta } from "./data"
import { useWorkspace, traceState } from "./workspace"
import type { Target } from "./Inspector"
import { M, StatusLine } from "./ui"

function Evaluation({ probe }: { probe: Probe }) {
  return (
    <div className="space-y-3 rounded-[14px] bg-subtle p-3 text-[13px]">
      {(["previous", "current"] as const).map((side) => (
        <div key={side}>
          <p className="text-ink2">
            {side === "previous" ? "Before" : "After"}
          </p>
          <p>
            <M>{`${probe[`${side}LeftValue`] ?? "—"} = ${probe[`${side}RightValue`] ?? "—"}`}</M> ·{" "}
            {probe[`${side}Defined`] === false
              ? "Undefined"
              : probe[`${side}PredicateResult`] === true
                ? "True"
                : probe[`${side}PredicateResult`] === false
                  ? "False"
                  : "Unverified"}
          </p>
        </div>
      ))}
    </div>
  )
}
export default function BackendInspector({
  target,
  pinned,
  onPin,
  onClose,
}: {
  target: Target
  pinned: boolean
  onPin: () => void
  onClose: () => void
  onGo?: (target: Target) => void
  compact?: boolean
}) {
  const { document, steps, trace } = useWorkspace()
  const index = typeof target === "number" ? target - 1 : 0
  const [tab, setTab] = useState("overview")
  const [value, setValue] = useState("0")
  const [probe, setProbe] = useState<Probe | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const request = useRef(0)
  useEffect(() => {
    request.current++
    setProbe(null)
    setError("")
    setBusy(false)
  }, [target, document])
  const relation = trace?.relations[index - 1]
  const state = trace?.states[index]
  const status = traceState(trace, index)
  const run = async () => {
    const token = ++request.current
    setBusy(true)
    setError("")
    setProbe(null)
    try {
      const cells =
        document?.cells
          .filter((c) => c.kind !== "markdown")
          .slice(0, index + 1) ?? []
      const source = await resolveSource(cells)
      const result = await call<ProbeTrace>("evaluateProbe", {
        document: { source },
        probe: { value },
      })
      if (token === request.current) setProbe(compareProbe(result))
    } catch (e) {
      if (token === request.current) setError((e as Error).message)
    } finally {
      if (token === request.current) setBusy(false)
    }
  }
  return (
    <div className="flex h-full flex-col bg-canvas">
      <header className="flex min-h-14 items-center gap-2 border-b hairline px-4">
        <h2 className="mr-auto font-semibold">
          {target === "idle" ? "Inspect" : `Step ${index + 1}`}
        </h2>
        <button
          className="press min-h-11 px-2 text-accent"
          onClick={onPin}
          aria-pressed={pinned}
        >
          Pin
        </button>
        <button className="press min-h-11 px-2 text-accent" onClick={onClose}>
          Close
        </button>
      </header>
      <div className="flex gap-1 p-3" role="tablist">
        {["overview", "evidence", "details"].map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`press min-h-11 flex-1 rounded-[10px] capitalize ${
              tab === t ? "bg-panel text-accent" : "text-ink2"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      <div
        className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4"
        role="tabpanel"
      >
        {target === "idle" ? (
          <p className="text-ink2">Select a step or relation to inspect.</p>
        ) : (
          <>
            <StatusLine state={status} />
            <M className="block overflow-x-auto text-[24px]">
              {steps[index]?.src ?? ""}
            </M>
            {tab === "overview" && (
              <div className="space-y-4 rounded-[18px] bg-panel p-4">
                <p className="text-[13px] text-ink2">
                  {relation?.reason ??
                    (trace
                      ? stateMeta[status].en
                      : "Run Check to compute the mathematical state.")}
                </p>
                <div>
                  <p className="text-[12px] text-ink2">Solution set</p>
                  <M>{formatSet(state?.solutionSet)}</M>
                </div>
                <div>
                  <p className="text-[12px] text-ink2">Domain</p>
                  <M>{formatSet(state?.domain)}</M>
                </div>
                {!!relation?.lostSolutions?.length && (
                  <p>Lost: {relation.lostSolutions.join(", ")}</p>
                )}
                {!!relation?.gainedSolutions?.length && (
                  <p>Gained: {relation.gainedSolutions.join(", ")}</p>
                )}
              </div>
            )}
            {tab === "evidence" && (
              <>
                <h3 className="font-semibold">Automatic witness</h3>
                {relation?.probe ? (
                  <>
                    <p>x = {relation.probe.value}</p>
                    <Evaluation probe={relation.probe} />
                  </>
                ) : (
                  <p className="text-[13px] text-ink2">
                    {trace
                      ? "No witness returned for this relation."
                      : "Run Check to obtain evidence."}
                  </p>
                )}
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    void run()
                  }}
                  className="space-y-3"
                >
                  <label className="block text-[13px]">
                    Manual probe · x
                    <input
                      required
                      aria-label="Probe value"
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      className="mt-2 min-h-11 w-full rounded-[10px] bg-panel px-3"
                    />
                  </label>
                  <button
                    disabled={busy || !value.trim()}
                    className="press min-h-11 rounded-full bg-accent/10 px-4 text-accent"
                  >
                    {busy ? "Evaluating…" : "Evaluate"}
                  </button>
                </form>
                {probe && <Evaluation probe={probe} />}
                {error && (
                  <p role="alert" className="text-bad">
                    {error}
                  </p>
                )}
              </>
            )}
            {tab === "details" && (
              <div className="space-y-3 rounded-[18px] bg-panel p-4 text-[13px]">
                <p>Engine: C++ MathCore</p>
                <p>Trust: {state?.trustLevel ?? "Not checked"}</p>
                <pre className="overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(
                    { state, relation, diagnostic: trace?.diagnostics[index] },
                    null,
                    2,
                  )}
                </pre>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
