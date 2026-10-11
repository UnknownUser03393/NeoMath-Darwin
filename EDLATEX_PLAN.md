# NeoMath → edLatex 升级实施计划

> 本文件是**长期可续接的施工总纲**。任何时候中断，读这份文件就能接着干。
> 每完成一步，更新末尾《进度追踪》表。禁止营销语言，只记真实工程结果。
>
> 仓库根：`D:\Development\NeoMath`（Git Bash 下为 `/d/Development/NeoMath`）
> 主要工作目录：`desktop/`

---

## 0. 现状审计结论（Phase 0 已完成）

### 0.1 目录与主链路
```
desktop/
  cpp/                     C++ MathCore（精确有理数方程分析器）
    include/neomath/       syntax(ast) / semantics(engine) / algebra(polynomial) / exact(rational)
    bindings/              pybind11 → 模块名 neomath_core
    tests/core_tests.cpp
  src/neomath/
    documents/             ★ 文档层：model / serializer / migration / repository / autosave
    bridge.py              ★ pywebview API 门面（NeoMathBridge）
    server.py              HTTP 镜像（EXPOSED_METHODS 白名单）
    core_client.py         调 neomath_core 的 8 个方法
    ai/                    openai_client / schemas / fallback
    ui/                    ★ 当前真正在用的前端：vanilla JS + index.html + KaTeX
  tests/
    golden/  integration/  python/
  scripts/verify_all.py    ★ 验收总入口
  pyproject.toml           py311, pytest, sympy>=1.12（dev 已含）
ui-mockups/                独立 Next.js/React 原型（未集成，做视觉参考）
```

### 0.2 关键事实（决定架构的约束）
1. **现有文档模型是扁平的**：`NeoMathDocument`（`documents/model.py`）只有
   `source: str` + `title / document_id / format_version=1 / breakpoints / recent_probe / collapsed_steps / updated_at`。
   **没有节点/块结构**。推导步骤全部塞在 `source` 里，一行一个 predicate。
2. **磁盘格式**：单文件 JSON `{id}.neomath.json`，camelCase，原子写（`.tmp`→rename）。
   `migration.py` 现有 `CURRENT_FORMAT_VERSION = 1`，处理 pre-v1 的 `steps[]`→`source`。
3. **C++ Core 能力边界**：精确有理数「方程步骤」分析——解析 predicate、runTrace、
   解集丢失/增根、定义域变化、多项式因式/展开、除法/平方证书。
   **不做通用符号**：无积分、求导、通用化简、级数。API 全部围绕 `{document:{source}}` 逐行工作。
4. **前端**：真正在用的是 `src/neomath/ui/scripts/app.js`（vanilla JS，pywebview api），
   不是 ui-mockups。所有 `api().xxx()` 调用对应 `bridge.py` 方法。
5. **bridge 契约**：所有方法收 `payload: dict` 返回 `{ok, result|error}`。
   `runTrace/analyzeDocument/replay/getCompletions/executeTransformation/evaluateProbe`
   都吃 `payload["document"]`（含 `source`）。

### 0.3 核心架构判断
- edLatex 必须成为**结构化节点树**（EdDocument），但要**向后兼容扁平模型**。
- 兼容策略：新 `format_version = 2`。扁平 v1 文档能迁移成 EdDocument（source 各行 → 语义节点）；
  EdDocument 能**投影回 legacy `{source}`** 供 C++ Core 逐行分析（DerivationNode ↔ source 行）。
- **通用符号能力放 Python 侧新增的 `SymPyBackend`**，与 C++ 的方程等价验证并存、互补，不改 C++。
- 前端优先在现有 `app.js`/`ui` 上增量做（保住主链路），ui-mockups 只作视觉/交互参考。

---

## 1. 总体设计决策（一次定死，后续 Phase 遵守）

