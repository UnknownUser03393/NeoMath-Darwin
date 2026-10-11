const editor = document.querySelector("#source-editor");
const lineNumbers = document.querySelector("#line-numbers");
const traceCanvas = document.querySelector("#trace-canvas");
const titleInput = document.querySelector("#document-title");
const documentState = document.querySelector("#document-state");
const toast = document.querySelector("#toast");

function makeId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `neomath-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const state = {
  demos: {},
  activeDemo: "lost-root",
  trace: null,
  documentPath: null,
  documentId: makeId(),
  undo: [],
  redo: [],
  completion: null,
  visibleSteps: Infinity,
  selectedStep: null,
  dirty: false,
  debounce: null,
  autosaveTimer: null,
  autosaveSeconds: 15,
};

const REASON_MESSAGES = {
  solutions_lost: "这一步丢失了原来成立的解。",
  solutions_gained: "这一步加入了原方程不成立的新解。",
  domain_expanded: "这一步把原来没有定义的值纳入了范围。",
  domain_shrunk: "这一步排除了原来有定义的值。",
  solution_set_and_domain_preserved: "解集和定义域保持不变。",
  one_or_both_steps_unverified: "当前版本暂时无法证明这两步的关系。",
  solver_supports_degree_at_most_two: "当前版本只验证一次和二次方程。",
  square_root_form_not_supported: "当前版本暂不支持这种根式结构。",
  squared_equation_degree_limit: "平方后次数超过当前求解上限。",
  parse_error: "这一步需要先修正输入格式。",
  exact_rational_solver: "已用精确有理数求解。",
  not_a_supported_difference_of_squares: "当前不是可因式分解的差平方形式。",
  INTEGER_LIMIT: "整数超出 63 位安全范围，请拆分步骤或缩小系数。",
};

const GUIDANCE = {
  root_fault:
    "先不要继续往下推。用 Probe 代回前后两行，确认丢根/增根/定义域问题，再改这一步并重新检查。",
  tainted: "前面已经出现语义分叉，后面结果不可信。请先修复“根本问题”那一步。",
  unverified:
    "当前版本只保证：单变量 x、有理运算、一次/有有理根的二次方程、简单分式与线性根式。可改写成支持形式，或拆成更小步骤。",
  unsupported:
    "输入超出 V1 能力边界。试试只用 x、整数/分数、+ − × ÷ ^、sqrt(一次式) 和等式。",
  parse_error: "检查括号、未知函数名（如 sin）以及是否每行一个等式。",
  valid: "这一步解集与定义域可验证。可继续推导，或用语义补全查看安全操作。",
};

function api() {
  return window.pywebview?.api;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 1800);
}

function setBusy(busy) {
  document.querySelectorAll(".run-controls button").forEach((button) => {
    if (button.id !== "stop-button") button.disabled = busy;
  });
  document.querySelector("#core-status").lastChild.textContent =
    busy ? "MathCore 正在验证" : "C++ MathCore 已连接";
}

function meaningfulLines() {
  return editor.value.split(/\r?\n/).filter((line) => line.trim() && !line.trim().startsWith("#"));
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = String(value);
  return node.innerHTML;
}

function friendlyReason(code) {
  if (!code) return "当前步骤已检查";
  return REASON_MESSAGES[code] || REASON_MESSAGES[String(code).toUpperCase()] || String(code);
}

function refreshEditorChrome(faultStep = null) {
  const lines = editor.value.split(/\r?\n/);
  const count = Math.max(1, lines.length);
  const numbers = [];
  let expressionIndex = -1;
  for (let i = 0; i < count; i += 1) {
    const text = (lines[i] || "").trim();
    const isExpression = text && !text.startsWith("#");
    if (isExpression) expressionIndex += 1;
    const markFault = isExpression && faultStep != null && expressionIndex === faultStep;
    numbers.push(markFault ? `!${i + 1}` : String(i + 1));
  }
  lineNumbers.innerHTML = numbers
    .map((label) => {
      const fault = label.startsWith("!");
      const text = fault ? label.slice(1) : label;
      return fault
        ? `<span class="fault-line">${escapeHtml(text)}</span>`
        : `<span>${escapeHtml(text)}</span>`;
    })
    .join("<br>");
  document.querySelector("#line-count").textContent = `${meaningfulLines().length} 步`;
  editor.classList.toggle("editor-has-fault", faultStep != null);
}

function markDirty() {
  state.dirty = true;
  documentState.textContent = "未保存";
}

function pushUndo(previous) {
  if (state.undo.at(-1) !== previous) state.undo.push(previous);
  if (state.undo.length > 80) state.undo.shift();
  state.redo = [];
}

function loadSource(source, title, demo = null) {
  if (editor.value) pushUndo(editor.value);
  editor.value = source;
  titleInput.value = title;
  state.activeDemo = demo;
  state.visibleSteps = Infinity;
  state.selectedStep = null;
  state.dirty = false;
  documentState.textContent = "演示文档";
  refreshEditorChrome();
  document.querySelectorAll(".demo-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.demo === demo);
  });
  runTrace();
}

function formatSolution(solution) {
  if (!solution) return "—";
  if (solution.kind === "finite") return `{ ${solution.values.join(", ")} }`;
  if (solution.kind === "empty") return "∅";
  if (solution.kind === "all_real") return "ℝ";
  if (solution.kind === "all_real_excluding_finite") {
    return `ℝ \\ { ${solution.excluded.join(", ")} }`;
  }
  return "暂时无法验证";
}

function formatDomain(domain) {
  if (!domain) return "—";
  if (domain.kind === "all_real") return "ℝ";
  if (domain.kind === "real_excluding_finite") return `ℝ \\ { ${domain.excluded.join(", ")} }`;
  if (domain.kind === "interval") {
    return `${domain.lower ?? "−∞"} ≤ x ≤ ${domain.upper ?? "+∞"}`;
  }
  if (domain.kind === "empty") return "∅";
  return "暂时无法验证";
}

function formatPredicateEval(defined, holds, left, right) {
  const equation = left != null && right != null ? `${left} = ${right}　` : "";
  if (defined === false) return `${equation}未定义`;
  if (holds == null) return `${equation}—`;
  return `${equation}${holds ? "成立" : "不成立"}`;
}

function renderFormula(element, source) {
  const latex = source
    .replace(/\*/g, "\\cdot ")
    .replace(/sqrt\(([^()]*)\)/g, "\\sqrt{$1}")
    .replace(/\^(-?\d+)/g, "^{$1}")
    .replace(/\bor\b/g, "\\;\\text{或}\\;");
  if (window.katex) {
    try {
      window.katex.render(latex, element, { throwOnError: false, displayMode: false });
      return;
    } catch (_) {
      /* fall through */
    }
  }
  element.textContent = source;
}

function diagnosticCode(relation, status) {
  const lost = relation?.lostSolutions || [];
  const gained = relation?.gainedSolutions || [];
  if (lost.length) return "LOST ROOT";
  if (gained.length) return "EXTRANEOUS ROOT";
  if (relation?.domainExpanded || relation?.domainShrunk) return "DOMAIN SHIFT";
  if (status === "tainted") return "TAINTED";
  return "NOT EQUIVALENT";
}

function buildCellOutput(index, result) {
  const diagnostic = result.diagnostics[index] || { status: "unverified", title: "待检查", message: "" };
  const status = diagnostic.status;
  const relation = index > 0 ? result.relations?.[index - 1] : null;
  const previous = index > 0 ? result.states[index - 1] : null;
  const current = result.states[index];

  if (status === "root_fault" || (status === "tainted" && relation && (
    (relation.lostSolutions && relation.lostSolutions.length)
    || (relation.gainedSolutions && relation.gainedSolutions.length)
    || relation.domainExpanded
    || relation.domainShrunk
  ))) {
    const lost = relation?.lostSolutions || [];
    const gained = relation?.gainedSolutions || [];
    const code = diagnosticCode(relation, status);
    const probe = result.activeProbe;
    const output = document.createElement("div");
    output.className = "cell-output";
    output.innerHTML = `
      <div class="set-diff" aria-label="解集差异">
        <div><span>此前</span><strong>${escapeHtml(formatSolution(previous?.solutionSet))}</strong></div>
        <div><span>此后</span><strong>${escapeHtml(formatSolution(current?.solutionSet))}</strong></div>
        <div class="lost-value">
          <span>${lost.length ? "丢失" : gained.length ? "新增" : "变化"}</span>
          <strong>${escapeHtml(
            lost.length
              ? `− ${lost.join(", ")}`
              : gained.length
                ? `+ ${gained.join(", ")}`
                : friendlyReason(relation?.reason || diagnostic.message),
          )}</strong>
        </div>
      </div>
      <p class="cell-output-summary">${escapeHtml(friendlyReason(diagnostic.message || relation?.reason))}</p>
    `;
    if (probe?.value != null && (status === "root_fault" || index === result.breakpointStep)) {
      const witness = document.createElement("div");
      witness.className = "witness-inline";
      witness.innerHTML = `
        <div class="witness-heading">反例 / WITNESS · ${escapeHtml(code)}</div>
        <div class="witness-value">x = ${escapeHtml(String(probe.value))}</div>
        <div class="witness-checks">
          <div><span>原式</span><strong>${escapeHtml(formatPredicateEval(
            probe.previousDefined,
            probe.previousPredicateResult,
            probe.previousLeftValue,
            probe.previousRightValue,
          ))}</strong></div>
          <div class="failed"><span>新式</span><strong>${escapeHtml(formatPredicateEval(
            probe.currentDefined,
            probe.currentPredicateResult,
            probe.currentLeftValue,
            probe.currentRightValue,
          ))}</strong></div>
        </div>
      `;
      output.append(witness);
    }
    return output;
  }

  if (status === "valid" && index > 0 && (
    relation?.relation === "equivalent"
    || relation?.reason === "solution_set_and_domain_preserved"
  )) {
    const output = document.createElement("div");
    output.className = "cell-output equivalence";
    output.innerHTML = `<p class="cell-output-summary">等价变换 · 解集与定义域保持不变</p>`;
    return output;
  }

  if (status === "unverified" || status === "unsupported" || status === "parse_error") {
    const output = document.createElement("div");
    output.className = "cell-output unverified";
    output.innerHTML = `<p class="cell-output-summary">${escapeHtml(
      friendlyReason(diagnostic.message || relation?.reason || status),
    )} ${escapeHtml(GUIDANCE[status] || GUIDANCE.unverified)}</p>`;
    return output;
  }

  return null;
}

function rootFaultIndex(result) {
  const index = result?.diagnostics?.findIndex((item) => item.status === "root_fault");
  return index >= 0 ? index : null;
}

function selectStep(index, { scroll = false } = {}) {
  state.selectedStep = index;
  document.querySelectorAll(".step-card").forEach((card) => {
    card.classList.toggle("selected", Number(card.dataset.step) === index);
  });
  document.querySelectorAll(".trace-item").forEach((item) => {
    item.classList.toggle("selected", Number(item.dataset.step) === index);
  });
  if (state.trace) renderInspector(state.trace);
  if (scroll) {
    document.querySelector(`.step-card[data-step="${index}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function renderTrace(response) {
  if (!response?.ok) {
    const message = response?.error?.message || "MathCore 未返回结果";
    traceCanvas.innerHTML = `<div class="empty-state"><strong>无法运行</strong><span>${escapeHtml(message)}</span></div>`;
    showToast(message);
    return;
  }
  state.trace = response;
  const result = response.result;
  const states = result.states.slice(0, state.visibleSteps);
  const fault = rootFaultIndex(result);
  if (state.selectedStep == null || state.selectedStep >= states.length) {
    state.selectedStep = fault ?? Math.max(0, states.length - 1);
  }
  traceCanvas.innerHTML = "";
  states.forEach((mathState, index) => {
    const diagnostic = result.diagnostics[index] || { status: "unverified", title: "待检查", message: "" };
    const card = document.createElement("article");
    card.className = `step-card ${diagnostic.status}`;
    card.dataset.step = index;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `第 ${index + 1} 步 ${diagnostic.title || ""}`);
    if (index === state.selectedStep) card.classList.add("selected");

    const indexNode = document.createElement("span");
    indexNode.className = "step-index";
    indexNode.textContent = index + 1;

    const body = document.createElement("div");
    body.className = "step-card-body";
    const formula = document.createElement("div");
    formula.className = "formula";
    renderFormula(formula, mathState.canonical || mathState.source);
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `${formatSolution(mathState.solutionSet)} · ${formatDomain(mathState.domain)}`;
    body.append(formula, meta);
    const output = buildCellOutput(index, result);
    if (output) body.append(output);

    const badge = document.createElement("span");
    badge.className = `diagnostic-badge ${diagnostic.status}`;
    badge.textContent = diagnostic.title;

    card.append(indexNode, body, badge);
    card.addEventListener("click", () => selectStep(index));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectStep(index);
      }
    });
    traceCanvas.append(card);
  });
  refreshEditorChrome(fault);
  renderInspector(response);
}

