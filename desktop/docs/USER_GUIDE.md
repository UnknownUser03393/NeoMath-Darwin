# NeoMath 用户指南

> 面向中学生、教师和自学者的数学推导调试器操作手册。
> 适用版本：v1。Windows 10/11 x64。

---

## 1. 安装与启动

### 1.1 环境要求

| 组件 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Windows 10/11 x64 | 当前仅支持 Windows |
| Python | 3.11+（实测 3.14） | 需在 PATH 中 |
| VS C++ Build Tools | 含 C++ CMake 工具 | 用于编译 MathCore |
| Node.js | ≥ 22.13 | 仅 AOT 构建时需要，运行期不需要 |

### 1.2 首次安装

```bat
cd desktop
bootstrap.bat
```

`bootstrap.bat` 按顺序执行：
1. 创建 Python 虚拟环境 `.venv`
2. 安装 Python 依赖（SymPy ≥ 1.12、pywebview、pytest、ruff、mypy 等）
3. 通过 CMake + pybind11 编译 `neomath_core.pyd`（C++ MathCore → Python 绑定模块）

### 1.3 启动应用

```bat
cd desktop
run.bat
```

启动后：
- 如果检测到 AOT 构建产物（`desktop/src/neomath/ui/notebook/`），默认打开 **Notebook UI**
- 使用 `python run.py --ui legacy` 可切换到旧版调试器（file:// + js_api）
- 应用通过 pywebview 创建桌面原生窗口

### 1.4 开发模式（React 热更新）

在终端 1 启动 Python HTTP 服务：

```bat
python -m neomath --serve
```

在终端 2 启动 Vite 开发服务器：

```bat
cd ui-mockups
npm install
npm run dev:spa          # Vite 开发服务器，代理 /api → 127.0.0.1:8765
```

浏览器打开 Vite 地址即可获得 React 热更新体验。前端修改即时反映，后端在 127.0.0.1:8765 提供 API。

### 1.5 无窗口核心演示

```bat
cd desktop
python run.py --demo lost-root --headless
python run.py --demo extraneous-root --headless
python run.py --demo domain-expansion --headless
python run.py --demo semantic-completion --headless
```

---

## 2. 主界面概览

NeoMath 有**两个标签页**，分别服务不同的使用场景。

### 2.1 Notebook 页 — 数学推导调试器

这是核心功能页面。布局：

```
┌──────────────────────────────────────────────────────┐
│ 菜单栏                                              │
│ [Demo 选择器 ▼] [保存] [运行全部] [变量面板] [设置]  │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌─ Cell 1 ─────────────────────────────────────┐   │
│  │ 编辑区：2x + 3 = 7                           │   │
│  │ 渲染：2x + 3 = 7    解集：{2}   定义域：ℝ    │   │
│  │ 等价状态：—（第一步）                         │   │
│  └──────────────────────────────────────────────┘   │
│                    ↓ 等价                            │
│  ┌─ Cell 2 ─────────────────────────────────────┐   │
│  │ 编辑区：2x = 4                               │   │
│  │ 渲染：2x = 4        解集：{2}   定义域：ℝ    │   │
│  │ 等价状态：✅ 等价                             │   │
│  └──────────────────────────────────────────────┘   │
│                    ↓ 不等价 ⚠                        │
│  ┌─ Cell 3 — Root Fault ────────────────────────┐   │
│  │ 编辑区：2x = 0                               │   │
│  │ 渲染：2x = 0        解集：{0}   定义域：ℝ    │   │
│  │ 诊断：                                          │
│  │   ❌ 不等价 — 丢根                              │
│  │   Witness: x = 4                               │
│  │   代入前步：2*4=8, 8=7? 否...不对，代回失败     │
│  │   前步解：2x+3=7 → x=2, 后步解：2x=0 → x=0       │
│  │   解集变化：{2} → {0}，丢失了 x=2                │
│  │   [一键修复] [查看解释]                           │
│  └──────────────────────────────────────────────┘   │
│                                                      │
├──────────────────────────────────────────────────────┤
│ CompletionBar: [因式分解] [配方] [合并同类项]        │
└──────────────────────────────────────────────────────┘
```