### 1.1 新增 Python 包结构（Core 侧，纯逻辑、不依赖 DOM）
```
desktop/src/neomath/edlatex/
  __init__.py
  ids.py            稳定 ID 生成（内容无关的短 id，非 uuid 全量重排）
  nodes.py          DocumentNode 及各子类（Section/Paragraph/Formula/Derivation/Assertion/Code/Context/Asset）
  document.py       EdDocument（metadata + layout + 节点树 + 作用域索引）
  metadata.py       Metadata 模型（+ 未知扩展字段保留）
  layout.py         Layout 模型（模板/纸张/边距/字体/主题）+ 内置模板注册
  serialize.py      EdDocument ⇄ JSON（往返无损，保留原始 source）
  parser_edl.py     content.edl 文本 ⇄ 节点树（保留用户原文、失败不毁原文）
  compat.py         v1 NeoMathDocument ⇄ EdDocument；EdDocument → legacy {source} 投影
  context/          Phase 3
    scope.py        ScopeTree / 声明解析 / ContextResolver / 冲突检测
  derivation/       Phase 4-5
    graph.py        DerivationGraph（依赖、拓扑、回溯 blame）
    rules.py        规则枚举与元数据
  backends/         Phase 4/6
    base.py         MathBackend 接口（capabilities/availability/execute/validate/timeout/cancel）
    sympy_backend.py
    registry.py     BackendRegistry + 能力查询
  debugger/         Phase 5
    solution_loss.py  assertions.py  breakpoints.py  conflicts.py
  render/           Phase 2
    base.py  html.py  latex.py  json.py   (pdf.py 骨架)
  suggest.py        Phase 6：DerivationSuggestion 模型 + 可验证插入流程
```

### 1.2 节点最小字段（所有语义节点）
`id, type, source, source_range, parent_id, context_id, created_at, updated_at, diagnostics[]`
Formula/Derivation 额外：`parsed_expression, symbol_references, assumptions, dependencies,
verification_status, normalized_expression`。
**内部用明确类型（dataclass），跨语言才序列化成 JSON。禁止无类型 dict 满天飞。**

### 1.3 稳定 ID 规则
- 每个节点创建时分配一次 id，之后**永不因兄弟节点增删而重排**。
- 顺序 = 节点列表顺序；身份 = id。两者分离（`EdDocument` 存 `node order[]` + `nodes{id:node}`）。

### 1.4 验证状态枚举（统一）
`unverified / valid / valid-with-conditions / warning / invalid / unknown`
UI 必须区分「数学错误 invalid」「条件不足 valid-with-conditions」「无法判断 unknown」。

### 1.5 迁移与兼容红线
- 保留 v1 读写；`migration.py` 增 v1→v2；旧 `.neomath.json` 打开不报错、不丢内容。
- `bridge.py` 现有方法签名不变；新增 edLatex 方法并列，不改旧的行为。
- C++ Core、pybind、打包、`verify_all` 不因本次改动而新增失败。

---

## 2. Phase 分解与验收

> 本轮目标：**至少交付 Phase 1，尽量推进 Phase 2**。后续 Phase 保留在本文件按序推进。

### Phase 1 — edLatex 核心文档模型 ★本轮必交付
**做什么**
- `edlatex/` 下：`ids / nodes / metadata / layout / document / serialize / parser_edl / compat`。
- 节点类型：Section / Paragraph / Formula / Derivation / Assertion / Code / Context / Asset。
- `serialize.py`：EdDocument ⇄ JSON 往返无损（含原始 source、node order、ids）。
- `migration.py`：`CURRENT_FORMAT_VERSION` 保持能读 v1；新增 v2；`compat.py` 做 v1↔v2。
- `repository.py` / `autosave.py`：支持保存/加载 EdDocument（沿用原子写；目录或单文件容器二选一——
  **首期用单文件 JSON 容器**内部分层，降低对 repository 的改动面）。
- `bridge.py` 新增：`openEdDocument / saveEdDocument / autosaveEdDocument`（旧方法不动）。
- 前端：最小接线——能加载 EdDocument、编辑一个文字节点+一个公式节点、改 metadata、切 layout、保存。
  （**投影回 `{source}` 复用现有 runTrace**，不重写计算主链路。）