function guidanceFor(status) {
  return GUIDANCE[status] || GUIDANCE.unverified;
}

function renderInspector(response) {
  const result = response.result;
  const selected = Math.min(
    state.selectedStep ?? result.states.length - 1,
    Math.min(result.states.length, state.visibleSteps) - 1,
  );
  const last = result.states[selected];
  const diagnostic = result.diagnostics[selected] || {};
  const relation = selected > 0 ? result.relations?.[selected - 1] : null;
  const root = result.diagnostics.find((item) => item.status === "root_fault");

  let statusText = "推导已验证";
  let summary = "当前可判定步骤保持语义";
  if (diagnostic.status === "root_fault") {
    statusText = "发现语义分叉";
    summary = friendlyReason(diagnostic.message || relation?.reason);
  } else if (diagnostic.status === "tainted") {
    statusText = "受前一步影响";
    summary = friendlyReason(diagnostic.message) || "建立在已改变的数学状态上";
  } else if (diagnostic.status === "unverified" || diagnostic.status === "unsupported") {
    statusText = "暂时无法验证";
    summary = friendlyReason(diagnostic.message || relation?.reason);
  } else if (root && selected > root) {
    statusText = "受前序分叉影响";
    summary = "请先修复更早的根本问题";
  }

  document.querySelector("#watch-status").textContent = statusText;
  document.querySelector("#watch-summary").textContent = summary;
  document.querySelector("#watch-solutions").textContent = formatSolution(last?.solutionSet);
  document.querySelector("#watch-domain").textContent = formatDomain(last?.domain);
  document.querySelector("#watch-trust").textContent =
    last?.trustLevel === "exact_core" ? "C++ 精确内核" : "暂时无法验证";
  document.querySelector("#watch-duration").textContent =
    `${Number(response.metrics?.durationMs || 0).toFixed(2)} ms`;

  const probe = result.activeProbe;
  const probeCard = document.querySelector("#probe-card");
  const showAutoProbe = Boolean(probe) && (
    diagnostic.status === "root_fault"
    || selected === result.breakpointStep
    || selected === rootFaultIndex(result)
  );
  probeCard.hidden = !showAutoProbe;
  if (showAutoProbe && probe) {
    document.querySelector("#probe-value").textContent = `x = ${probe.value}`;
    document.querySelector("#probe-before").textContent = formatPredicateEval(
      probe.previousDefined,
      probe.previousPredicateResult,
      probe.previousLeftValue,
      probe.previousRightValue,
    );
    document.querySelector("#probe-after").textContent = formatPredicateEval(
      probe.currentDefined,
      probe.currentPredicateResult,
      probe.currentLeftValue,
      probe.currentRightValue,
    );
    const reason = {
      lost_solution: "这个值证明该步丢失了一个原有解。",
      gained_solution: "这个值证明该步加入了一个新解。",
      domain_expansion: "这个值证明定义域在该步被扩大。",
      domain_shrink: "这个值证明定义域在该步被缩小。",
    };
    document.querySelector("#probe-reason").textContent = reason[probe.reason] || probe.reason;
  }

  const guidance = document.querySelector("#step-guidance");
  const guidanceText = document.querySelector("#step-guidance-text");
  const guideKey = diagnostic.status || (root ? "tainted" : "valid");
  guidance.hidden = false;
  guidanceText.textContent = guidanceFor(guideKey);

  const traceList = document.querySelector("#trace-list");
  traceList.innerHTML = "";
  result.diagnostics.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = `trace-item ${item.status}`;
    row.dataset.step = index;
    if (index === selected) row.classList.add("selected");
    row.innerHTML = `<strong>${index + 1}. ${escapeHtml(item.title)}</strong><span>${escapeHtml(friendlyReason(item.message))}</span>`;
    row.addEventListener("click", () => {
      selectStep(index, { scroll: true });
      activateTab("watch");
    });
    traceList.append(row);
  });
}

