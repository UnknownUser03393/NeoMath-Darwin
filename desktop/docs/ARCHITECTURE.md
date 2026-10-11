# 系统架构

> NeoMath 的三层架构、模块职责、数据流与关键设计决策。

---

## 1. 三层架构总览

```text
┌──────────────────────────────────────────────────────────────┐
│  React UI（ui-mockups/）                                     │
│  ┌─────────────────┐  ┌────────────────────────────────┐    │
│  │ Notebook 页      │  │ XDLT 页                        │    │
│  │ Cell / Witness   │  │ .hw 编辑器 → 实时 HTML 预览     │    │
│  │ TransformPalette │  │ 调试面板（patch/失效/耗时）      │    │
│  │ CompletionBar    │  │                                │    │
│  └────────┬─────────┘  └───────────────┬────────────────┘    │
│           │                            │                     │
│           │  HTTP 127.0.0.1:8765       │                     │
│           │  POST /api/* + GET /api/health                   │
│           │  AOT 静态构建，运行期无 Node                       │
├───────────┼──────────────────────────────────────────────────┤
│           ▼                                                  │
│  Python 应用层（desktop/src/neomath/）                        │
│  ┌──────────────────────────────────────────────────┐       │
│  │ bridge.py       API 门面（NeoMathCoreClient）      │       │
│  │ server.py       HTTP 镜像（EXPOSED_METHODS 白名单）│       │
│  │ app.py          pywebview 生命周期 / 多进程         │       │
│  ├──────────────────────────────────────────────────┤       │
│  │ edlatex/        文档模型（Phase 1-4 完成）         │       │
│  │   ids / nodes / metadata / layout / document      │       │
│  │   serialize / parser_edl / compat / context        │       │
│  │   derivation / backends / render / suggest         │       │
│  ├──────────────────────────────────────────────────┤       │
│  │ xdlt/           .hw 编译器（8 个子系统）           │       │
│  │   math/   lexer / parser / AST / semantic lower   │       │
│  │   parser / semantic / resolve（顶层 .hw 编译）     │       │
│  │   graph/  依赖图 / 哈希 / 增量失效                  │       │
│  │   verification/  SymPy 断言（四态）                 │       │
│  │   execution/  Python runner / 缓存 /  provenance   │       │
│  │   cards/   知识卡注册 / 绑定 / 条件                  │       │
│  │   render/  HTML / 编号 / 增量 diff/patch            │       │
│  │   session/  CompilationSession（编辑→增量编译）     │       │
│  │   sel/     SEL 结构化选择表达式                      │       │
│  │   values/  值环境 / 转换 / 解析                      │       │
│  ├──────────────────────────────────────────────────┤       │
│  │ ai/             OpenAI 兼容客户端                    │       │
│  │   openai_client / schemas / fallback               │       │
│  ├──────────────────────────────────────────────────┤       │
│  │ documents/      文档持久化                           │       │
│  │   model / serializer / migration / repository      │       │
│  │   autosave（原子写 + .tmp→rename）                   │       │
│  └──────────────┬───────────────────────────────────┘       │
│                 │ pybind11（核心计算释放 GIL）                │
├─────────────────┼───────────────────────────────────────────┤
│                 ▼                                            │
│  C++20 MathCore（desktop/cpp/）                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │ exact/rational   checked int64 Rational 精确计算   │       │
│  │ syntax/ast       不可变 variant AST + Predicate    │       │
│  │ syntax/parser    递归下降 Parser（含隐式乘法）      │       │
│  │ algebra/polynomial 稀疏多项式 / RationalFunction   │       │
│  │ semantics/engine MathState / Trace / DomainSet    │       │
│  │                   SolutionSet / Probe / Witness    │       │
│  │                   变换证书 / Replay 缓存            │       │
│  ├──────────────────────────────────────────────────┤       │
│  │ bindings/        纯胶水层（不增语义）               │       │
│  │   module.cpp     PYBIND11_MODULE                   │       │
│  │   api.cpp        8 个导出方法 + GIL + 计时 + 缓存  │       │
│  │   converters.cpp C++ → Python dict 序列化          │       │
│  │   exception_translation.cpp 异常翻译               │       │
│  │   测试：tests/core_tests.cpp（Catch2）              │       │
│  └──────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 职责纪律（硬约束）

### 2.1 C++ 层 — 数学真值的唯一来源

C++ MathCore 负责所有数学判定：
- 解析表达式为 AST
- 计算定义域和解集
- 比较相邻步骤等价性
- 生成 Witness 反例
- 执行变换并生成证书
- 管理 Replay 缓存

**C++ 不与 Python UI 层耦合**。核心库 `neomath_mathcore` 不链接 Python，CTest 可独立运行。

### 2.2 Python 层 — 编排与桥接

Python 只做：
- 桌面窗口管理（pywebview）
- HTTP 服务镜像（`server.py`）
- 文档持久化（JSON 原子写）
- 设置与日志管理
- AI 客户端接入
- SymPy 通用符号推理（与 C++ 互补）
- XDLT 编译器（Python 侧）

**`NeoMathCoreClient`（`bridge.py`）是 Python 中唯一允许 `import neomath_core` 的模块**。
所有其他模块通过 `NeoMathCoreClient` 访问 C++ 能力。

### 2.3 React 层 — 渲染与交互

JS 只做：
- 缓存编辑状态（文档文本、光标位置）
- 将 C++ 返回结果渲染为 KaTeX / HTML
- 管理 UI 状态（选中 Cell、折叠面板、Demo 切换）
- 发送 HTTP 请求到 Python 服务

**JS 不复制任何求解逻辑**。不实现 parser、不计算定义域、不比较解集。
甚至 MathCell Editor 也只是纯文本编辑——解析由 C++ 完成。

---

## 3. 通信协议

### 3.1 Python ↔ C++（pybind11）

```python
# bridge.py — 唯一允许 import neomath_core 的模块
class NeoMathCoreClient:
    def run_trace(self, document: dict) -> dict:
        # 1. 在持有 GIL 时复制输入
        # 2. 释放 GIL，调用 C++ run_trace
        # 3. 重新持有 GIL，构造返回 dict
        result = self._core.run_trace(json.dumps(document))
        return {"ok": True, "result": result}

    # 同样模式用于其他 7 个方法
