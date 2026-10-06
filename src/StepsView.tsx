import { stateMeta } from "./data"
import { useWorkspace, traceState } from "./workspace"
import { M, StatusLine, toneTint } from "./ui"

export default function StepsView({
  strongStep,
  onSelectStep,
}: {
  strongStep: number | null
  onSelectStep: (n: number) => void
}) {
  const { steps, relationForStep, trace } = useWorkspace()
  return (
    <ol className="mx-auto flex w-full max-w-2xl flex-col gap-3 px-4 py-6 sm:px-6">
      {steps.map((s) => {
        const rel = relationForStep(s.n)
        const state = traceState(trace, s.n - 1)
        const meta = stateMeta[state]
        const on = strongStep === s.n
        return (
          <li key={s.n}>
            <button
              onClick={() => onSelectStep(s.n)}
              aria-current={on ? "step" : undefined}
              aria-label={`Step ${s.n}: ${s.src}. ${meta.en}`}
              className="press w-full min-h-16 rounded-[14px] border-2 bg-panel p-4 text-left"
              style={{
                borderColor: on
                  ? "var(--accent-foreground)"
                  : "var(--separator-decorative)",
              }}
            >
              <div className="flex items-start gap-4">
                <span className="w-5 pt-2 text-[12px] leading-[17px] text-ink3">
                  {s.n}
                </span>
                <div className="min-w-0 flex-1">
                  <M className="block text-[26px] leading-9 overflow-x-auto whitespace-nowrap">
                    {s.src}
                  </M>
                  <div
                    className={`mt-2 inline-flex rounded-[10px] px-2 py-1 ${toneTint[meta.tone]}`}
                  >
                    <StatusLine state={state} className="text-[13px]" />
                  </div>
                  <p className="mt-1 text-[12px] leading-[17px] text-ink2">
                    {rel
                      ? `Relation from Step ${rel.from}`
                      : "Initial state — no relation to a previous step"}
                  </p>
                </div>
              </div>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
