# NeoMath — 数学动态调试环境

> **The Debugger for Mathematics｜把数学当程序运行，把错误当 Bug 调试**

NeoMath 是一个面向中学生的**单变量实数代数推导调试器**。它把每一行数学推导当作一个
**可运行的数学状态**：解析、求定义域、算解集、做变换、验证书，全部由本地 C++ 内核
**精确计算**——不依赖 AI 当数学真值来源。当相邻两步不再等价，NeoMath 不画一个红叉，
而是给出一个**能亲手代回去验证的精确反例（Witness）**：这一步丢根了、这一步增根了、
这一步悄悄扩大了定义域。

它的第二层野心，是把**数学写作本身变成一门可编译的语言**（`.hw`，见
[`xdlt-spec.md`](xdlt-spec.md)）：文档即源码，编辑器里写 `.hw`，实时编译成
语义 IR 和 HTML 预览，让「写数学」和「跑数学」在同一处发生。

---

## 1｜动机：数学推导为什么需要调试器

- 学生最容易错、也最说不清的三类错误，恰好是**语义分叉**问题：
  - **丢根**：`x(x-1)=0` 两边除以 `x`，悄悄丢掉了 `x=0`；
  - **增根**：`x²=4` 两边开平方得到 `x=2`，其实还有 `x=-2`；方程两边平方则会混入增根；
  - **定义域扩大**：化简分式后分母消失，`x=1` 在原式未定义、在新式却「成立」。
- 这类错误的难点在于：**错误不在任何单独一行里**，而在两行之间的“这一步凭什么这么变”。
- 主流工具要么只给最终答案，要么把 AI 当万能答案机——都解释不了「哪一步、为什么、值是多少」。

NeoMath 的回答：**推导是程序，分叉是 Bug，反例是日志。**

---

## 2｜核心工作流

```text
Write ──► Complete ──► Run ──► Break ──► Explain ──► Fix ──► Replay
写推导    语义补全     运行     首错即停     教学解释     插入修复     增量重放
```

| 环节 | 做什么 | 真值来源 |
|---|---|---|
| Run | 每行计算解集 + 定义域，检测相邻步骤是否等价 | C++ MathCore |
| Break | 停在第一处可证明分叉（Root Fault），后续标 Tainted | C++ MathCore |
| Explain | 把诊断翻译成学生能懂的话（≤120 字） | 本地模板 / AI（仅措辞） |
| Fix | 诊断卡一键插入修复 Cell，C++ 验证证书 | C++ MathCore |
| Replay | 修改某一行后增量重放，复用未受影响的状态 | C++ MathCore（Trace LRU） |

---

## 3｜四个内置 Demo（产品演示主线）

| Demo | 演示内容 | Probe 反例 |
|---|---|---|
| 丢根 | 等式两边除以变量，解集从 `{0,1}` 变 `{1}` | `x=0`：前一步成立，后一步不成立 |
| 平方增根 | 原式解 `{4}`，平方后候选 `{1,4}` | `x=1`：代回原式不成立，证明增根 |
| 定义域扩大 | 分式行 `x=1` 未定义，化简为 `1=1` 却“成立” | `x=1`：落在两行定义域差集中 |
| 语义补全 | `x²-4=0` 上按 `Ctrl+Space` 给出“因式分解” | C++ 验证 Difference of Squares 证书 |

> 一句话讲稿：**“NeoMath 把数学当程序运行，把错误当 Bug 调试。”**
> ——开丢根 Demo，运行，停在第二步，展示 Probe `x=0` 亲手代回。

---

## 4｜数学内核的严谨性（C++20 MathCore）

**不变量**（写进内核，不是约定）：

- 有理数分母恒正、自动约分、零统一为 `0/1`；加、减、乘、除全部**溢出检查**；
- **不使用浮点数**判定等价、根或解集；
- 方程状态同时携带定义域与解集；消去分母不会悄悄恢复被排除点；
- 相邻步骤**只在解集和定义域都保持时**才算等价；条件等价单独标注；
- 第一处可证明分叉是 Root Fault，其后依赖步骤是 Tainted；
- Probe 优先选择丢失解 / 新增解 / 定义域差集中的**精确有理数**。

