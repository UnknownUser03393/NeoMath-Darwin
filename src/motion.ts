import { flushSync } from "react-dom"

let active: { skipTransition: () => void } | undefined
let revision = 0

export function transitionPage(
  update: () => void,
  direction: "forward" | "back" = "forward",
  scope: "page" | "content" = "page",
) {
  const current = ++revision
  active?.skipTransition()
  active = undefined
  document.documentElement.dataset.pageDirection = direction
  document.documentElement.dataset.transitionScope = scope
  if (
    scope === "content" ||
    !document.startViewTransition ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    flushSync(update)
    return
  }
  const transition = document.startViewTransition(() => {
    if (current === revision) flushSync(update)
  })
  active = transition
  const clear = () => {
    if (active === transition) active = undefined
  }
  void transition.finished.then(clear, clear)
}