async function runTrace() {
  if (!api()) return;
  setBusy(true);
  try {
    const response = await api().runTrace({ document: { source: editor.value } });
    state.visibleSteps = Infinity;
    state.selectedStep = null;
    renderTrace(response);
    await refreshCompletion();
  } finally {
    setBusy(false);
  }
}

async function analyzeDebounced() {
  if (!api()) return;
  const response = await api().analyzeDocument({ document: { source: editor.value } });
  if (response?.ok) {
    state.trace = response;
    document.querySelector("#core-status").lastChild.textContent = "C++ MathCore 已连接";
    // Live light feedback: keep full step cards only after explicit Run, but
    // surface parse / unverified status on the current last step summary.
    const last = response.result?.diagnostics?.at(-1);
    if (last?.status === "parse_error" || last?.status === "unverified") {
      document.querySelector("#watch-status").textContent =
        last.status === "parse_error" ? "输入需要修正" : "暂时无法验证";
      document.querySelector("#watch-summary").textContent = friendlyReason(last.message);
      document.querySelector("#step-guidance").hidden = false;
      document.querySelector("#step-guidance-text").textContent = guidanceFor(last.status);
    }
  }
}

async function replay() {
  if (!api()) return;
  setBusy(true);
  try {
    const changedStep = Math.max(0, meaningfulLines().length - 1);
    const response = await api().replay({ document: { source: editor.value }, changedStep });
    state.visibleSteps = Infinity;
    state.selectedStep = null;
    renderTrace(response);
    showToast(`已从第 ${changedStep + 1} 步重新检查`);
  } finally {
    setBusy(false);
  }
}