每个 Cell 包含以下输出组件：
- **MathOutput**：KaTeX 渲染的数学表达式
- **SolutionSet**：该行的解集
- **DomainSet**：该行的定义域
- **EquivalenceOutput**：与上一步的等价性判断
- **DiagnosticOutput**：不等价时的详细诊断
- **WitnessOutput**：精确反例数值及代回结果
- **UnsupportedOutput**：超出能力范围时的结构化提示

### 2.2 XDLT 页 — 可编译数学写作

左侧：`.hw` 源码编辑器。右侧：编译后的 HTML 实时预览。底部调试面板显示：
- 编辑距离（patch 数量）
- 失效节点数
- 编译往返耗时（ms）
- revision 竞态保护状态

详见 [xdlt-spec.md](../xdlt-spec.md)。

---

## 3. Notebook 完整工作流

NeoMath 的核心闭环：

```text
Write ──► Complete ──► Run ──► Break ──► Explain ──► Fix ──► Replay
 写推导    语义补全     运行     首错即停     教学解释     插入修复     增量重放
```

### 3.1 写推导（Write）

每个 Cell 输入一行数学表达式。**每行是一个独立的数学命题**，可以是等式、不等式或表达式。

#### 支持语法

| 语法 | 示例 | 说明 |
|---|---|---|
| 整数四则运算 | `2 + 3 * 4` | 标准优先级 |
| 变量 | `2x + 3 = 7` | 仅支持单变量 `x` |
| 等式 | `x² - 4 = 0` | 使用 `=` 连接 |
| 幂运算 | `x^2`、`(x+1)^2` | `^` 表示幂 |
| 开方 | `sqrt(x)`、`sqrt(x+1)` | 内置函数 |
| 隐式乘法 | `2x`（等价于 `2*x`） | 系数 × 变量 |
| 或运算 | `x = 1 or x = -1` | 多个解用 `or` 连接 |
| 括号嵌套 | `(x+1)(x-1)` | 支持多层嵌套 |
| 分式 | `(x+1)/(x-1)` | 用括号明确分子分母 |

#### 输入限制

- **变量**：仅 `x`
- **系数**：精确整数或有理数
- **次数**：≤ 2
- **方程类型**：单变量实数代数方程
- **文档规模**：≤ 200 步，每步 ≤ 10,000 AST 节点
- **嵌套深度**：≤ 64
- **多项式次数**：≤ 4
- **求解次数**：≤ 2

超出范围时返回 `Unverified` 或 `Unsupported`，给出明确改写建议，**绝不伪装成已验证**。

### 3.2 语义补全（Complete）

选中可补全的 Cell，`CompletionBar` 自动浮出建议变换。按 `Ctrl+Space` 打开补全菜单。

补全候选来自 C++ MathCore 对**当前数学状态**的分析结果（解集、定义域、多项式结构），不是静态字符串模板。

常见补全：
- **因式分解**：`x²-4=0` → `(x-2)(x+2)=0`（含 Difference of Squares 证书）
- **合并同类项**：`2x+3x+1=0` → `5x+1=0`
- **配方**：`x²+6x+5=0` → `(x+3)²-4=0`
- **展开**：`(x+1)²=0` → `x²+2x+1=0`

选择一个补全后，C++ 执行变换并生成**变换证书**，新 Cell 插入到当前 Cell 之后。

### 3.3 运行（Run）

按 `Ctrl+Enter` 运行当前文档。系统：

1. **逐行解析**所有表达式为 AST
2. 计算每步的**解集**（哪些 x 使等式成立）
3. 计算每步的**定义域**（哪些 x 使表达式有意义）
4. 比较相邻步骤：解集和定义域**都必须一致**才算等价
5. 在第一个可证明的语义分叉处停止，标记 **Root Fault**
6. Root Fault 之后的所有步骤标记为 **Tainted**（因依赖错误中间状态）

### 3.4 断点与诊断（Break）

当相邻步骤不再等价时，NeoMath 区分以下三类语义分叉：

