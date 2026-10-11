# 数学规格

> NeoMath C++ MathCore 的数学不变量、支持范围与复杂度限制。
> 所有规格在 C++ 内核中强制执行，不是约定。

---

## 1. 有理数不变量（`exact/rational`）

```
Rational = (numerator: int64, denominator: int64)
```

- **分母恒正**：`denominator > 0`，符号由分子携带
- **自动约分**：构造和每次运算后除以 `gcd(numerator, denominator)`
- **零统一表示**：`0 = 0/1`
- **溢出检查**：所有加减乘除运算检测 `int64` 溢出，溢出时以结构化错误返回
- **精确相等**：`a/b == c/d` 当且仅当 `a*d == b*c`
- **精确比较**：`a/b < c/d` 当且仅当 `a*d < b*c`（考虑分母正负）

**不使用浮点数判定等价、根或解集**。浮点数仅用于单元测试中的近似比较（`Approx` matcher）。

---

## 2. 数学状态不变量（`semantics/engine`）

### 2.1 MathState

每个推导步骤的完整数学状态：

```cpp
struct MathState {
    SolutionSet solution_set;    // 使等式成立的 x 值集合
    DomainSet domain_set;         // 使表达式有意义的 x 值集合
    ExpressionAST ast;            // 当前表达式的抽象语法树
    Diagnostics diagnostics;      // 诊断信息列表
};
```

`SolutionSet` 的可能形态：
- `Empty`：空解集（如 `1 = 2`）
- `FiniteSet{rationals...}`：有限个精确有理数解
- `RealLine`：所有实数（如恒等 `x = x`）
- `Unverified`：无法确定（如含无理数根）

`DomainSet` 的可能形态：
- `AllReals`：所有实数
- `Exclude{frozenset}`：排除有限个点的实数集
- `Restricted{conditions...}`：满足特定条件的区间

### 2.2 等式状态

**方程状态同时携带定义域与解集**。消去分母不会悄悄恢复被排除点。

```
例：(x-1)(x+1)/(x-1) = 0

定义域: ℝ \ {1}  （x=1 时分母为零）
解集: {-1}       （分子为零且分母非零时）

与 x+1 = 0 比较：
定义域: ℝ        （没有分母限制）
解集: {-1}

→ 解集相同，但定义域不同 → ⚠️ 条件等价（非完全等价）
```

### 2.3 相邻步骤等价性

相邻步骤等价**当且仅当解集和定义域都保持**：

```
Step₁ ⟺ Step₂
  ⇔
SolutionSet(Step₁) == SolutionSet(Step₂) AND DomainSet(Step₁) == DomainSet(Step₂)
```

- **等价**（✅）：解集相同，定义域相同
- **条件等价**（⚠️）：解集相同，定义域在同一交集上相同（如两边乘以非零常数）
- **不等价**（❌）：解集或定义域不同，可给出差集中的 Witness

---

## 3. 错误分类与检测

### 3.1 丢根（ROOT_LOST）

```
条件：S₁ ⊈ S₂（前解集不是后解集的子集）
检测：存在 x₀ ∈ S₁ 但 x₀ ∉ S₂
Witness：x₀（来自 S₁ \ S₂ 的任意值）
```

常见场景：
- `x(x-1) = 0` 两边除以 `x` → `x-1 = 0`
- 开方时默认取正 → 遗漏负根
- 消去含解因式 → 丢失对应解

### 3.2 增根（ROOT_EXTRANEOUS）

```
条件：S₂ ⊈ S₁（后解集不是前解集的子集）
检测：存在 x₀ ∈ S₂ 但 x₀ ∉ S₁
Witness：x₀（来自 S₂ \ S₁ 的任意值）
```

常见场景：
- 方程两边平方 → 引入增根
- 方程两边乘以含 `x` 的表达式 → 可能引入增根
- 消去分母后不检查 → 增根混入

### 3.3 定义域扩大（DOMAIN_EXPANDED）

```
条件：D₁ ⊈ D₂（前定义域不是后定义域的子集）
检测：存在 x₀ ∈ D₂ 但 x₀ ∉ D₁
Witness：x₀（来自 D₂ \ D₁ 的任意值）
```

常见场景：
- 分式化简：`(x-1)/(x-1) = 1` → `1 = 1`，`x=1` 从不合法变合法
- 消去分母后忘记排除原限制点
- `sqrt` 内外移项的等价性

---

## 4. Root Fault 与 Tainted 传递

```
Step₁ → Step₂ → Step₃ → Step₄
  ✅      ❌      ⬜      ⬜
          ↑
     Root Fault    Tainted  Tainted
```

- **Root Fault**：第一个可证明分叉的步骤对（Step₂ 与 Step₁ 不等价）
- **Tainted**：Root Fault 之后的所有步骤，因其依赖了错误的中间状态
- **传递规则**：一旦标记 Root Fault，后续全部 Tainted——不测试其等价性（依赖性失效）
- **修复后**：修改 Root Fault 步骤后 Replay，Tainted 自动清除（如果修复正确）

