import { useMemo, type ReactNode } from 'react'
import { renderMath } from './math-format'
import { stateMeta, type StateKey } from './data'

export function M({ children, className = '' }: { children: string; className?: string }) {
  const rendered = useMemo(() => renderMath(children), [children])
  if (rendered.html) return <span className={`math-render ${className}`} data-math-source={children} dangerouslySetInnerHTML={{ __html: rendered.html }} />
  return (
    <span className={`font-math ${className}`} data-math-fallback title={rendered.error ?? undefined}>
      {children}
    </span>
  )
}

const toneText = { ok: 'text-ok', warn: 'text-warn', bad: 'text-bad', none: 'text-none' } as const
const toneTint = { ok: 'tint-ok', warn: 'tint-warn', bad: 'tint-bad', none: 'tint-none' } as const
export { toneText, toneTint }

export function Glyph({ kind, size = 18 }: { kind: StateKey; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 18 18',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
  if (kind === 'lostSolution')
    return (
      <svg {...common}>
        <path d="M9 16V9M9 9L4 3M9 9l5-6" />
        <circle cx="14" cy="3" r="1" fill="currentColor" />
      </svg>
    )
  if (kind === 'tainted')
    return (
      <svg {...common}>
        <path d="M9 2v3M9 8v2M9 13v3" strokeDasharray="1 3" />
        <path d="M4 9h10" />
      </svg>
    )
  return (
    <svg {...common}>
      <circle cx="9" cy="9" r="6" />
      <circle cx="9" cy="9" r="1.6" fill="currentColor" />
    </svg>
  )
}

export function StatusLine({ state, className = '' }: { state: StateKey; className?: string }) {
  const m = stateMeta[state]
  return (
    <span className={`inline-flex items-center gap-1.5 font-medium ${toneText[m.tone]} ${className}`}>
      <Glyph kind={state} />
      {m.en}
    </span>
  )
}

export function Chip({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center rounded-full bg-subtle px-2 text-[12px] leading-[17px] py-0.5 text-ink2"
    >
      {children}
    </span>
  )
}