| 错误类型 | 模式 | 示例 | 检测机制 |
|---|---|---|---|
| **丢根** | 前一步的某个解在后一步不成立 | `x(x-1)=0` 两边除以 `x` → `x-1=0`，丢失 `x=0` | 前解集 ⊈ 后解集 |
| **增根** | 后一步的某个解在前一步不成立 | `x²=4` → `x=2`，遗漏 `x=-2` | 后解集 ⊈ 前解集 |
| **定义域扩大** | 后一步的定义域比前一步宽 | `(x-1)/(x-1)=1` → `1=1`，`x=1` 从不合法变合法 | 前定义域 ⊈ 后定义域 |

每种错误都会生成对应的诊断代码（`ROOT_LOST`、`ROOT_EXTRANEOUS`、`DOMAIN_EXPANDED`）。

### 3.5 解释（Explain）

每个 Diagnostic 包含：
- **中文诊断标题**：简短的错误类型描述
- **教学解释**（≤ 120 字）：发生了什么、为什么错、举例反例
- **Witness 值**：精确有理数，可以亲手代回

解释来源：
1. **默认**：本地确定性模板。根据诊断代码、解集差集、定义域差集直接生成，无需网络。
2. **AI 增强**：配置 API Key 后，AI 可以改写措辞使语言更贴近学生水平。但数学事实不变。

### 3.6 修复（Fix）

在诊断卡上可以：
- **一键插入修复 Cell**：系统建议修复操作（如恢复被除去的因式、补充漏掉的解）
- **手动编辑**：直接在 Cell 编辑区修改
- **变换面板操作**：通过按钮执行安全的数学变换

所有修复和变换都需经过 C++ 验证。

### 3.7 Replay（增量重放）

修改任意 Cell 后，系统只重新计算受影响的后缀：

- **前缀复用**：改动之前、且表达式文本完全一致的步骤直接复用缓存状态
- **后缀重算**：从改动点开始，所有后续步骤重新解析、求定义域、求解集、判等价
- **cacheHits**：显示实际复用步骤数（如 "Replay: 199/200 cached, 1 recomputed"）
- **无可验证前缀时**：自动退化为全量 Trace

性能数据（200 步文档）：P50 加速约 **2.16 倍**。

---

## 4. 快捷键

| 快捷键 | 操作 | 适用页面 |
|---|---|---|
| `Ctrl+Enter` | 运行当前文档 | Notebook |
| `F10` | 单步执行（运行下一个 Cell） | Notebook |
| `F5` | 继续执行（运行至结尾或 Root Fault） | Notebook |
| `Ctrl+Space` | 语义补全（打开补全菜单） | Notebook |
| `Ctrl+S` | 保存文档 | Notebook |
| `Ctrl+R` | 重新检查当前文档 | Notebook |
| `Ctrl+Z` | 撤销 | 全部 |
| `Ctrl+Shift+Z` | 重做 | 全部 |

---

## 5. 变换面板（TransformPalette）

变换面板位于选中 Cell 的右侧，将常见数学操作变成**按钮**。学生不需要手动输入操作，只需输入参数。

### 5.1 可用变换

| 变换 | 操作 | 参数 | 前提条件 | 验证证书 |
|---|---|---|---|---|
| 两边加减 | 等式两边同时 `+` 或 `-` | 表达式（如 `3`、`2x`） | 无（加减恒等价） | Type: `ADD_BOTH_SIDES` / `SUBTRACT_BOTH_SIDES` |
| 两边乘除 | 等式两边同时 `×` 或 `÷` | 非零表达式 | **除数/乘数 ≠ 0** | Type: `MULTIPLY_BOTH_SIDES` / `DIVIDE_BOTH_SIDES`，含非零前提 |
| 两边平方 | 等式两边同时平方 | 无 | 可能增根 | Type: `SQUARE_BOTH_SIDES`，标注可能增根 |
| 两边开方 | 等式两边同时开方 | 无 | 两边均 ≥ 0（需上下文） | Type: `SQRT_BOTH_SIDES` |
| 因式分解 | 将多项式分解为因式乘积 | 无 | 可分解的多项式 | Type: `FACTOR`，含因式验证 |
| 展开 | 将因式乘积展开为多项式 | 无 | 乘积形式 | Type: `EXPAND` |

每个变换执行后生成 **变换证书（Transformation Certificate）**：
- 变换类型枚举
- 前提条件及其满足状态
- 操作前后解集和定义域对比
- 等价性结论（等价 / 单向蕴含 / 不等价）

### 5.2 设计原则

