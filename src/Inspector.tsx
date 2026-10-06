import { useState } from "react"
import {
  frStr,
  parseRational,
  relations,
  stateMeta,
  steps,
  type Evaluation,
  type Fr,
  type RelId,
  type Step,
} from "./data"
import { Chip, M, StatusLine, toneTint } from "./ui"

type ResultTarget = "initial" | RelId
export type Target = "idle" | ResultTarget
type Tab = "overview" | "evidence" | "details"

const tabs: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence" },
  { id: "details", label: "Details" },
]

function Section({
  title,
  children,
  bare,
}: {
  title: string
  children: React.ReactNode
  bare?: boolean
}) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="px-1 text-[15px] leading-5 font-semibold text-ink2">
        {title}
      </h3>
      {bare ? (
        children
      ) : (
        <div className="flex flex-col gap-3 rounded-[18px] bg-panel p-4">
          {children}
        </div>
      )}
    </section>
  )
}

function Verdict({ ok }: { ok: boolean }) {
  return (
    <span className={`font-semibold ${ok ? "text-ok" : "text-bad"}`}>
      {ok ? "True" : "False"}
    </span>
  )
}

function Compare({ before, after }: { before: Step | null; after: Step }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3">
      {before && (
        <div className="rounded-[14px] bg-subtle p-3 min-w-0">
          <div className="text-[12px] leading-[17px] text-ink3">
            Before · Step {before.n}
          </div>
          <M className="block text-[21px] mt-1 overflow-x-auto whitespace-nowrap">
            {before.src}
          </M>
        </div>
      )}
      <div className="rounded-[14px] bg-subtle p-3 min-w-0">
        <div className="text-[12px] leading-[17px] text-ink3">
          {before ? "After" : "Equation"} · Step {after.n}
        </div>
        <M className="block text-[21px] mt-1 overflow-x-auto whitespace-nowrap">
          {after.src}
        </M>
      </div>
    </div>
  )
}

function Solutions({ before, after }: { before: Step | null; after: Step }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3">
      {before && (
        <div className="min-w-0">
          <div className="text-[12px] leading-[17px] text-ink3">
            Before · Step {before.n} · Solution set
          </div>
          <M className="text-[21px]">{before.solutions}</M>
        </div>
      )}
      <div className="min-w-0">
        <div className="text-[12px] leading-[17px] text-ink3">
          {before ? `After · Step ${after.n} · Solution set` : "Solutions"}
        </div>
        <M className="text-[21px]">{after.solutions}</M>
      </div>
    </div>
  )
}

function EvalRow({ label, step, x }: { label: string; step: Step; x: Fr }) {
  const e: Evaluation = step.evaluate(x)
  return (
    <div className="rounded-[10px] bg-subtle p-3 text-[15px]">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-medium">{label}</span>
        <Verdict ok={e.holds} />
      </div>
      <div className="mt-1 break-words text-ink2">
        Defined · left <M>{frStr(e.left)}</M>, right <M>{frStr(e.right)}</M>
      </div>
    </div>
  )
}

function Witness({ relId }: { relId: RelId }) {
  const rel = relations[relId]
  const [open, setOpen] = useState(false)
  const before = steps[rel.from - 1]
  const after = steps[rel.to - 1]
  if (!rel.witnessX)
    return (
      <p className="text-ink2">
        Not applicable — no divergence was found in this step. The upstream
        witness belongs to Step 1 → 2.
      </p>
    )
  const x = rel.witnessX
  const b = before.evaluate(x)
  const a = after.evaluate(x)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <div>
          <div className="text-[12px] leading-[17px] text-ink3">
            Witness · automatic
          </div>
          <M className="text-[28px] leading-9">{`x = ${frStr(x)}`}</M>
        </div>
        <div className="flex gap-5 pb-1">
          <div>
            <div className="text-[12px] leading-[17px] text-ink3">Before</div>
            <Verdict ok={b.holds} />
          </div>
          <div>
            <div className="text-[12px] leading-[17px] text-ink3">After</div>
            <Verdict ok={a.holds} />
          </div>
        </div>
      </div>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="press self-start min-h-11 rounded-full bg-accent/10 px-5 font-medium text-accent hover:bg-accent/15"
      >
        {open ? "Hide substitution" : "Substitute"}
      </button>
      {open && (
        <div className="t-content flex flex-col gap-2">
          <EvalRow label={`Before · Step ${before.n}`} step={before} x={x} />
          <EvalRow label={`After · Step ${after.n}`} step={after} x={x} />
        </div>
      )}
    </div>
  )
}

