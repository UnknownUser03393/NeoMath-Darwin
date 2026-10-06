export type Fr = { n: bigint; d: bigint }

const gcd = (a: bigint, b: bigint): bigint =>
  b === 0n ? (a < 0n ? -a : a) : gcd(b, a % b)
export const fr = (n: bigint, d = 1n): Fr => {
  if (d === 0n) throw new RangeError("Zero denominator")
  const g = gcd(n, d) || 1n
  const s = d < 0n ? -1n : 1n
  return { n: (s * n) / g, d: (s * d) / g }
}
const sub = (a: Fr, b: Fr) => fr(a.n * b.d - b.n * a.d, a.d * b.d)
const mul = (a: Fr, b: Fr) => fr(a.n * b.n, a.d * b.d)
const same = (a: Fr, b: Fr) => a.n === b.n && a.d === b.d
const ONE = fr(1n)
const ZERO = fr(0n)

export const frStr = (v: Fr) => {
  const t = v.d === 1n ? `${v.n}` : `${v.n}/${v.d}`
  return t.replace("-", "−")
}

export function parseRational(raw: string): Fr | null {
  const s = raw.trim().replace(/[−–]/g, "-")
  const m = /^(-?\d+)(?:\/(\d+))?$/.exec(s)
  if (!m) return null
  const d = m[2] ? BigInt(m[2]) : 1n
  if (d === 0n) return null
  return fr(BigInt(m[1]), d)
}

export type Evaluation = { left: Fr; right: Fr; holds: boolean }

export interface Step {
  n: number
  src: string
  evaluate: (x: Fr) => Evaluation
  solutions: string
}

const mk = (l: Fr, r: Fr): Evaluation => ({
  left: l,
  right: r,
  holds: same(l, r),
})

export const steps: Step[] = [
  {
    n: 1,
    src: "x(x − 1) = 0",
    solutions: "{0, 1}",
    evaluate: (x) => mk(mul(x, sub(x, ONE)), ZERO),
  },
  {
    n: 2,
    src: "x − 1 = 0",
    solutions: "{1}",
    evaluate: (x) => mk(sub(x, ONE), ZERO),
  },
  { n: 3, src: "x = 1", solutions: "{1}", evaluate: (x) => mk(x, ONE) },
]

export type StateKey = "initial" | "lostSolution" | "tainted" | "unchecked" | "equivalent" | "gainedSolution" | "domainShift" | "unverified"

export interface StateMeta {
  en: string
  zh: string
  tone: "ok" | "warn" | "bad" | "none"
}

export const stateMeta: Record<StateKey, StateMeta> = {
  unchecked: { en: "Not checked", zh: "尚未检查", tone: "none" },
  equivalent: { en: "Equivalent", zh: "等价", tone: "ok" },
  gainedSolution: { en: "Extraneous solution", zh: "增解", tone: "bad" },
  domainShift: { en: "Domain changed", zh: "定义域改变", tone: "bad" },
  unverified: { en: "Unverified", zh: "无法验证", tone: "warn" },
  initial: { en: "Initial state", zh: "初始状态", tone: "none" },
  lostSolution: { en: "Lost solution", zh: "丢解", tone: "bad" },
  tainted: { en: "Affected by Step 2", zh: "受步骤2影响", tone: "warn" },
}

export type RelId = number

export interface Relation {
  id: RelId
  from: number
  to: number
  state: StateKey
  explanation: string
  witnessX: Fr | null
  localNote?: string
}

export const relations: Record<RelId, Relation> = {
  12: {
    id: 12,
    from: 1,
    to: 2,
    state: "lostSolution",
    explanation: "Dividing by x removes the case x = 0.",
    witnessX: fr(0n),
  },
  23: {
    id: 23,
    from: 2,
    to: 3,
    state: "tainted",
    explanation:
      "This step is consistent with the previous line, but the chain already lost a solution at Step 1 → 2.",
    witnessX: null,
    localNote:
      "Locally equivalent: x − 1 = 0 and x = 1 have the same solution set.",
  },
}

export const relationForStep = (n: number) =>
  Object.values(relations).find((r) => r.to === n) ?? null