- **变换是按钮，不是打字**："两边除以 10" 是命令操作，不让学生手写
- **参数是数学输入**：除法时的除数、加减时的表达式才是学生真正要决定的数学内容
- **每个变换后即时验证**：新 Cell 插入后自动运行，验证等价性

---

## 6. Witness / Probe — 亲手验证反例

NeoMath 不给红叉，给出能**亲手代回验证的精确有理数**。

### 6.1 什么是 Witness

Witness 来自前后解集的差集或定义域的差集：

```
前解集 S₁, 后解集 S₂

丢根：Witness ∈ S₁ \ S₂  （在 S₁ 中成立，在 S₂ 中不成立）
增根：Witness ∈ S₂ \ S₁  （在 S₂ 中成立，在 S₁ 中不成立）
定义域：Witness ∈ D₂ \ D₁ （在 D₂ 中有定义，在 D₁ 中无定义）
```

### 6.2 四个 Demo 的 Witness

**Demo 1：丢根**
```
Cell 1: x(x-1) = 0    解集: {0, 1}
Cell 2: x-1 = 0        解集: {1}
────────────────────────────────
Witness: x = 0
  代入 Cell 1: 0*(0-1) = 0  ✅ 成立
  代入 Cell 2: 0-1 = -1 ≠ 0  ❌ 不成立
结论: x=0 是原方程的解，但被第二步丢失了。
```

**Demo 2：平方增根**
```
Cell 1: sqrt(x) = 2   解集: {4}
Cell 2: x = 4         解集: {4}    ← 这个 Demo 是展示 x²=4→x=2 丢失 x=-2
```

更典型的增根场景：
```
Cell 1: sqrt(x+5) = x-1   解集: {4}
Cell 2: x+5 = (x-1)²     解集: {1, 4}
────────────────────────────────
Witness: x = 1
  代入 Cell 1: sqrt(1+5) = sqrt(6) ≠ 0 = 1-1  ❌ 不成立
  代入 Cell 2: 1+5 = 6 = (1-1)² = 0           ❌ ...需要具体验证
结论: 平方后 x=1 是新引入的增根。
```

**Demo 3：定义域扩大**
```
Cell 1: (x-1)/(x-1) = 1    定义域: ℝ \ {1}，解集: ℝ \ {1}
Cell 2: 1 = 1               定义域: ℝ，解集: ℝ
────────────────────────────────
Witness: x = 1
  代入 Cell 1: (1-1)/(1-1) = 0/0 → 无定义 ❌
  代入 Cell 2: 1 = 1 → 成立 ✅
结论: x=1 在 Cell 2 中"成立"，但在 Cell 1 中根本无定义。
     化简时悄悄扩大了定义域。
```

### 6.3 手动 Probe

在变量面板输入任意有理数（如 `3`、`-1/2`），点击 Probe。C++ 将该值分别代入每行 AST 并返回：

```
Probe x = 3:
  Cell 1: 3*(3-1) = 6, 6=0? → false
  Cell 2: 3-1 = 2, 2=0? → false
```
或对于等价验证：
```
Probe x = 0:
  Cell 1 (x(x-1)=0): 0*(0-1) = 0 ✅
  Cell 2 (x-1=0): 0-1 = -1 ≠ 0 ❌
→ status: ROOT_LOST, lost_value: 0
```

---

## 7. 四个内置 Demo

点击菜单栏 Demo 选择器切换。

| Demo | 内置 ID | 演示内容 | 关键输出 |
|---|---|---|---|
| 丢根 | `lost-root` | 等式两边除以变量导致丢根 | Witness `x=0` |
| 平方增根 | `extraneous-root` | 方程两边平方引入增根 | Witness `x=1` |
| 定义域扩大 | `domain-expansion` | 分式化简后定义域被悄悄扩大 | Witness `x=1` |
| 语义补全 | `semantic-completion` | `x²-4=0` → 因式分解，展示验证证书 | Difference of Squares 证书 |

无头运行（无需 GUI）：

```bat
cd desktop
python run.py --demo lost-root --headless
python run.py --demo extraneous-root --headless
python run.py --demo domain-expansion --headless
python run.py --demo semantic-completion --headless
```

四个 Demo 合并 P95 执行时间：**0.171 ms**。