function pickPreferredCompletion(available, hasRootFault) {
  if (!available.length) return null;
  const order = hasRootFault
    ? ["factor", "expand", "move_terms", "verify", "multiply", "divide", "square_both_sides", "solve"]
    : ["factor", "expand", "move_terms", "solve", "multiply", "divide", "square_both_sides", "verify"];
  for (const id of order) {
    const match = available.find((item) => item.id === id);
    if (match) return match;
  }
  return available[0];
}

async function refreshCompletion() {
  const bar = document.querySelector("#completion-bar");
  const select = document.querySelector("#completion-select");
  const step = Math.max(0, meaningfulLines().length - 1);
  const response = await api().getCompletions({ document: { source: editor.value }, step });
  const available = response?.result?.filter((item) => item.available) || [];
  const hasRootFault = Boolean(state.trace?.result?.diagnostics?.some((item) => item.status === "root_fault"));
  const completion = pickPreferredCompletion(available, hasRootFault);
  state.completion = completion || null;
  bar.hidden = !completion;
  select.innerHTML = "";
  available.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.label} · ${item.risk === "safe" ? "安全" : "需检查"}`;
    option.selected = item.id === completion?.id;
    select.append(option);
  });
  if (completion) {
    document.querySelector("#completion-preview").textContent = completion.preview;
  }
  select.onchange = () => {
    state.completion = available.find((item) => item.id === select.value) || null;
    document.querySelector("#completion-preview").textContent = state.completion?.preview || "";
  };
}

async function applyIntent(intent) {
  const step = Math.max(0, meaningfulLines().length - 1);
  const response = await api().executeTransformation({
    document: { source: editor.value },
    step,
    intent,
  });
  if (!response?.ok || !response.result?.applied) {
    showToast(response?.result?.reason || response?.error?.message || "无法应用补全");
    return;
  }
  pushUndo(editor.value);
  editor.value = `${editor.value.trim()}\n${response.result.source}`;
  markDirty();
  refreshEditorChrome(rootFaultIndex(state.trace?.result));
  showToast(`证书已验证：${response.result.certificate.rule}`);
  await runTrace();
}

async function applyCompletion() {
  if (!state.completion) return;
  await applyIntent({ intent: state.completion.id });
}

async function runAiCommand() {
  const input = document.querySelector("#ai-command");
  const command = input.value.trim();
  if (!command) return;
  const compiled = await api().compileAiIntent({ command });
  if (!compiled?.ok) {
    showToast(compiled?.error?.message || "命令无法安全识别");
    return;
  }
  await applyIntent(compiled.result);
  input.value = "";
}

async function runManualProbe() {
  if (!api()) return;
  const raw = document.querySelector("#manual-probe-input").value.trim();
  const resultNode = document.querySelector("#manual-probe-result");
  if (!raw) {
    resultNode.textContent = "请输入有理数，例如 0、2、-1/2。";
    return;
  }
  if (!editor.value.trim()) {
    resultNode.textContent = "请先写下至少一行推导。";
    return;
  }
  resultNode.textContent = "正在代回…";
  const response = await api().evaluateProbe({
    document: { source: editor.value },
    probe: { value: raw },
  });
  if (!response?.ok) {
    resultNode.innerHTML = `<span class="fail">${escapeHtml(response?.error?.message || "Probe 失败")}</span>`;
    return;
  }
  const steps = response.result?.steps || [];
  if (!steps.length) {
    resultNode.textContent = "没有可代回的步骤。";
    return;
  }
  const list = steps.map((step, index) => {
    const label = formatPredicateEval(
      step.defined,
      step.predicateResult,
      step.leftValue,
      step.rightValue,
    );
    const cls = step.defined === false || step.predicateResult === false ? "fail" : "pass";
    return `<li class="${cls}">第 ${index + 1} 步：${escapeHtml(label)}</li>`;
  }).join("");
  resultNode.innerHTML = `<div>x = ${escapeHtml(raw)} 逐步代回：</div><ol>${list}</ol>`;
  activateTab("watch");
}

function currentDocumentPayload() {
  return {
    formatVersion: 1,
    documentId: state.documentId,
    title: titleInput.value,
    source: editor.value,
    breakpoints: state.trace?.result?.breakpointStep != null ? [state.trace.result.breakpointStep] : [],
    recentProbe: state.trace?.result?.activeProbe || null,
    collapsedSteps: [],
  };
}

async function saveDocument() {
  const payload = {
    ...currentDocumentPayload(),
    path: state.documentPath,
  };
  const response = await api().saveDocument(payload);
  if (response?.ok) {
    state.documentPath = response.result.path;
    state.dirty = false;
    documentState.textContent = "已保存";
    showToast("文档已保存");
    loadRecent();
  }
}

async function openDocument(path = null) {
  const response = await api().openDocument(path ? { path } : {});
  if (!response?.ok) return;
  const documentData = response.result.document;
  state.documentPath = response.result.path;
  state.documentId = documentData.documentId;
  loadSource(documentData.source, documentData.title);
  documentState.textContent = "已保存";
}

async function loadRecent() {
  if (!api()) return;
  const response = await api().getRecentDocuments();
  const container = document.querySelector("#recent-documents");
  container.innerHTML = "";
  if (!response?.result?.length) {
    container.innerHTML = '<span class="muted">尚无最近文档</span>';
    return;
  }
  response.result.forEach((item) => {
    const button = document.createElement("button");
    button.className = "nav-item";
    button.textContent = `▱ ${item.title}`;
    button.title = item.path;
    button.addEventListener("click", () => openDocument(item.path));
    container.append(button);
  });
}

async function explain() {
  if (!state.trace) await runTrace();
  const response = await api().requestAiExplanation({ trace: state.trace });
  document.querySelector("#explanation").textContent = response.text || "暂时无法生成解释";
  document.querySelector("#explanation-source").textContent =
    response.source === "openai" ? `${response.model} · 数学结论来自 C++` : "本地离线解释 · C++ 真值";
  activateTab("explain");
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${name}`));
}

