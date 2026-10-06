export interface ErrorEdge { parent: number; child: number }
export interface AnchorGeometry { cx: number; cy: number; left: number }

/** Notebook trace is linear: tainted steps inherit the preceding root fault. */
export function errorDependencies(statuses: string[]): ErrorEdge[] {
  let fault: number | null = null
  const edges: ErrorEdge[] = []
  statuses.forEach((status, step) => {
    if (status === "root_fault" || status === "parse_error") fault = step
    else if (status === "tainted" && fault !== null) edges.push({ parent: fault, child: step })
    else fault = null
  })
  return edges
}

export function connectorPath(edges: ErrorEdge[], geometry: Map<number, AnchorGeometry>): string {
  const kidsOf = new Map<number, number[]>()
  for (const edge of edges) {
    const kids = kidsOf.get(edge.parent) ?? []
    kids.push(edge.child)
    kidsOf.set(edge.parent, kids)
  }
  const paths: string[] = []
  for (const [parentId, kids] of kidsOf) {
    const parent = geometry.get(parentId)
    if (!parent) continue
    const branches = kids.flatMap(id => {
      const child = geometry.get(id)
      if (!child) return []
      const targetX = child.left - 8
      const span = targetX - parent.cx, rise = child.cy - parent.cy
      if (span <= 0 || rise <= 0) return []
      return [{ cy: child.cy, targetX, rad: Math.min(12, span, rise) }]
    }).sort((a, b) => a.cy - b.cy)
    if (!branches.length) continue
    const last = branches[branches.length - 1]
    const cap = Math.min(12, last.targetX - parent.cx)
    paths.push(`M ${parent.cx + cap} ${parent.cy} H ${parent.cx} V ${last.cy - last.rad} Q ${parent.cx} ${last.cy} ${parent.cx + last.rad} ${last.cy} H ${last.targetX}`)
    for (const branch of branches.slice(0, -1)) {
      paths.push(`M ${parent.cx} ${branch.cy - branch.rad} Q ${parent.cx} ${branch.cy} ${parent.cx + branch.rad} ${branch.cy} H ${branch.targetX}`)
    }
  }
  return paths.join(" ")
}