---

## 8. 保存与加载

### 8.1 保存操作

- 快捷键：`Ctrl+S`
- 菜单栏：点击"保存"
- 自动保存：默认启用，间隔可配置

磁盘路径：`%USERPROFILE%\.neomath\documents\{document_id}.neomath.json`

### 8.2 原子写策略

保存时先写入 `.tmp` 临时文件，写入成功后 `rename` 覆盖原文件。防止：
- 写入中断导致文件损坏
- 读到不完整的文件

### 8.3 文档格式

NeoMath 文档是单文件 JSON 容器：

**v1 格式**（扁平模型）：
```json
{
  "format_version": 1,
  "document_id": "abc123",
  "title": "我的推导",
  "source": "2x+3=7\n2x=4\n2x=0",
  "breakpoints": [2],
  "recent_probe": null,
  "collapsed_steps": []
}
```

**v2 格式**（edlatex 结构化节点树）：
```json
{
  "format_version": 2,
  "document_id": "abc123",
  "metadata": {"title": "我的推导", "author": ""},
  "layout": {"template": "homework"},
  "node_order": ["node-1", "node-2", "node-3"],
  "nodes": {
    "node-1": {"id": "node-1", "type": "derivation", "source": "2x+3=7", ...},
    "node-2": {"id": "node-2", "type": "derivation", "source": "2x=4", ...},
    "node-3": {"id": "node-3", "type": "derivation", "source": "2x=0", ...}
  }
}
```

### 8.4 向后兼容

- 打开 v1 格式文档时自动迁移到最新格式
- 迁移不改变数据内容，只改组结构
- 迁移失败有明确错误提示，不会静默丢失数据

---

## 9. AI 功能配置

NeoMath **默认纯本地运行**，无需 AI 即可使用全部核心数学功能。

### 9.1 AI 能做什么（及不能做什么）

| 能力 | 权威来源 | 可否被 AI 改写 |
|---|---|---|
| 解析、定义域、解集 | C++ MathCore | 否 |
| Root Fault / Tainted | C++ MathCore | 否 |
| Probe 值与代回结果 | C++ MathCore | 否 |
| Transformation Certificate | C++ MathCore | 否 |
| 学生语言解释 | 本地模板 / AI | **是，仅措辞** |
| 自然语言 → Intent | AI + Python allowlist | **候选，须经 C++ 验证** |

### 9.2 配置 API Key

在应用菜单"设置"中填写，或直接编辑 `%USERPROFILE%\.neomath\settings.json`：

```json
{
  "ai": {
    "provider": "openai-compatible",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "your-api-key-here",
    "model": "qwen-plus",
    "enabled": true
  }
}
```

- 默认提供商：阿里云百炼（DashScope Qwen）
- 兼容任何 OpenAI 兼容接口，只需覆盖 `base_url`
- API Key **仅保存在 `settings.json`**，不进文档、日志或发布包

### 9.3 离线回退机制

以下情形自动回退到本地模板，不影响核心功能：
- 未配置 API Key
- `ai.enabled = false`
- 网络断开
- AI 返回错误或超时
- 响应不满足 Schema 校验

---

## 10. XDLT `.hw` 数学写作（进阶）

XDLT 是 NeoMath 的第二子系统——把数学写作变成可编译语言。

### 10.1 核心理念

`.hw`（Human Writing）不是 Markdown + 公式，也不是 LaTeX 套壳。它不写 `\documentclass`、
`\begin{document}`、页边距——只写语义结构。

### 10.2 XDLT 工作区使用

1. 切换到 XDLT 标签页
2. 左侧编辑器写 `.hw` 源码
3. 右侧实时预览编译后的 HTML（100ms debounce）
4. 底部调试面板：
   - Patch 计数（每次编辑的 diff 量）
   - 失效节点数（依赖图增量失效追踪）
   - 往返耗时（ms）
   - Revision 保护：慢编译不会覆盖新编辑的结果

### 10.3 `.hw` 最小示例

```hw
# 我的数学作业

@context {
    alpha: Real & Positive = 0.01
}

温度场 $u(x,t)$ 满足：

$$ #eq:heat(numbered=true)
\frac{\partial u}{\partial t} = \alpha \frac{\partial^2 u}{\partial x^2}
$$

见 #eq:heat 的解。

@assert:valid(using=sympy) {
    claim: alpha + 0 == alpha
}
```