function renderSettingsForm(result) {
  const content = document.querySelector("#dialog-content");
  content.innerHTML = `
    <h2>设置</h2>
    <p class="settings-hint">
      数学核心始终离线。AI 仅用于把 C++ 已验证的诊断改写成学生语言，不能改变解集或定义域。
      目标交互形态见仓库 <code>ui-mockups/</code>（Notebook）；当前桌面壳在对齐该体验。
    </p>
    <form class="settings-form" id="settings-form">
      <label>API Key（OpenAI 兼容接口）
        <input id="settings-api-key" type="password" autocomplete="off"
          placeholder="${result.openaiConfigured ? `已配置 ${escapeHtml(result.openaiApiKeyMasked || "")}，留空则保持不变` : "可选，粘贴后保存"}">
      </label>
      <label>模型
        <input id="settings-model" type="text" value="${escapeHtml(result.openaiModel || "qwen-plus")}">
      </label>
      <label>自动保存间隔（秒）
        <input id="settings-autosave" type="number" min="5" max="600" value="${Number(result.autosaveSeconds || 15)}">
      </label>
      <p class="settings-hint">数据目录：${escapeHtml(result.dataDir || "本地用户目录")}</p>
      <div class="settings-actions">
        <button type="submit" class="primary">保存</button>
        <button type="button" id="settings-clear-key">清除已存密钥</button>
      </div>
    </form>
  `;

  document.querySelector("#settings-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!api()?.saveSettings) return;
    const keyInput = document.querySelector("#settings-api-key").value.trim();
    const payload = {
      openai_model: document.querySelector("#settings-model").value.trim() || "qwen-plus",
      autosave_seconds: Number(document.querySelector("#settings-autosave").value) || 15,
    };
    if (keyInput) payload.openai_api_key = keyInput;
    const response = await api().saveSettings(payload);
    if (!response?.ok) {
      showToast(response?.error?.message || "设置保存失败");
      return;
    }
    state.autosaveSeconds = Number(response.result?.autosaveSeconds || 15);
    restartAutosave();
    showToast(response.result?.openaiConfigured ? "已保存，AI 可用" : "已保存（离线解释）");
    document.querySelector("#info-dialog").close();
  });

  document.querySelector("#settings-clear-key").addEventListener("click", async () => {
    if (!api()?.saveSettings) return;
    const response = await api().saveSettings({ openai_api_key: "" });
    if (response?.ok) {
      showToast("已清除本地密钥");
      document.querySelector("#info-dialog").close();
    }
  });
}