**支持范围**（刻意限定，宁缺毋滥）：

- 整数、变量 `x`、`+ - * / ^ = or`、`sqrt(...)`、括号与隐式乘法；
- 次数 ≤ 2 的有理系数方程、简单有理函数、线性根式方程；
- 二次方程的无理根明确返回 **Unverified**（不伪装）；负判别式可**精确证明空解集**；
- 复杂度限制：文档 200 步、每步 10,000 AST 节点、深度 64、多项式次数 4、求解次数 2；
  超限返回结构化错误，绝不弹 Python Traceback。

**C++ Core API 面**（`NeoMathCoreClient`，8 个方法）：

| 方法 | 作用 |
|---|---|
| `parse_document` | 逐行解析表达式 |
| `analyze_document` | 整篇分析：解集 / 定义域 / 诊断 |
| `run_trace` | 全量 Trace（每步 MathState） |
| `replay(document, changedStep)` | 增量重放，返回 `cacheHits` |
| `get_completions` | 语义补全候选 |
| `execute_transformation` | 执行变换并生成证书 |
| `evaluate_probe` | 代回 Probe 反例 |
| `get_capabilities` | 能力声明 |

---

## 5｜系统架构

```text
┌─ React UI（ui-mockups/，AOT 静态构建，运行期无 Node）─────────────┐
│  Notebook 页：Cell / 解集 diff / Witness / Probe / 四个 Demo       │
│  XDLT 页：`.hw` 增量编辑器 → 编译 → HTML 预览 / 调试面板            │
└──────────────┬─────────────────────────────────────────────────────┘
               │ pywebview / HTTP 127.0.0.1:8765（/api/* 白名单）
┌──────────────▼─────────────────────────────────────────────────────┐
│ Python 应用层（desktop/src/neomath/）                               │
│  edlatex/  文档模型 · 上下文系统 · 推导图 · 渲染导出 · v1→v2 迁移    │
│  xdlt/     `.hw` 编译器全套：parser→semantic→graph→verify→render   │
│            →execution→cards→session                                 │
│  bridge.py  API 门面 · server.py HTTP 镜像（EXPOSED_METHODS 白名单）│
└──────────────┬─────────────────────────────────────────────────────┘
               │ pybind11（核心计算释放 GIL）
┌──────────────▼─────────────────────────────────────────────────────┐
│ C++20 NeoMath MathCore                                             │
│  Lexer → 递归下降 Parser → 不可变 variant AST → checked Rational →  │
│  Polynomial → 定义域 / 解集 / Trace / Probe / Transformation / 证书  │
└────────────────────────────────────────────────────────────────────┘
```

职责纪律：

- **C++ 是数学真值的唯一正式来源**；Python 只做编排、窗口、持久化、设置、日志、AI（OpenAI 兼容）接入与打包；
- `NeoMathCoreClient` 是 Python 中唯一允许导入 `neomath_core` 的模块；JS 只缓存编辑状态、
  渲染 C++ 返回结果，**不复制任何求解逻辑**；
- 通用符号推理（求导 / 积分 / 化简 / 集合裁决 / 断言验证）交给 **SymPy**，与 C++ 并存互补；
- 增量 Replay：仅当改动点之前表达式文本逐步一致才复用对应 `MathState`，`cacheHits` 返回
  实际复用的状态数，无可验证前缀时自动退化为全量重算。

---

## 6｜AI 可信边界与隐私

**AI 不碰数学真值：**

| 能力 | 权威来源 | 可否被 AI 改写 |
|---|---|---|
| 解析、定义域、解集 | C++ MathCore | 否 |
| Root Fault / Tainted | C++ MathCore | 否 |
| Probe 值与代回结果 | C++ MathCore | 否 |
| Transformation Certificate | C++ MathCore | 否 |
| 学生语言解释 | 本地模板 / AI | 是，仅措辞 |
| 自然语言 → Intent | AI + Python allowlist | 候选，须经 C++ 执行与证书验证 |