function Probe({ relId }: { relId: RelId | null }) {
  const [text, setText] = useState("")
  const [storedResult, setResult] = useState<{
    target: RelId | null
    value: { x: Fr; list: { label: string; step: Step }[] } | "invalid"
  } | null>(null)
  const result = storedResult?.target === relId ? storedResult.value : null
  const rel = relId ? relations[relId] : null
  const targets = rel
    ? [
        { label: `Before · Step ${rel.from}`, step: steps[rel.from - 1] },
        { label: `After · Step ${rel.to}`, step: steps[rel.to - 1] },
      ]
    : [{ label: "Step 1", step: steps[0] }]

  const run = () => {
    const x = parseRational(text)
    setResult({ target: relId, value: x ? { x, list: targets } : "invalid" })
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <label htmlFor="probe" className="font-medium whitespace-nowrap">
          Try <M>x</M> =
        </label>
        <input
          id="probe"
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setResult(null)
          }}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.nativeEvent.isComposing &&
              e.keyCode !== 229
            )
              run()
          }}
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          inputMode="text"
          placeholder="e.g. 2 or −1/2"
          className="min-h-11 min-w-0 flex-1 rounded-[12px] bg-subtle px-3 font-math text-[17px]"
        />
        <button
          onClick={run}
          className="press min-h-11 rounded-full bg-accent px-5 font-medium text-onaccent"
        >
          {rel ? "Compare" : "Evaluate"}
        </button>
      </div>
      {result === "invalid" && (
        <p className="text-bad" role="alert">
          Enter an integer or a fraction such as 3/2.
        </p>
      )}
      {result && result !== "invalid" && (
        <div className="t-content flex flex-col gap-2">
          <div className="text-[12px] leading-[17px] text-ink3">
            Manual probe · does not replace the automatic witness
          </div>
          {result.list.map((t) => (
            <EvalRow key={t.label} label={t.label} step={t.step} x={result.x} />
          ))}
        </div>
      )}
      <p className="text-[12px] leading-[17px] text-ink3">
        A single test value does not prove equivalence.
      </p>
    </div>
  )
}

function Review({ onClose }: { onClose: () => void }) {
  const opts = [
    [
      "Replace this step",
      "Keep the step ID, update its source from the last correct upstream state, then recheck every later step.",
    ],
    [
      "Start a new group from Step 1",
      "Branch from the correct prefix and keep this group for comparison.",
    ],
    [
      "Edit manually",
      "Return to ink or source editing with the fault location kept.",
    ],
  ]
  return (
    <div
      className="t-content rounded-[18px] bg-panel p-3 flex flex-col gap-2"
      role="group"
      aria-label="Review this step"
    >
      {opts.map(([t, d]) => (
        <button
          key={t}
          disabled
          title="Demo fixture — editing is not connected"
          className="min-h-11 rounded-[12px] bg-subtle px-3 py-2 text-left"
        >
          <div className="font-medium">{t}</div>
          <div className="text-[12px] leading-[17px] text-ink2">{d}</div>
        </button>
      ))}
      <p className="px-3 text-[12px] text-ink3">
        All three actions are unavailable: editing is not connected in this
        demo.
      </p>
      <button
        onClick={onClose}
        className="press min-h-11 self-start rounded-[10px] px-3 font-medium text-accent"
      >
        Close
      </button>
    </div>
  )
}