async function showSettings() {
  // Open immediately so UI smoke and keyboard users see the dialog without waiting.
  renderSettingsForm({
    openaiConfigured: false,
    openaiModel: "qwen-plus",
    autosaveSeconds: state.autosaveSeconds || 15,
    dataDir: "",
  });
  document.querySelector("#info-dialog").showModal();
  try {
    const settings = await api()?.getSettings?.();
    if (settings?.ok && settings.result) {
      renderSettingsForm(settings.result);
    }
  } catch (_) {
    /* keep the empty form */
  }
}

function showInfo(kind) {
  if (kind === "settings") {
    showSettings();
    return;
  }
  const content = document.querySelector("#dialog-content");
  const copy = {
    tutorial: `<h2>六步调试数学</h2>
      <p><b>写下</b>每一步等式，按 <code>Ctrl+Enter</code> 运行。点击任一步查看 Watch / Probe。
      语义分叉会以内嵌「此前 / 此后 / 反例」呈现（对齐 Notebook 目标 UI）。
      修正后按 <code>Ctrl+R</code> 重新检查；也可在右侧手输 Probe 代回验证。</p>`,
    about: `<h2>NeoMath 1.0</h2>
      <p>数学动态调试环境 · The Debugger for Mathematics</p>
      <p>产品目标 UI：<code>ui-mockups/</code> Notebook。当前桌面版提供同一 C++ MathCore，并逐步对齐单元格诊断与 Witness 体验。</p>
      <p>栈：HTML/CSS/JS → pywebview → Python → pybind11 → C++20 MathCore</p>`,
  };
  content.innerHTML = copy[kind];
  document.querySelector("#info-dialog").showModal();
}