- AI 只承担两类**非真值**任务：① 把结构化诊断改写成 ≤120 字的学生语言；
  ② 把自然语言命令编译成 `factor / solve / expand` 白名单 Intent；
- 未配置 API Key / 断网 / AI 失败 / Schema 不合法时，核心功能完全不受影响；
  Explain 自动回落确定性本地模板；
- **任何 AI 候选都不能直接修改 MathState**。

**隐私**：

- 默认**纯本地运行**，数学核心无需联网；推导文档保存在
  `%USERPROFILE%\.neomath\documents`，日志同目录且经 **SecretFilter 脱敏**；
- 只有用户主动请求 AI 解释且已配置 API Key 时，当前结构化 Trace 才发送到配置的
  OpenAI 兼容接口（默认阿里云百炼）；发送内容**不包含本地路径、最近文档、环境变量**；
- 文档格式与日志**均不含 API Key**；密钥只存在 `settings.json`；
- 测试默认不访问真实 API，只有显式 `NEOMATH_RUN_LIVE_AI_TESTS=1` 才做现场连通性检查。

---

## 7｜技术选型

| 层 | 技术 | 用途 |
|---|---|---|
| 数学内核 | **C++20**、递归下降 Parser、不可变 variant AST、checked Rational/Polynomial | 精确真值，核心计算释放 GIL |
| 绑定 | **pybind11**（scikit-build-core / CMake） | 编译 `neomath_core.pyd` |
| Python | **Python 3.11+**（实测 3.14）、**SymPy ≥1.12** | 应用层、通用符号推理、差分验证 |
| 桌面壳 | **pywebview**、stdlib `http.server`、**PyInstaller** | 窗口 / HTTP 镜像 / 打包 |
| 前端 | **React 19、Next 16、Vite 8（SPA）、TypeScript 5.9、KaTeX、Framer Motion 13、Tailwind 4** | Notebook + XDLT 编辑器，AOT 后无 Node |
| 测试 | **Catch2**（C++）、**pytest**（Python）、**node:test**（UI）、ruff / mypy | 三层独立验证 |

运行环境要求：Windows 10/11 x64、Python 3.11+、VS C++ Build Tools；构建 AOT 需 Node ≥22.13（运行期不需要）。

---

## 8｜实测性能（本机基准，非估算）

`python tools/benchmark/run_benchmarks.py`，每项预热 20 次、采样 600 次：

| 场景 | P95 | 目标 | 结果 |
|---|---:|---:|---|
| 单行解析 | 0.007 ms | < 2 ms | ✅ |
| 一次方程分析 | 0.017 ms | < 10 ms | ✅ |
| 二次方程分析 | 0.024 ms | < 10 ms | ✅ |
| 20 行 Trace | 0.307 ms | < 100 ms | ✅ |
| 4 步增量 Replay | 0.047 ms | < 150 ms | ✅ |
| 200 步全量 Trace | 2.820 ms | < 100 ms | ✅ |
| 200 步增量 Replay | 1.271 ms | < 100 ms | ✅ |

四个 Demo 合并 P95：**0.171 ms**。

**增量优化对比**（200 步文档改最后一步）：全量 Trace P50 `2.252 ms` →
增量 Replay P50 `1.043 ms`，复用 199 个状态，**P50 加速约 2.16 倍**
（已含 pybind 完整响应成本）。

---

## 9｜验证与测试（独立、可复现）

实测现状（`desktop/`）：

```
python -m pytest          → 258 passed / 0 failed
python -m ruff check      → All checks passed
python -m mypy src/neomath → no issues in 118 source files
```

**按模块测试分布**（`tests/python/`，共 231 项）：