function Overview({
  target,
  onGo,
}: {
  target: ResultTarget
  onGo: (t: Target) => void
}) {
  const [review, setReview] = useState(false)
  if (target === "initial") {
    return (
      <div className="flex flex-col gap-5">
        <Section title="Conclusion" bare>
          <StatusLine state="initial" />
          <p className="text-[12px] text-ink3">
            Demo fixture · not computed by a kernel · freshness unavailable
          </p>
          <p className="text-ink2">
            First valid state. It has a solution set and domain but no relation
            to a previous step.
          </p>
        </Section>
        <Section title="Equation">
          <Compare before={null} after={steps[0]} />
        </Section>
        <Section title="Solutions and domain">
          <Solutions before={null} after={steps[0]} />
          <p className="text-ink2">
            Domain: <M>ℝ</M>
          </p>
        </Section>
        <Section title="Conditions">
          <p className="text-ink2">None. No transformation was applied.</p>
        </Section>
      </div>
    )
  }
  const rel = relations[target]
  const meta = stateMeta[rel.state]
  const before = steps[rel.from - 1]
  const after = steps[rel.to - 1]
  return (
    <div className="flex flex-col gap-5">
      <Section title="Conclusion" bare>
        <div className={`rounded-[14px] p-3 ${toneTint[meta.tone]}`}>
          <div className="flex items-baseline justify-between gap-2">
            <StatusLine state={rel.state} className="text-[17px]" />
            <span className="text-[12px] leading-[17px] text-ink3">
              {meta.zh}
            </span>
          </div>
          <p className="mt-1">{rel.explanation}</p>
          {rel.localNote && <p className="mt-1 text-ink2">{rel.localNote}</p>}
          <p className="mt-2 text-[12px] leading-[17px] text-ink3">
            Demo fixture · not computed by a kernel · freshness unavailable
          </p>
        </div>
      </Section>
      <Section title="Before / After">
        <Compare before={before} after={after} />
      </Section>
      <Section title="Solutions and domain">
        <Solutions before={before} after={after} />
        <p className="text-ink2">
          Domain: <M>ℝ</M> before and after.
        </p>
      </Section>
      <Section title="Conditions">
        <p className="text-ink2">For this transformation: none recorded.</p>
      </Section>
      <Section title="Witness">
        <Witness relId={rel.id} />
      </Section>
      <Section title="Next">
        <div className="flex flex-wrap gap-2">
          {rel.id === 12 ? (
            <button
              onClick={() => setReview((r) => !r)}
              aria-expanded={review}
              className="press min-h-11 rounded-full bg-accent px-5 font-medium text-onaccent"
            >
              Review this step
            </button>
          ) : (
            <button
              onClick={() => onGo(12)}
              className="press min-h-11 rounded-full bg-accent px-5 font-medium text-onaccent"
            >
              Go to Step 1 → 2
            </button>
          )}
        </div>
        {review && <Review onClose={() => setReview(false)} />}
      </Section>
    </div>
  )
}

function Details({ target }: { target: ResultTarget }) {
  const rel = target === "initial" ? null : relations[target]
  const rows: [string, string][] = [
    ["Source", "Demo data · design fixture"],
    ["Freshness", "Not applicable (no kernel connected)"],
    ["Relation", rel ? `${rel.from} → ${rel.to}` : "None (first step)"],
    ["State", stateMeta[rel ? rel.state : "initial"].en],
    ["Certificate", "None"],
    ["Engine", "Not connected"],
  ]
  return (
    <div className="flex flex-col gap-4">
      <dl className="flex flex-col divide-y hairline rounded-[18px] bg-panel px-4">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 py-2">
            <dt className="text-ink2">{k}</dt>
            <dd className="text-right">{v}</dd>
          </div>
        ))}
      </dl>
      <button
        disabled
        title="Nothing to copy from a fixture"
        className="min-h-11 self-start rounded-[10px] bg-subtle px-4 font-medium text-ink3"
      >
        Copy diagnostics
      </button>
      <p className="text-[12px] text-ink3">
        No kernel diagnostics exist for this fixture.
      </p>
    </div>
  )
}