function restartAutosave() {
  clearInterval(state.autosaveTimer);
  state.autosaveTimer = setInterval(async () => {
    if (!state.dirty || !api()) return;
    const response = await api().autosaveDocument(currentDocumentPayload());
    if (response?.ok) documentState.textContent = "已自动保存";
  }, Math.max(5, Number(state.autosaveSeconds || 15)) * 1000);
}

editor.addEventListener("input", () => {
  refreshEditorChrome(rootFaultIndex(state.trace?.result));
  markDirty();
  clearTimeout(state.debounce);
  state.debounce = setTimeout(analyzeDebounced, 300);
});
titleInput.addEventListener("input", markDirty);
document.querySelector("#run-button").addEventListener("click", runTrace);
document.querySelector("#replay-button").addEventListener("click", replay);
document.querySelector("#save-button").addEventListener("click", saveDocument);
document.querySelector("#open-button").addEventListener("click", () => openDocument());
document.querySelector("#apply-completion").addEventListener("click", applyCompletion);
document.querySelector("#run-ai-command").addEventListener("click", runAiCommand);
document.querySelector("#ai-command").addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); runAiCommand(); }
});
document.querySelector("#explain-button").addEventListener("click", explain);
document.querySelector("#probe-button").addEventListener("click", () => {
  activateTab("watch");
  const target = document.querySelector("#probe-card:not([hidden])")
    || document.querySelector(".manual-probe");
  target?.scrollIntoView({ behavior: "smooth" });
});
document.querySelector("#manual-probe-button").addEventListener("click", runManualProbe);
document.querySelector("#manual-probe-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); runManualProbe(); }
});
document.querySelector("#step-button").addEventListener("click", async () => {
  if (!state.trace) await runTrace();
  state.visibleSteps = Math.min(
    (state.visibleSteps === Infinity ? 0 : state.visibleSteps) + 1,
    meaningfulLines().length,
  );
  state.selectedStep = Math.max(0, state.visibleSteps - 1);
  renderTrace(state.trace);
});
document.querySelector("#continue-button").addEventListener("click", () => {
  state.visibleSteps = Infinity;
  if (state.trace) renderTrace(state.trace);
});
document.querySelector("#stop-button").addEventListener("click", async () => {
  await api().stop();
  setBusy(false);
  showToast("已请求停止");
});
document.querySelector("#new-document").addEventListener("click", () => {
  state.documentPath = null;
  state.documentId = makeId();
  loadSource("2x + 3 = 7\n2x = 4\nx = 2", "未命名推导");
  markDirty();
});
document.querySelectorAll(".demo-button").forEach((button) => {
  button.addEventListener("click", () => {
    const demo = state.demos[button.dataset.demo];
    loadSource(demo.source, demo.title, button.dataset.demo);
  });
});
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.tab)));
document.querySelector("#tutorial-button").addEventListener("click", () => showInfo("tutorial"));
document.querySelector("#settings-button").addEventListener("click", () => showInfo("settings"));
document.querySelector("#about-button").addEventListener("click", () => showInfo("about"));
document.querySelector(".dialog-close").addEventListener("click", () => document.querySelector("#info-dialog").close());

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.key === "Enter") { event.preventDefault(); runTrace(); }
  else if (event.key === "F10") { event.preventDefault(); document.querySelector("#step-button").click(); }
  else if (event.key === "F5") { event.preventDefault(); document.querySelector("#continue-button").click(); }
  else if (event.ctrlKey && event.key.toLowerCase() === "r") { event.preventDefault(); replay(); }
  else if (event.ctrlKey && event.key === " ") { event.preventDefault(); refreshCompletion(); }
  else if (event.ctrlKey && event.key.toLowerCase() === "s") { event.preventDefault(); saveDocument(); }
  else if (event.ctrlKey && !event.shiftKey && event.key.toLowerCase() === "z") {
    event.preventDefault();
    if (state.undo.length) {
      state.redo.push(editor.value);
      editor.value = state.undo.pop();
      refreshEditorChrome(); markDirty(); runTrace();
    }
  } else if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "z") {
    event.preventDefault();
    if (state.redo.length) {
      state.undo.push(editor.value);
      editor.value = state.redo.pop();
      refreshEditorChrome(); markDirty(); runTrace();
    }
  }
});

async function initialize() {
  const startup = window.NEOMATH_STARTUP;
  if (!startup || !api()) return;
  state.demos = startup.demos;
  state.autosaveSeconds = Number(startup.autosaveSeconds || 15);
  const demo = state.demos[startup.demo] || state.demos["lost-root"];
  loadSource(demo.source, demo.title, startup.demo);
  const capabilities = await api().getCapabilities();
  if (capabilities?.ok) {
    document.querySelector("#core-status").lastChild.textContent = "C++ MathCore 已连接";
  }
  try {
    const settings = await api().getSettings?.();
    if (settings?.ok && settings.result?.autosaveSeconds) {
      state.autosaveSeconds = Number(settings.result.autosaveSeconds);
    }
  } catch (_) {
    /* optional */
  }
  restartAutosave();
  loadRecent();
}

window.addEventListener("neomath-ready", initialize, { once: true });
if (window.NEOMATH_STARTUP) initialize();