---

## 5. Witness 选择策略

Witness 来自差集，优先选择：

1. **丢失解**：`S₁ \ S₂` 中最简单的值（绝对值最小）
2. **增根**：`S₂ \ S₁` 中最简单的值
3. **定义域差集**：`D₂ \ D₁` 中最简单的值

"最简单"定义为整数优先于分数、绝对值较小的优先。

所有 Witness 是**精确有理数**，代回时不需要浮点近似。

---

## 6. 变换证书（Transformation Certificate）

每个数学变换生成证书，包含：

| 字段 | 说明 | 示例 |
|---|---|---|
| `type` | 变换类型枚举 | `DIVIDE_BOTH_SIDES` |
| `preconditions` | 操作前提条件 | `divisor ≠ 0` |
| `preconditions_satisfied` | 前提满足状态 | `true`（x=0 除外） |
| `solution_set_before` | 变换前解集 | `{0, 1}` |
| `solution_set_after` | 变换后解集 | `{1}` |
| `solution_set_change` | 解集变化分析 | `LOST: {0}` |
| `domain_set_before` | 变换前定义域 | `ℝ` |
| `domain_set_after` | 变换后定义域 | `ℝ` |
| `equivalence` | 等价性结论 | `NOT_EQUIVALENT` |
| `witness` | 反例值（如不等价） | `0` |

---

## 7. 支持范围

### 7.1 语法支持

| 语法 | 示例 | 限制 |
|---|---|---|
| 整数四则 | `2 + 3 * 4` | — |
| 变量 | `x` | 仅 `x` |
| 等式 | `2x + 3 = 7` | `=` 两端为表达式 |
| 幂运算 | `x^2` | 指数为自然数 |
| 开方 | `sqrt(x+1)` | 参数为线性表达式 |
| 隐式乘法 | `2x`、`(x+1)(x-1)` | — |
| 或运算 | `x = 1 or x = -1` | 解集表达 |
| 括号 | `(x+1)/(x-1)` | 任意嵌套 |

### 7.2 求解能力

| 类型 | 能力 | 无力时行为 |
|---|---|---|
| 线性方程 | 精确求解 | — |
| 二次方程（有理根） | 精确求解 | 无理根→`Unverified` |
| 二次方程（无理根） | — | `Unverified`（不伪装） |
| 二次方程（负判别式） | 精确证明空解集 | — |
| 简单有理方程 | 定义域排除 + 解集 | 高次分母→`Unverified` |
| `sqrt(linear) = linear` | 平方 + 回代检验 | — |
| 多项式次数 > 2 | — | `Unsupported` |
| 三角 / 对数 / 指数 | — | `Unsupported` |

### 7.3 复杂度硬限制

| 参数 | 上限 | 超限行为 |
|---|---|---|
| 文档步骤数 | 200 | 返回结构化错误 |
| 每步 AST 节点数 | 10,000 | 同上 |
| AST 嵌套深度 | 64 | 同上 |
| 多项式次数 | 4 | 同上 |
| 方程求解次数 | 2 | 同上 |
| 单次运算时间 | 500 ms | 超时取消 |

所有超限情况返回结构化错误对象，**不弹 Python Traceback**。

---

## 8. 不支持场景的行为

当输入超出支持范围时，NeoMath 的行为：

1. **不伪装**：明确返回 `Unverified` 或 `Unsupported`
2. **给出原因**：在诊断中说明哪部分超出了 v1 范围
3. **给出建议**：提供改写建议使问题落在支持范围内（如果可能）

```json
{
  "status": "unverified",
  "reason": "quadratic_has_irrational_roots",
  "message": "x² - 2 = 0 的根是无理数 (x = ±√2)，超出 v1 精确有理数求解范围",
  "suggestion": "当前版本只支持有理数根。可尝试改写为 (x-1)(x+1)=0 等有理根方程。"
}
```

---

## 9. 数学状态演进示意

```text
Cell 1: "x(x-1) = 0"
  ├── AST: Equal(Mult(Var(x), Sub(Var(x), 1)), 0)
  ├── 定义域: ℝ
  ├── 解集: {0, 1}
  └── 多项式: x² - x

        │ 变换: ÷ x  （前提: x ≠ 0, 但 0 ∈ 解集）
        ▼

Cell 2: "x - 1 = 0"
  ├── AST: Equal(Sub(Var(x), 1), 0)
  ├── 定义域: ℝ
  ├── 解集: {1}
  └── 多项式: x - 1

        │ 检测: S₁ \ S₂ = {0} ≠ ∅
        │ → ROOT_LOST, Witness = 0
        ▼

诊断输出:
  ❌ 不等价 — 丢根
  丢失解: x = 0
  解释: 方程两边除以 x 时默认 x ≠ 0，但 0 是原方程的一个解
  反例: 代入 x=0 → Cell1: 0·(-1)=0 ✅ | Cell2: 0-1≠0 ❌
```