**测试（新增 `tests/python/`）**
- `test_edlatex_roundtrip.py`：建文档→加节点→序列化→反序列化，ids/顺序/source 全等。
- `test_edlatex_migration.py`：旧 `.neomath.json`（v1，含多行 source）→ EdDocument → 投影回 source 一致。
- `test_edlatex_ids_stable.py`：中间插入/删除节点，其余节点 id 不变。
- `test_edlatex_metadata_layout.py`：改 metadata 不动 content；切 layout 后节点 id/顺序不变。

**验收脚本**：创建→输入文字与公式→改 Metadata→切 Layout→保存→重启→内容/ID/布局/元信息全一致。

---

### Phase 2 — 渲染与导出（尽量本轮推进）
- `render/`：HtmlRenderer、LatexRenderer、JsonRenderer（同一模型，单一内容来源）。
- 内置模板：article / homework / report / arXiv-like / NeurIPS-like（首期结构正确即可）。
- LaTeX 导出：Metadata→标题/作者/日期；模板生成导言区；节点 id 以注释保留；不支持节点给明确诊断。
- HTML 预览与导出共用模型；预览随 layout 改动即时刷新。
- 测试：同 content 切多 layout → content 不变；导出 .tex 结构正确、标题作者来自 metadata；
  `test_latex_export.py` / `test_html_render.py`。
- PDF：仅留骨架（从 LaTeX/受控 HTML 生成），工具链缺失时明确报不可用。**不伪实现时间轴 PDF。**

### Phase 3 — 上下文系统
- `context/scope.py`：声明解析（数域/正非零/区间/等式/不等式/常量/参数）、ScopeTree
  （Document→Section→Block→Derivation）、ContextResolver（继承+覆盖）、冲突检测。
- Context Badge（顶部，来自真实 Resolver，非写死）+ Inspector（来源/继承/覆盖/冲突/被谁使用）。
- 增量：改父作用域→仅受影响后代重验，不全算。
- 验收：全局 `x∈ℝ`→Section 覆盖 `x>0`→子节点读到有效上下文→加 `x=-1` 产冲突→删除后诊断消失。

### Phase 4 — 推导图 + SymPy 验证
- `derivation/graph.py` + `backends/sympy_backend.py` + `backends/registry.py`。
- 规则：simplify/expand/factor/substitute/add|subtract|multiply|divide-both-sides/
  square|sqrt-both-sides/differentiate/integrate/solve-equation。无法确认→`unknown`。
- Problems 面板；验证状态四态区分。
- 与 C++ Core 分工：方程步骤等价 → 可继续用 Core；通用符号（积分/求导/化简）→ SymPy。

### Phase 5 — 数学调试器
- Solution Loss（除变量/平方/开根/乘可能为零）、结构化 Assertion、Conflicted Conditions、
  Value Breakpoint（数值环境与符号上下文分离）、推导链回溯（基于依赖图的 blame）。
- 验收：`x(x-1)=0` 两边除以 x → 检出丢 `x=0`；`x²=4→x=2` → 检出漏 `x=-2`，
  但 `x≥0` 上下文下不误报。

### Phase 6 — Python 及扩展 Backend
- Python Kernel 适配、BackendRegistry、能力查询、异步执行、取消/超时、结果落为文档节点。
- 骨架不伪装：Lean/Coq/多模态 AI/本地推导模型/语音/Pencil/协同/云端——未配置显式 Unavailable。
- InputProvider 接口（KeyboardLatex 真实完成，其余适配层）。
- ReusableBlock 本地卡片（保存/搜索/插入生成新实例 id/检查 requiredContext）。
- 语义历史层 DocumentRevision（undo/redo、节点级 diff、保存点），Git 作为可选适配层。

---

## 3. 测试与验收命令
```bash
# 目录：desktop/
python -m pytest tests/python -q            # Python 单元（本次新增集中于此）
python -m pytest -q                          # 全量 pytest
python scripts/verify_all.py                 # 项目验收总入口（勿新增失败）
# C++（如改动 core，通常本次不改）
cmake --build build/verify && ctest --test-dir build/verify
```
每完成一个模块即跑相关测试并修复；每个 Phase 结束跑一次 `verify_all.py`。

