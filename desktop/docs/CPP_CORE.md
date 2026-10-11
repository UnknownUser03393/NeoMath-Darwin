# C++20 MathCore

> NeoMath 数学内核的内部模块设计、数据结构与 API 架构。

---

## 1. 概览

C++ MathCore 是 NeoMath 数学真值的唯一来源。它是一个独立的 C++20 静态库
（`neomath_mathcore`），不链接 Python，可通过 Catch2 独立测试。

```
neomath_mathcore (static library)
├── include/neomath/         公共头文件
│   ├── exact/rational.hpp     Rational 精确有理数
│   ├── syntax/ast.hpp         Expression / Predicate AST
│   ├── algebra/polynomial.hpp Polynomial / RationalFunction
│   └── semantics/engine.hpp   MathState / Trace / Engine
├── src/                      实现文件
│   ├── exact/rational.cpp
│   ├── syntax/parser.cpp      递归下降 Parser
│   ├── algebra/polynomial.cpp
│   └── semantics/engine.cpp
└── tests/
    └── core_tests.cpp         Catch2 12 个测试用例

neomath_core (pybind11 extension)
└── bindings/
    ├── module.cpp            PYBIND11_MODULE 注册
    ├── api.cpp               8 个导出方法
    ├── converters.cpp        C++ struct → Python dict
    └── exception_translation.cpp  C++ 异常 → Python 异常
```

---

## 2. 模块详解

### 2.1 `exact/rational` — 精确有理数

**核心类**：`Rational`

```cpp
class Rational {
    int64_t num_;  // 分子
    int64_t den_;  // 分母（恒正、约分后）

public:
    Rational(int64_t n, int64_t d);  // 自动约分，d>0 保证
    Rational(int64_t n);              // den_=1

    // 运算（全部溢出检查）
    Rational operator+(const Rational&) const;
    Rational operator-(const Rational&) const;
    Rational operator*(const Rational&) const;
    Rational operator/(const Rational&) const;  // 除零 → 异常

    // 比较
    bool operator==(const Rational&) const;
    bool operator<(const Rational&) const;

    // 工具
    int64_t numerator() const;
    int64_t denominator() const;
    bool isZero() const;   // num_ == 0
    bool isInteger() const; // den_ == 1
};

Rational pow(const Rational& base, int exp);
std::optional<Rational> exactSquareRoot(const Rational& r);
```

**不变量保证**：
- `den_ > 0` 始终
- `gcd(num_, den_) == 1` 始终
- `0` 统一为 `0/1`
- 所有运算检测 `int64_t` 溢出（`__builtin_add_overflow` 等）

### 2.2 `syntax/ast` — 抽象语法树

**不可变 AST**：`Expression` 和 `Predicate` 使用 `std::variant`：

```cpp
// 原子类型
using Atom = std::variant<int64_t, Rational, std::string>;

// 表达式节点
struct Add;
struct Sub;
struct Mul;
struct Div;
struct Pow;
struct Sqrt;
struct Var;
struct Const;

using Expression = std::variant<
    Atom,
    Add, Sub, Mul, Div, Pow, Sqrt,
    Var, Const
>;

// 谓词
struct Equal;    // lhs == rhs
struct Or;       // pred1 or pred2

using Predicate = std::variant<Equal, Or>;
```

**SourceSpan**：每个 AST 节点携带源码位置信息，用于诊断定位。

**ExecutionLimits**：
```cpp
struct ExecutionLimits {
    int max_steps = 200;
    int max_ast_nodes_per_step = 10000;
    int max_depth = 64;
    int max_polynomial_degree = 4;
    int max_solve_degree = 2;
};
```

### 2.3 `syntax/parser` — 递归下降解析器

**特性**：
- 递归下降（recursive descent），无外部依赖
- 支持**隐式乘法**：`2x` → `Mul(Const(2), Var(x))`
- 支持 `sqrt(expr)` 函数
- 运算符优先级严格遵守代数惯例
- 错误恢复：解析失败返回 `ParseError`，含位置和期望信息

**词法单元**：
```cpp
enum class TokenKind {
    Number,     // 整数或分数
    Variable,   // x
    Plus, Minus, Star, Slash,
    Caret,      // ^
    Equal,      // =
    Or,         // or
    LParen, RParen,
    Sqrt,       // sqrt
    End,
    Error,
};
```

### 2.4 `algebra/polynomial` — 多项式与有理函数

**Polynomial**：
```cpp
class Polynomial {
    // 稀疏表示：map<degree, Rational>
    std::map<int, Rational> coeffs_;  // 次数 → 系数

public:
    int degree() const;
    Rational evaluate(const Rational& x) const;
    std::vector<Rational> rationalRoots() const;  // 次数 ≤ 2
    Polynomial derivative() const;

    Polynomial operator+(const Polynomial&) const;
    Polynomial operator-(const Polynomial&) const;
    Polynomial operator*(const Polynomial&) const;
};
```