export default function Inspector({
  target,
  pinned,
  onPin,
  onClose,
  onGo,
  compact,
}: {
  target: Target
  pinned: boolean
  onPin: () => void
  onClose: () => void
  onGo: (t: Target) => void
  compact: boolean
}) {
  const [tab, setTab] = useState<Tab>("overview")
  if (target === "idle")
    return (
      <div className="flex h-full flex-col gap-4 bg-canvas p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-[17px] font-semibold">Inspect</h2>
          <button
            onClick={onClose}
            aria-label="Close inspector"
            className="press min-h-11 min-w-11 text-xl text-accent"
          >
            ×
          </button>
        </div>
        <p className="text-ink2">Select a step or relation to inspect it.</p>
        <button
          onClick={() => onGo(12)}
          className="press min-h-11 rounded-full bg-accent px-4 text-onaccent"
        >
          Demo: locate lost solution
        </button>
      </div>
    )
  const title =
    target === "initial"
      ? "Step 1"
      : `Step ${relations[target].from} → ${relations[target].to}`
  const state = target === "initial" ? "initial" : relations[target].state
  const pad = compact ? "px-4" : "px-5"

  return (
    <div className="flex h-full min-h-0 flex-col bg-canvas">
      <div
        className={`${pad} pt-3 pb-2 flex items-center justify-between gap-2 material`}
      >
        <div className="min-w-0">
          <h2 className="truncate text-[17px] leading-[22px] font-semibold">
            {title}
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            <StatusLine state={state} className="text-[13px]" />
            {pinned && <Chip>Pinned to {title}</Chip>}
          </div>
          <p className="text-[12px] leading-[17px] text-ink3">
            Demo fixture · no kernel · freshness unavailable
          </p>
        </div>
        <div className="flex shrink-0">
          <button
            onClick={onPin}
            aria-pressed={pinned}
            className={`press min-h-11 min-w-11 rounded-full px-3 text-[13px] font-semibold ${
              pinned ? "bg-subtle text-accent" : "text-ink2"
            }`}
          >
            {pinned ? "Unpin" : "Pin"}
          </button>
          <button
            onClick={onClose}
            aria-label="Close inspector"
            className="press min-h-11 min-w-11 rounded-full text-ink2 text-xl"
          >
            ×
          </button>
        </div>
      </div>
      <div className={`${pad} pb-3 material border-b hairline`}>
        <div
          role="tablist"
          aria-label="Inspector sections"
          className="relative flex rounded-[10px] bg-subtle p-0.5"
        >
          <span
            aria-hidden="true"
            className="inspector-tab-indicator pointer-events-none absolute bottom-0.5 left-0.5 top-0.5 rounded-[8px] bg-elevated"
            style={{ width: "calc((100% - 4px) / 3)", transform: `translateX(${tabs.findIndex((t) => t.id === tab) * 100}%)` }}
          />
          {tabs.map((t) => (
            <button
              key={t.id}
              role="tab"
              id={`tab-${t.id}`}
              aria-controls={`panel-${t.id}`}
              tabIndex={tab === t.id ? 0 : -1}
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              onKeyDown={(e) => {
                if (
                  e.nativeEvent.isComposing ||
                  !["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)
                )
                  return
                e.preventDefault()
                const index = tabs.findIndex((item) => item.id === tab)
                const next =
                  e.key === "Home"
                    ? 0
                    : e.key === "End"
                      ? tabs.length - 1
                      : (index +
                          (e.key === "ArrowRight" ? 1 : -1) +
                          tabs.length) %
                        tabs.length
                setTab(tabs[next].id)
                document.getElementById(`tab-${tabs[next].id}`)?.focus()
              }}
              className={`press relative min-h-11 flex-1 rounded-[8px] px-2 text-[13px] font-semibold ${
                tab === t.id ? "text-ink" : "text-ink2"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <div
          className="inspector-panel-track flex h-full"
          style={{ transform: `translateX(-${tabs.findIndex((t) => t.id === tab) * 100}%)` }}
        >
        <div
          id="panel-overview"
          role="tabpanel"
          aria-labelledby="tab-overview"
          tabIndex={0}
          aria-hidden={tab !== "overview"}
          inert={tab !== "overview"}
          className={`h-full w-full shrink-0 overflow-y-auto ${pad} py-4`}
        >
          <Overview target={target} onGo={onGo} />
        </div>
        <div
          id="panel-evidence"
          role="tabpanel"
          aria-labelledby="tab-evidence"
          tabIndex={0}
          aria-hidden={tab !== "evidence"}
          inert={tab !== "evidence"}
          className={`h-full w-full shrink-0 overflow-y-auto ${pad} py-4`}
        >
          <div className="flex flex-col gap-5">
            {target !== "initial" && (
              <Section title="Witness">
                <Witness relId={target} />
              </Section>
            )}
            <Section
              title={target === "initial" ? "Evaluate this equation" : "Probe"}
            >
              <Probe relId={target === "initial" ? null : target} />
            </Section>
          </div>
        </div>
        <div
          id="panel-details"
          role="tabpanel"
          aria-labelledby="tab-details"
          tabIndex={0}
          aria-hidden={tab !== "details"}
          inert={tab !== "details"}
          className={`h-full w-full shrink-0 overflow-y-auto ${pad} py-4`}
        >
          <Details target={target} />
        </div>
        </div>
      </div>
    </div>
  )
}