```

8 个导出 API：
1. `parse_document` — 逐行解析
2. `analyze_document` — 解集/定义域/诊断
3. `run_trace` — 全量 Trace
4. `replay` — 增量重放
5. `get_completions` — 语义补全
6. `execute_transformation` — 执行变换
7. `evaluate_probe` — 代回 Probe
8. `get_capabilities` — 能力声明

### 3.2 React ↔ Python（HTTP）

```
POST /api/runTrace         { document: { source: "2x+3=7\n2x=4" } }
POST /api/replay           { document: {...}, changedStep: 1 }
POST /api/getCompletions   { document: {...}, step: 0 }
POST /api/evaluateProbe    { document: {...}, probe: "0" }
POST /api/executeTransformation { document: {...}, step: 0, intent: "factor" }
GET  /api/health           → { status: "ok", capabilities: {...} }
```

- 所有 `/api/*` 路由在 `server.py` 的 `EXPOSED_METHODS` 白名单中注册
- SPA 通过 `__NEOMATH_CORE_URL__=""` 使用同源 API（由 Python 服务器托管）
- 前端构建时 AOT 编译为静态文件，放在 `desktop/src/neomath/ui/notebook/`
- Python 服务器同时托管 `/api/*` 和静态 UI 文件

### 3.3 前端回退机制

```typescript
// lib/runtime/CoreMathRuntime.ts
// 检测后端可用性
const health = await fetch('/api/health');
if (health.ok) {
    return new CoreMathRuntime();  // 真实 C++ 后端
} else {
    return new MockMathRuntime();  // 离线 Demo 回退
}
```

离线 Demo 运行时使用内置的 mock 数据，确保四个 Demo 在没有后端时仍然可以展示 UI 交互。

---

## 4. 数据流详解

### 4.1 Notebook 运行流程

```text
React UI                        Python Server                   C++ MathCore
   │                                │                               │
   │ POST /api/runTrace             │                               │
   │ {document: {source: "..."}}     │                               │
   ├───────────────────────────────►│                               │
   │                                │ NeoMathCoreClient.run_trace() │
   │                                ├──────────────────────────────►│
   │                                │     (release GIL)              │
   │                                │     解析每行 → AST              │
   │                                │     求定义域 / 求解集            │
   │                                │     比较相邻步骤等价性            │
   │                                │     找 Root Fault               │
   │                                │     选 Witness                  │
   │                                │     (re-acquire GIL)           │
   │                                │◄───────────────────────────────│
   │                                │     ExecutionTrace JSON        │
   │◄───────────────────────────────│                                │
   │ {steps: [{solutionSet,         │                               │
   │   domainSet, diagnostics}]}    │                               │
   │                                │                               │
   │ 渲染: KaTeX 公式                │                               │
   │       EquivalenceOutput         │                               │
   │       WitnessOutput             │                               │
   │       DiagnosticOutput          │                               │
```

### 4.2 Replay（增量重放）

```text
React UI                        Python Server                   C++ MathCore
   │                                │                               │
   │ POST /api/replay               │                               │
   │ {document: {...},              │                               │
   │  changedStep: 2}               │                               │
   ├───────────────────────────────►│                               │
   │                                │ NeoMathCoreClient.replay()    │
   │                                ├──────────────────────────────►│
   │                                │     检查 Step 0, 1 不变        │
   │                                │     → 复用 Trace Cache         │
   │                                │     从 Step 2 开始重算         │
   │                                │◄───────────────────────────────│
   │                                │ {steps: [...], cacheHits: 2}  │
   │◄───────────────────────────────│                                │
   │ 只更新 Step 2+ 的渲染           │                               │
```

缓存策略：
- 线程安全的 LRU 缓存，有容量上限
- 仅当 `changedStep` 之前的步骤表达式文本**逐字符一致**时才复用
- 变更边界及之后的步骤始终重新推导
- `cacheHits` 返回实际复用数
- 无可验证前缀时自动退化为全量重算

### 4.3 XDLT 编译流程

```text
.hw 源码
  ↓
Lexer（行式 + body-mode，无损）
  ↓
Parser（块解析，失败不毁原文，畸形块降级为诊断节点）
  ↓
Semantic Analysis（引用解析、作用域、上下文继承）
  ↓
Dependency Graph（节点级哈希，增量失效追踪）
  ↓
Verification（SymPy 断言：valid / valid-with-conditions / invalid / unknown）
  ↓
Render（HTML / LaTeX / JSON 多后端）
  ↓
Session（CompilationSession：编辑 → diff → 补丁更新 → 竞态保护）
```

---

## 5. 模块依赖图

```text
C++ MathCore (neomath_mathcore)
  ├── exact/rational       (无外部依赖)
  ├── syntax/ast           → rational
  ├── syntax/parser        → ast, rational
  ├── algebra/polynomial   → rational
  └── semantics/engine     → ast, parser, polynomial, rational

C++ Bindings (neomath_core)
  └── bindings/*           → engine, ast, rational (+ pybind11)

Python
  bridge.py                → neomath_core (exclusive)
  server.py                → bridge
  edlatex/*                → bridge (via compat projection)
  xdlt/*                   → sympy, bridge (for math core ops)
  ai/*                     → openai (optional, no bridge dependency)

React (AOT → static files)
  components/*             → lib/runtime/* (HTTP bridge)
  lib/runtime/*            → fetch('/api/*')
  lib/xdlt/*               → fetch('/api/xdlt/*')
```

---

## 6. 关键设计决策

### 6.1 为什么不把数学逻辑放 Python 侧

- **真值来源单一**：C++ 是数学结论的唯一权威源，Python 无法覆盖 C++ 的判定
- **性能隔离**：精确有理数运算的溢出检查、AST 遍历、多项式因式分解——在 C++ 中更高效
- **可独立验证**：C++ 库可以在无 Python 环境下通过 CTest 独立测试
- **未来复用**：MathCore 可以嵌入其他语言运行时（WASM、C API），不绑定 Python

### 6.2 为什么有 SymPy 还要 C++

- C++ 负责**精确有理数代数**（次数 ≤ 2，100% 确定性，0 假阳性）
- SymPy 负责**通用符号推理**（求导、积分、广义化简、XDLT 断言验证）
- 两者互补不互替。方程等价判定永远走 C++；通用符号操作走 SymPy 但结果标注 `using=sympy`

### 6.3 为什么是 AOT 静态构建

- **运行期零依赖**：不需要 Node、npm、webpack-dev-server
- **pywebview 兼容**：静态文件由 Python stdlib HTTP server 直接托管
- **分发简单**：PyInstaller 打包后是一个 `.exe`，不包含 Node 运行时
- **开发期可选**：开发者仍然可以 `npm run dev:spa` 享受热更新

### 6.4 为什么 Trace 缓存是 LRU 而非无限

- 内存可预测：上限固定，不会因长文档或高频编辑而膨胀
- 线程安全：有锁保护，pybind11 的 GIL 释放/重获机制配合得当
- 足够覆盖：典型场景（200 步文档改 1 步）复用 199 个状态，LRU 容量远大于此

### 6.5 为什么 XDLT 编译器在 Python 侧

- XDLT 的语义分析、引用解析、SymPy 验证、Python 执行引擎——天然需要 Python 生态
- C++ 只做 MathCore 的精确代数运算，不做文本解析
- XDLT 数学子语言的 parser 在 Python 侧（独立于 C++ MathCore 的 parser）