| 模块 | 测试数 | 覆盖 |
|---|---:|---|
| xdlt 数学解析 | 24 | lexer / parser / AST / lower |
| xdlt 渲染 | 25 | HTML / 编号 / 引用 / 诊断 |
| xdlt 知识卡 | 20 | 注册 / 绑定 / 条件 / 引用 |
| xdlt SEL | 19 | 结构化选择表达式 |
| xdlt 验证 | 19 | SymPy 断言，四态区分 |
| xdlt 会话 | 17 | 增量 / 失效 / 补丁 |
| xdlt 执行 | 16 | Python runner / 缓存 / 结果 |
| xdlt 图 | 16 | 依赖图 / 增量失效 / 哈希 |
| xdlt 值 | 14 | 值环境 / 转换 / 解析 |
| edlatex 模型 | 13 | 往返 / 迁移 / 稳定 ID |
| edlatex 上下文 | 12 | 作用域 / 冲突 / 增量 |
| edlatex 推导 | 12 | 规则验证 / blame |
| edlatex 渲染 | 8 | 多布局 / 导出 |
| 文档 + AI | 7 | 文档模型 / AI 门面 |
| xdlt 集成 | 2 | 端到端 |

UI 侧（`ui-mockups/`，`node --test`）：**24 项全过**——会话防竞态、补丁运行时、
侧栏模式、渲染 HTML。

软件验证报告（`docs/VALIDATION_REPORT.md`）关键项：总判定 **PASS**；C++ 单测 10 项、
差分验证 **10,000 组 / SymPy 对照 / 0 差异**、桌面 UI 交互 18 项、密钥扫描通过。

---

## 10｜XDLT：把数学写作变成一门可编译的语言

`.hw`（Human Writing）是面向人类的数学源语言（规范见 [`xdlt-spec.md`](xdlt-spec.md)，
Draft 0.1）：**语义结构优先于视觉标记、稳定 ID 优先于位置引用、可编译的块优先于模糊的散文约定**。
它不是 Markdown 加公式，也不是 LaTeX 套壳——不写 `\documentclass` / `\begin{document}` /
页边距 / 字号，只写语义。

**一个完整的 `.hw` 文档（内置 Demo 原文）：**

```hw
# 热传导示例

#context {
    alpha: Real & Positive = 0.01
    L: Real & Positive = 1
    T: Real & Positive = 300
}

温度场 $u(x,t)$ 满足热传导方程，其中扩散率 $\alpha = 0.01$，杆长 $L = 1$。

$$ #eq:heat(numbered=true)
\frac{\partial u}{\partial t}
=
\alpha \frac{\partial^2 u}{\partial x^2}
$$

见 #eq:heat 的解。把初温记为 $T$，参考 #thm:solution。

#thm:solution("Heat equation solution") {
    解具有形式：

    $$ #eq:solution(numbered=true)
    u(x,t)
    =
    \sin\left(\frac{\pi x}{L}\right)
    e^{-\alpha (\frac{\pi}{L})^2 t}
    $$
}

#proof(#thm:solution) {
    使用分离变量法求解。
}

#assert:valid(using=sympy) {
    claim alpha + 0 == alpha
}

#assert:unknown(using=sympy) {
    claim f(x) == 1
}

#exec:data(python, inputs=[alpha, L]) {
from xdlt_runtime import output
output.text("alpha = " + str(alpha))
output.json({"alpha": alpha, "L": L})
output.table([["alpha", alpha], ["L", L]])
output.image(b"\x89PNG\r\n\x1a\n", name="plot.png")
}

#fig:heat-plot(source=#exec:data[3]) {
    温度场示意图。
}

#use-card:demo(#card:demo-card, mode=reference) {
    bind alpha = alpha
}
```

这一页就同时表达：上下文声明、行内/行间数学、带编号公式、定理与证明、可验证断言
（`valid` 与 `unknown` 明确区分）、可执行代码块（多类型输出）、图引用、知识卡引用。

**配套编译器（`desktop/src/neomath/xdlt/`，已端到端接线）：**

