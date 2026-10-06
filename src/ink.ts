export type Pt = [number, number]
export type Strokes = Pt[][]
export type InkHistory = { past: Strokes[]; present: Strokes; future: Strokes[] }
export type InkAction = { type: "commit" | "reset"; strokes: Strokes } | {
  type: "undo" | "redo"
}

export function inkReducer(state: InkHistory, action: InkAction): InkHistory {
  if (action.type === "reset")
    return { past: [], present: action.strokes, future: [] }
  if (action.type === "commit") {
    if (action.strokes === state.present) return state
    return {
      past: [...state.past, state.present],
      present: action.strokes,
      future: [],
    }
  }
  if (action.type === "undo" && state.past.length) {
    return {
      past: state.past.slice(0, -1),
      present: state.past[state.past.length - 1],
      future: [state.present, ...state.future],
    }
  }
  if (action.type === "redo" && state.future.length) {
    return {
      past: [...state.past, state.present],
      present: state.future[0],
      future: state.future.slice(1),
    }
  }
  return state
}

// Hit-test segments, including fast strokes with widely spaced sampled points.
export function eraseAt(strokes: Strokes, p: Pt, radius: number): Strokes {
  const distance = (a: Pt, b: Pt) => {
    const dx = b[0] - a[0],
      dy = b[1] - a[1]
    const length = dx * dx + dy * dy
    const t = length
      ? Math.max(
          0,
          Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length),
        )
      : 0
    return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
  }
  const next = strokes.filter(
    (stroke) =>
      !stroke.some(
        (point, i) => distance(stroke[Math.max(0, i - 1)], point) <= radius,
      ),
  )
  return next.length === strokes.length ? strokes : next
}
