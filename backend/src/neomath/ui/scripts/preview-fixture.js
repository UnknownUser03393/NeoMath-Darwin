// Development-only visual fixture. It is inert unless the URL has ?preview=1.
if (new URLSearchParams(window.location.search).get("preview") === "1") {
  const source = "x(x - 1) = 0\nx - 1 = 0\nx = 1";
  const demos = {
    "lost-root": { title: "Demo 1 · 丢根", source },
    "extraneous-root": { title: "Demo 2 · 平方增根", source: "sqrt(x) = x - 2\nx = (x - 2)^2" },
    "domain-expansion": { title: "Demo 3 · 定义域扩大", source: "(x - 1) / (x - 1) = 1\n1 = 1" },
    "semantic-completion": { title: "Demo 4 · 语义补全", source: "x^2 - 4 = 0" },
  };
  const domain = { kind: "all_real", excluded: [], lower: null, upper: null };
  const trace = {
    ok: true,
    result: {
      states: [
        { source: "x(x - 1) = 0", canonical: "x * (x - 1) = 0", domain,
          solutionSet: { kind: "finite", values: ["0", "1"], excluded: [] },
          verificationStatus: "verified", trustLevel: "exact_core" },
        { source: "x - 1 = 0", canonical: "x - 1 = 0", domain,
          solutionSet: { kind: "finite", values: ["1"], excluded: [] },
          verificationStatus: "verified", trustLevel: "exact_core" },
        { source: "x = 1", canonical: "x = 1", domain,
          solutionSet: { kind: "finite", values: ["1"], excluded: [] },
          verificationStatus: "verified", trustLevel: "exact_core" },
      ],
      relations: [
        { relation: "forward_implication", lostSolutions: ["0"], gainedSolutions: [],
          domainExpanded: false, domainShrunk: false, reason: "solutions_lost" },
        { relation: "equivalent", lostSolutions: [], gainedSolutions: [],
          domainExpanded: false, domainShrunk: false, reason: "solution_set_and_domain_preserved" },
      ],
      diagnostics: [
        { status: "valid", title: "起点", message: "已建立精确数学状态" },
        { status: "root_fault", title: "根本问题", message: "丢失了解 x = 0" },
        { status: "tainted", title: "受前一步影响", message: "当前步骤基于已经改变的数学状态" },
      ],
      activeProbe: {
        value: "0", previousDefined: true, currentDefined: true,
        previousPredicateResult: true, currentPredicateResult: false, reason: "lost_solution",
      },
      breakpointStep: 1,
    },
    metrics: { durationMs: 0.08, cacheHits: 0 },
  };
  const completions = {
    ok: true,
    result: [{ id: "solve", label: "求解", risk: "safe", available: true,
      reason: "verified_solution_set", preview: "x = 1" }],
  };
  window.NEOMATH_STARTUP = { demo: "lost-root", demos };
  window.pywebview = {
    api: {
      runTrace: async () => trace,
      analyzeDocument: async () => trace,
      replay: async () => trace,
      getCompletions: async () => completions,
      getCapabilities: async () => ({ ok: true, result: { core: "C++20" } }),
      getRecentDocuments: async () => ({ ok: true, result: [] }),
      requestAiExplanation: async () => ({
        ok: true,
        text: "在这里试入 x = 0：它在上一步成立，在这一步不再成立，所以发生了丢根。",
        source: "local",
      }),
      stop: async () => ({ ok: true }),
    },
  };
}