- **无损解析器**：行式 + body-mode，失败不毁原文，畸形块降级为带诊断的节点；
- **数学子语言**：lexer → parser → AST → 语义 lower；
- **语义层**：引用解析、上下文作用域、重复 ID 诊断、断言验证状态
  （`valid / valid-with-conditions / invalid / unknown`，**`unknown` 绝不渲染成 `invalid`**）；
- **依赖图 + 增量失效**：节点级哈希，编辑后仅重算受影响子树；
- **执行引擎**：Python runner + 结果缓存，`@result` 语义引用，provenance + hash；
- **知识卡**：`.card.json` 注册 / 绑定 / 条件检查 / 引用，插入即产生依赖边；
- **增量会话**：`CompilationSession`，编辑 → 补丁级 diff（HTML 增量 patch）；
- **SEL 子语言**：结构化选择 / 取值表达式，服务断言与值环境。

**XDLT 工作区（UI）**：`.hw` 源码编辑器 → 编译 → HTML 预览的增量闭环——
100ms debounce、**revision 竞态保护**（慢的旧编译绝不覆盖新结果）、首次全量挂载 +
后续补丁级更新，附调试面板（patch 数 / 失效节点 / 往返耗时）。

---

## 11｜产品 UI

React（Next + Vite SPA、Framer Motion、KaTeX），AOT 编译成静态资源由 Python 托管，
**运行期无 Node**。主界面两个页签：

**Notebook 页**：每个数学 Cell 运行后展示 Math / Equivalence / Diagnostic / Unsupported；
Diagnostic 含解集 diff 与 Witness；全部运行停首错；变量面板支持手动 Probe。特色交互：

- **结构化变换面板（TransformPalette）**：变换是按钮不是打字——
  “两边除以 10” 这类操作绝不让学生手打，参数才是数学输入；
- **语义补全条（CompletionBar）**：选中可补全的数学 Cell 时浮出建议
  （如 `x²-4=0` → 因式分解），来自当前数学状态而非字符串模板；
- 快捷键：`Ctrl+Enter` 运行、`F10/F5` 单步/继续、`Ctrl+R` 重查、`Ctrl+Space` 语义补全、
  `Ctrl+S` 保存、`Ctrl+Z / Ctrl+Shift+Z` 撤销/重做。

**XDLT 页**：见 §10。未启动内核时自动落到离线演示运行时，Demo 主路径仍可走完。

界面截图：`desktop/docs/assets/neomath-ui.png`。

---

## 12｜目标用户与使用场景

| 角色 | 场景 | 价值 |
|---|---|---|
| 中学生 | 课后自查一元代数推导 | 每一步都可验证，错误能“亲眼看到”反例 |
| 数学教师 | 课堂演示常见错误 | 精确讲解丢根 / 增根 / 定义域，不是空口说“你错了” |
| 竞赛 / 自学 | 训练严谨推导习惯 | 条件等价、证书、Unverified 边界，培养数学严谨性 |
| 开发者 / 研究者 | 学习可编译数学写作 | `.hw` 语言 + 增量编译器 + 知识卡 + 可执行块 |

**定位边界**：不做拍照搜题、不做通用 CAS、不生成标准答案、不做完整 LaTeX 编辑、
不做形式化证明。超出能力范围时**明确返回 Unverified 或 Unsupported 并给改写建议**，
绝不把启发式结果包装成 Verified。

---

## 13｜创新点（一句话可答辩）

1. **推导即程序**：把「丢根 / 增根 / 定义域」定义为可证明的语义分叉，而非笼统的“错误”；
2. **精确反例代替红叉**：Witness 来自解集差集的精确有理数，能亲手代回验证，不随机抽样；
3. **AI 不碰数学真值**：AI 只改措辞与生成候选，一切数学结论由 C++ 本地精确计算并出证书；
4. **数学写作可编译**：`.hw` 语言 + 增量编译器 + 补丁级预览，写数学与跑数学合二为一；
5. **增量重放**：改一处只重算受影响子树，200 步文档 P50 加速约 2.16 倍。