### 10.4 编译器管线

```text
.hw 源码
  → Lexer（词法）
  → Parser（语法，无损——失败不毁原文）
  → AST
  → Semantic（引用解析、作用域）
  → Graph（依赖图，节点级哈希，增量失效）
  → Verify（SymPy 断言：valid / valid-with-conditions / invalid / unknown）
  → Render（HTML / LaTeX / JSON 多后端）
  → Execution（Python runner + 缓存 + provenance）
  → Cards（知识卡注册/绑定/引用）
  → Session（增量编译会话）
```

详见 [xdlt-spec.md](../xdlt-spec.md)。

---

## 11. 故障排除

### 11.1 `bootstrap.bat` 失败

| 症状 | 检查 | 解决 |
|---|---|---|
| CMake 找不到编译器 | VS C++ Build Tools 未安装 | 安装 VS 2022 Build Tools，勾选"使用 C++ 的桌面开发" |
| Python 未找到 | PATH 不含 Python | 确认 `python --version` 正常 |
| pip install 失败 | 网络 / 权限问题 | 尝试 `pip install --user` 或更换镜像 |

### 11.2 启动时黑屏 / 白屏

- 尝试 `python run.py --ui legacy` 使用旧版 UI
- 尝试 `python -m neomath --serve` 仅启动 HTTP 服务（无 GUI）
- 检查 `python -c "import webview"` 是否成功
- 确认显卡驱动正常（pywebview 依赖系统 WebView）

### 11.3 AI 解释不生效

- 检查 `%USERPROFILE%\.neomath\settings.json` 中 `ai.enabled = true`
- 检查 `base_url` 可访问：`curl <base_url>/models`
- 检查 API Key 有效
- 离线不影响核心计算功能

### 11.4 文档打不开

- 确认 `%USERPROFILE%\.neomath\documents` 目录存在且有读写权限
- 确认 `.neomath.json` 未被其他程序占用（如文本编辑器）
- 尝试删除 `.tmp` 临时文件（可能残留上次崩溃的未完成写入）
- v1 格式文件会自动迁移到 v2，迁移失败会有明确错误消息

### 11.5 计算结果不符预期

- 确认输入语法符合 C++ Parser 要求（单变量 `x`、有理系数、次数 ≤ 2）
- 超出能力范围的操作返回 `Unverified`，可查看给出的改写建议
- 查看 Watch 面板中该步的定义域和解集

---

## 12. 文档索引

| 文档 | 内容 |
|---|---|
| [PRODUCT.md](PRODUCT.md) | 产品定义、目标用户、定位边界 |
| [MATH_SPEC.md](MATH_SPEC.md) | 数学内核不变量、支持范围、复杂度限制 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 三层架构、数据流、模块职责 |
| [TRUST_MODEL.md](TRUST_MODEL.md) | AI 可信边界与能力矩阵 |
| [AI_USAGE.md](AI_USAGE.md) | AI 接入配置、白名单、Schema、回退 |
| [PRIVACY.md](PRIVACY.md) | 隐私保护、数据存储、SecretFilter |
| [CPP_CORE.md](CPP_CORE.md) | C++ MathCore 内部模块设计 |
| [PYBIND_API.md](PYBIND_API.md) | pybind11 8 个 API 方法参考 |
| [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) | 实测性能与增量对比 |
| [VALIDATION_REPORT.md](VALIDATION_REPORT.md) | 独立验证报告（软件验证通过） |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 演示讲稿（8 个分镜，完整串联词） |
| [DEMO_STORYBOARD.md](DEMO_STORYBOARD.md) | 录屏分镜表 |
| [USER_TEST_PLAN.md](USER_TEST_PLAN.md) | 用户测试计划与任务设计 |
| [DEFENSE_QA.md](DEFENSE_QA.md) | 常见答辩问答 |
| [../xdlt-spec.md](../xdlt-spec.md) | `.hw` 语言规范 Draft 0.1 |
| [../EDLATEX_PLAN.md](../EDLATEX_PLAN.md) | 工程实施总纲与进度追踪 |