**RationalFunction**：
```cpp
class RationalFunction {
    Polynomial num_;
    Polynomial den_;

public:
    std::vector<Rational> zeros() const;   // 分子零点减分母零点
    std::vector<Rational> poles() const;   // 分母零点
    DomainSet domain() const;
};
```

**有理根求解**（次数 ≤ 2）：
- 一次：`ax + b = 0` → `x = -b/a`
- 二次（判别式 ≥ 0 且为完全平方）：有理根
- 二次（判别式 ≥ 0 但非完全平方）：`Unverified`（无理根）
- 二次（判别式 < 0）：`Empty`（精确证明空解集）

### 2.5 `semantics/engine` — 语义引擎

**核心数据结构**：

```cpp
struct MathState {
    Expression ast;
    SolutionSet solution_set;
    DomainSet domain_set;
    Polynomial polynomial;        // 化简后的标准多项式
    std::vector<Diagnostic> diagnostics;
};

struct ExecutionTrace {
    std::vector<MathState> states;
    std::vector<StepRelation> relations;
    int root_fault_index;          // -1 = 无错误
    std::vector<int> tainted_indices;
    ExecutionLimits limits;
};

struct StepRelation {
    bool is_equivalent;
    bool is_conditionally_equivalent;
    std::optional<Rational> witness;
    DiagnosticCode diagnostic;
    SolutionSetDiff solution_diff;
    DomainSetDiff domain_diff;
};

struct TransformationCertificate {
    TransformationType type;
    std::vector<Precondition> preconditions;
    bool all_preconditions_satisfied;
    MathState state_before;
    MathState state_after;
    bool is_equivalent;
};

struct ProbeResult {
    Rational value;
    bool valid_in_previous;
    bool valid_in_next;
    std::string status;  // "ok", "lost", "extraneous", "domain_issue"
};
```

**核心算法**：
1. `runTrace`：逐行解析 → 求定义域 → 求解集 → 比较相邻
2. `replay`：前缀匹配 → 缓存复用 → 从变更点重算
3. `findRootFault`：扫描相邻关系，找第一个不等价的
4. `selectWitness`：从差集中选最优有理数反例
5. `executeTransformation`：应用变换 → 生成新 MathState → 验证 → 生成证书

---

## 3. Trace 缓存

```cpp
class TraceCache {
    std::mutex mutex_;
    std::list<CacheEntry> lru_;
    std::unordered_map<std::string, CacheEntry::iterator> index_;
    size_t max_entries_;

public:
    std::optional<MathState> lookup(const std::string& source_text);
    void store(const std::string& source_text, const MathState& state);
    void clear();
    size_t size() const;
};
```

- 线程安全：`std::mutex` 保护所有操作
- LRU 淘汰：容量上限固定，最久未使用的条目被淘汰
- Key：步骤的表达式原文（文本完全一致）

---

## 4. Bindings 层（pybind11）

Bindings 层是**纯胶水层**，不添加数学语义。

**api.cpp** 中的标准 wrapper 模式：

```cpp
py::dict run_trace(const std::string& document_json) {
    py::gil_scoped_release release;  // 1. 释放 GIL
    try {
        auto result = MathEngine::runTrace(document_json, limits);
        py::gil_scoped_acquire acquire;  // 2. 重新获取 GIL
        return converters::trace_to_dict(result);  // 3. 转换为 Python dict
    } catch (const std::exception& e) {
        py::gil_scoped_acquire acquire;
        throw std::runtime_error(e.what());
    }
}
```

**converters.cpp**：C++ struct → Python dict 的递归转换。每层都做边界检查。

**exception_translation.cpp**：将 C++ 异常（解析错误、溢出、超限）转换为 Python 异常。

---

## 5. 测试

**Catch2 测试**（`cpp/tests/core_tests.cpp`）：

12 个测试用例覆盖：
- Rational 构造、四则运算、溢出检测
- Parser 基础表达式、带括号、隐式乘法、`sqrt` 函数
- Polynomial 求值、因式分解
- 四个 Demo 的完整 Trace
- Probe 反例的生成和代回

**独立运行**（不需要 Python）：

```bash
cmake --build build/verify
ctest --test-dir build/verify --output-on-failure
```

---

## 6. 设计原则

1. **不可变 AST**：`std::variant` 表达式不可变，修改即创建新节点
2. **无浮点数判定**：所有等价性、根、解集判定使用精确有理数
3. **超限检查**：每个算法有复杂度上限，超限返回结构化错误
4. **检查型算术**：所有整数运算检查溢出，Zero = `0/1` 是唯一的零表示
5. **异常安全**：所有错误通过异常传递（被 pybind11 转换为 Python 异常）
6. **无全局状态**：Engine 是纯函数，输入 document → 输出 trace