**答辩快答**：为什么不用纯 Python——数学真值集中在独立 C++20 MathCore；
AI 会不会算错——AI 不产生解集 / 定义域 / Verified 状态，候选必须经 C++ 执行并通过证书；
Probe 为什么可信——来自前后解集 / 定义域差集并分别代回两棵 AST；
为什么不支持所有数学——首版刻意限定单变量实数代数，不能证明就返回 Unverified。

---

## 14｜当前进度与路线图

| 模块 | 状态 | 备注 |
|---|---|---|
| C++ MathCore | ✅ 可用 | pybind11 已编译打包 |
| edlatex 文档模型 | ✅ Phase 1 | 往返 / 迁移 / 稳定 ID |
| 渲染导出 | ✅ Phase 2 | 同模型多布局，LaTeX / HTML / JSON |
| 上下文系统 | ✅ Phase 3 | SymPy 集合裁决冲突，增量重算子树 |
| 推导图 + SymPy | ✅ Phase 4 | 规则验证 / 依赖图 / blame |
| XDLT 编译器 | ✅ 主要完成 | parser→semantic→graph→verify→render→exec→cards→session |
| XDLT 增量 UI | ✅ 已接线 | workspace + 补丁运行时 + 调试面板 |

**下一步（路线图）**：
- Phase 5 数学调试器：结构化断言、条件冲突、值断点、基于依赖图的回溯 blame；
- Phase 6 扩展后端：Python 内核适配、能力查询、异步执行、Lean/Coq/多模态 AI 显式 Unavailable、
  ReusableBlock 本地卡片、语义历史（undo/redo）；
- XDLT：`.hw` 词法/语义分析器公开 API、LSP、PDF 后端、更多内置模板与编辑器体验打磨。

---

## 15｜快速开始（Windows 10/11 x64）

```bat
cd desktop
bootstrap.bat      :: 创建 .venv + 编译 neomath_core.pyd
run.bat            :: 启动应用（检测到 AOT 产物时默认打开 Notebook）
```

开发联调（React 热更新，可选）：

```bat
cd ui-mockups
npm install
npm run build:spa  :: 产物写入 desktop/src/neomath/ui/notebook/（AOT）
npm run dev:spa    :: 或 Vite 联调
```

完整验收：

```bat
cd desktop
scripts\verify_all.bat
```

无窗口核心演示：

```bat
cd desktop
python run.py --demo lost-root --headless
python run.py --demo extraneous-root --headless
python run.py --demo domain-expansion --headless
python run.py --demo semantic-completion --headless
```

---

## 16｜文档索引

| 文档 | 内容 |
|---|---|
| [`xdlt-spec.md`](xdlt-spec.md) | `.hw` 语言规范 Draft 0.1（词法 / 块 / 引用 / 断言 / 执行 / 知识卡 / 完整示例） |
| [`EDLATEX_PLAN.md`](EDLATEX_PLAN.md) | 施工总纲与进度追踪（Phase 0–4 ✅，5–6 待推进） |
| `desktop/docs/PRODUCT.md` | 产品定义与定位 |
| `desktop/docs/MATH_SPEC.md` | 数学内核不变量与支持范围 |
| `desktop/docs/ARCHITECTURE.md` | 系统架构与职责纪律 |
| `desktop/docs/PERFORMANCE_REPORT.md` | 实测性能与增量对比 |
| `desktop/docs/VALIDATION_REPORT.md` | 独立验证报告 |
| `desktop/docs/TRUST_MODEL.md` | AI 可信边界 |
| `desktop/docs/AI_USAGE.md` | AI 接入与白名单 |
| `desktop/docs/PRIVACY.md` | 隐私与数据 |
| `desktop/docs/USER_GUIDE.md` | 用户指南与快捷键 |
| `desktop/docs/DEMO_SCRIPT.md` | 演示讲稿（8 个分镜） |
| `desktop/docs/DEFENSE_QA.md` | 答辩问答 |