## 4. 施工纪律（对齐 CLAUDE.md）
- 禁止伪实现：无写死演示数据、无 setTimeout 假 AI、无「暂不支持」兜底、无空接口堆砌。
- 每个功能必须有真实数据流：输入→解析→模型→状态→验证/计算→UI→持久化→重载一致。
- 不破坏 MathCore / Notebook 主链路 / 公式计算 / pywebview 通信 / 打包验收。
- Core 逻辑不依赖 DOM；核心模块可单测。
- 一条垂直链路优先于铺满接口。不一次性创建几十个未使用文件。
- UI 视觉：低装饰、细边框、IDE 密度；错误/警告色仅用于真实诊断（见 memory: ui-dark-theme-preference）。

---

## 5. 进度追踪
| Phase | 状态 | 说明 |
|---|---|---|
| 0 审计 | ✅ 完成 | 现状与架构判断见 §0 |
| 1 核心文档模型 | ✅ 完成 | edlatex 包(ids/metadata/layout/nodes/document/serialize/parser_edl/compat/migration) + repository/autosave/bridge 接线；13项单测 `tests/python/test_edlatex_model.py` 全过；验收脚本 create→edit→save→restart→reload 一致，磁盘 fmt=2。命令：`python -m pytest tests/python -q`（20 passed），`ruff/mypy` 全绿 |
| 2 渲染/导出 | ✅ 基本完成 | `edlatex/render/`(base+json+html+latex+dispatcher)；LaTeX导言区/metadata映射/节点id注释/不支持节点诊断；PDF 诚实报不可用；bridge `exportDocument`；HTTP 白名单已注册。测试 `tests/python/test_edlatex_render.py` 9项全过（含同content多layout不变、bridge端到端）。**待办**：预览面板前端接线、5 套模板精确视觉、PDF 工具链适配 |
| 3 上下文系统 | ✅ 基本完成 | `edlatex/context/`(declarations + scope)：声明解析(数域/符号/区间/等式/参数/contract)、ScopeTree(Document→Section→Derivation)、ContextResolver(继承+覆盖+badge+inspect+增量affected/recompute)。**冲突判定由 sympy 集合机制裁决**：把域/符号/区间/值翻译成 `Interval/Reals/Integers/FiniteSet/Complement`，`Intersection(...).is_empty` 判空即冲突；`is_empty=None`(无法判定)→不误报。代码只做翻译与分类，不手搓可满足性；bridge `resolveContext/inspectContext/contextDiagnostics` + HTTP白名单。测试 `tests/python/test_edlatex_context.py` 12项全过。**验收PASS**：全局x∈ℝ→section x>0→子节点读到有效上下文→加x=-1产VALUE_VIOLATES_BOUND冲突→删除后消失；域覆盖(reals→integers)不误报；增量仅重算子树。**待办**：Context Badge/Inspector 前端面板接线；sign-vs-sign 跨域语义、单位量纲。 |
| 4 推导图+SymPy | ✅ 基本完成 | `edlatex/derivation/`(rules + graph) / `edlatex/backends/`(base + sympy + registry)；sympy 负责规则验证与集合比较，ContextResolver 提供 nonzero/nonnegative/domain 条件；bridge `getMathBackends/validateStep/validateDerivations/derivationBlame` + HTTP 白名单；测试 `tests/python/test_edlatex_derivation.py` 12项全过。覆盖: valid / valid-with-conditions / unknown / invalid、求导/积分/解方程、依赖图/最早故障/回溯路径。**待办**：更完整的加减乘除条件推导、square-root 反向条件、Problems 面板前端接线 |
| 5 数学调试器 | ⬜ 未开始 | 下一阶段起点，见 §2 Phase 5 |
| 5 数学调试器 | ⬜ 未开始 | |
| 6 扩展后端 | ⬜ 未开始 | |

> 更新约定：开始一个 Phase 置 🚧，通过验收置 ✅ 并在《说明》记下测试命令与结果一行。

---

## 6. 每次续接的第一步
1. 读本文件 §5 找到当前 🚧/下一个 ⬜。
2. 读该 Phase 的「做什么/测试/验收」。
3. `cd desktop && python -m pytest tests/python -q` 确认基线绿。
4. 增量实现 → 跑该 Phase 测试 → `verify_all.py` → 更新 §5。
