# pybind11 API 参考

> C++ MathCore 通过 pybind11 暴露给 Python 的 8 个粗粒度 API 方法。

---

## 1. 设计原则

- **粗粒度业务方法**：不暴露 C++ 内部对象（AST 节点、Rational 实例、指针）
- **GIL 管理**：输入复制在持有 GIL 时完成，核心计算释放 GIL，输出构造重新获取 GIL
- **无生命周期依赖**：返回纯 Python dict/list，不持有 C++ 对象引用
- **统一错误格式**：所有错误以 `{"ok": false, "error": {"code": ..., "message": ...}}` 返回
- **Metrics 追踪**：每次调用返回 `metrics` 字段，记录 C++ 侧耗时（ms）

---

## 2. API 方法

### 2.1 `parse_document`

逐行解析文档，不执行数学分析。

```python
def parse_document(source: str) -> dict:
    """
    Args:
        source: 原始文本，包含多行数学表达式
    Returns:
        {
            "ok": true,
            "result": {
                "steps": [
                    {
                        "index": 0,
                        "source": "2x + 3 = 7",
                        "ast": {...},           # 结构化 AST 描述
                        "parse_error": null     # 或 {"message": "...", "position": ...}
                    },
                    ...
                ]
            },
            "metrics": {"elapsed_ms": 0.005}
        }
    """
```

**用途**：在编辑器中进行语法检查，不等价分析。用于实时反馈输入格式问题。

---

### 2.2 `analyze_document`

逐行计算解集和定义域，但不比较相邻步骤。

```python
def analyze_document(document: dict) -> dict:
    """
    Args:
        document: {"source": "x(x-1)=0\nx-1=0"}
    Returns:
        {
            "ok": true,
            "result": {
                "steps": [
                    {
                        "index": 0,
                        "source": "x(x-1)=0",
                        "solution_set": {"type": "finite", "values": [0, 1]},
                        "domain_set": {"type": "all_reals"},
                        "polynomial": {"degree": 2, "coeffs": {...}},
                        "diagnostics": []
                    },
                    {
                        "index": 1,
                        "source": "x-1=0",
                        "solution_set": {"type": "finite", "values": [1]},
                        "domain_set": {"type": "all_reals"},
                        "polynomial": {"degree": 1, "coeffs": {...}},
                        "diagnostics": []
                    }
                ]
            },
            "metrics": {"elapsed_ms": 0.012}
        }
    """
```

**用途**：查看每步的独立状态但不触发错误标定。适合"巡视模式"。

---

### 2.3 `run_trace`

全量 Trace：解析 + 求定义域 + 求解集 + 比较相邻等价性 + 标定 Root Fault。

```python
def run_trace(document: dict) -> dict:
    """
    Args:
        document: {"source": "x(x-1)=0\nx-1=0"}
    Returns:
        {
            "ok": true,
            "result": {
                "states": [
                    {
                        "index": 0,
                        "source": "x(x-1)=0",
                        "solution_set": {"type": "finite", "values": [0, 1]},
                        "domain_set": {"type": "all_reals"}
                    },
                    {
                        "index": 1,
                        "source": "x-1=0",
                        "solution_set": {"type": "finite", "values": [1]},
                        "domain_set": {"type": "all_reals"}
                    }
                ],
                "relations": [
                    null,  // 第一步无前驱
                    {
                        "is_equivalent": false,
                        "diagnostic": "ROOT_LOST",
                        "solution_diff": {
                            "lost": [0],
                            "gained": []
                        },
                        "witness": {
                            "value": 0,
                            "previous_result": true,
                            "next_result": false
                        }
                    }
                ],
                "root_fault_index": 1,
                "tainted_indices": []
            },
            "metrics": {"elapsed_ms": 0.15}
        }
    """
```

**用途**：核心入口——运行整个推导并找出错误。

**输出字段**：
- `states`：每个步骤的完整 MathState
- `relations`：相邻步骤的关系（`null` 表示第一步）
- `root_fault_index`：第一个错误步骤的索引（`-1` 表示全部等价）
- `tainted_indices`：依赖 Root Fault 的步骤索引列表

---

### 2.4 `replay`

增量重放：缓存复用未改动的步骤前缀，仅重算受影响的后缀。

```python
def replay(document: dict, changed_step: int) -> dict:
    """
    Args:
        document: {"source": "x(x-1)=0\n(x-1)(x+1)=0\nx=1 or x=-1"}
        changed_step: 1  # 第二行被修改了
    Returns:
        {
            "ok": true,
            "result": {
                "states": [...],      # 与 run_trace 相同结构
                "relations": [...],
                "root_fault_index": -1,  # 修复后无错误
                "tainted_indices": [],
                "cache_hits": 1,       # 第一步被复用
                "recomputed_from": 1   # 从第二步起重新计算
            },
            "metrics": {"elapsed_ms": 0.03}
        }
    """
```

**用途**：用户编辑某一步后的高效重算。

**缓存策略**：
- 从 `step = 0` 逐行验证到 `changed_step - 1`
- 仅当行文本**逐字符一致**时命中缓存
- 变更边界及之后的步骤始终重新推导
- `cache_hits` 报告实际复用数量
- 无可验证前缀时自动退化为全量 `run_trace`

---

### 2.5 `get_completions`

获取当前步骤的语义补全建议。

```python
def get_completions(document: dict, step: int) -> dict:
    """
    Args:
        document: {"source": "x^2-4=0"}
        step: 0
    Returns:
        {
            "ok": true,
            "result": {
                "completions": [
                    {
                        "type": "factor",
                        "label": "因式分解",
                        "result": "(x-2)(x+2)=0",
                        "certificate_type": "DIFFERENCE_OF_SQUARES",
                        "confidence": "high"
                    },
                    {
                        "type": "complete_square",
                        "label": "配方",
                        "result": "(x)^2 = 4",
                        "certificate_type": null,
                        "confidence": "medium"
                    }
                ]
            },
            "metrics": {"elapsed_ms": 0.01}
        }
    """
```

**用途**：`Ctrl+Space` 补全菜单的数据源。

**补全类型**：`factor`、`expand`、`simplify`、`solve`、`complete_square`、`difference_of_squares`

**Confidence**：
- `high`：多步变换，C++ 已验证等价性
- `medium`：单步变换，需 UI 确认

---

### 2.6 `execute_transformation`

执行数学变换并生成验证证书。

```python
def execute_transformation(document: dict, step: int, intent: str) -> dict:
    """
    Args:
        document: {"source": "x^2-4=0"}
        step: 0
        intent: "factor"  # 白名单值
    Returns:
        {
            "ok": true,
            "result": {
                "new_step": {
                    "index": 1,
                    "source": "(x-2)(x+2)=0",
                    "solution_set": {"type": "finite", "values": [-2, 2]},
                    "domain_set": {"type": "all_reals"}
                },
                "certificate": {
                    "type": "FACTOR",
                    "preconditions": [],
                    "all_preconditions_satisfied": true,
                    "is_equivalent": true,
                    "solution_set_before": {"type": "finite", "values": [-2, 2]},
                    "solution_set_after": {"type": "finite", "values": [-2, 2]},
                    "domain_set_before": {"type": "all_reals"},
                    "domain_set_after": {"type": "all_reals"}
                }
            },
            "metrics": {"elapsed_ms": 0.04}
        }
    """
```

**用途**：变换面板和补全菜单的执行后端。

**白名单 Intent**（与 AI Intent 白名单一致）：
```python
ALLOWED_INTENTS = [
    "factor", "expand", "simplify", "solve", "substitute",
    "add_both_sides", "subtract_both_sides",
    "multiply_both_sides", "divide_both_sides",
    "square_both_sides", "sqrt_both_sides",
    "complete_square", "difference_of_squares"
]
```

---

### 2.7 `evaluate_probe`

将指定值代入每行 AST 并返回代回结果。

```python
def evaluate_probe(document: dict, probe: str) -> dict:
    """
    Args:
        document: {"source": "x(x-1)=0\nx-1=0"}
        probe: "0"  # 字符串表示的有理数
    Returns:
        {
            "ok": true,
            "result": {
                "probe_value": 0,
                "results": [
                    {
                        "index": 0,
                        "source": "x(x-1)=0",
                        "is_defined": true,
                        "is_satisfied": true,
                        "evaluated_expression": "0*(0-1)=0"
                    },
                    {
                        "index": 1,
                        "source": "x-1=0",
                        "is_defined": true,
                        "is_satisfied": false,
                        "evaluated_expression": "0-1=-1≠0"
                    }
                ]
            },
            "metrics": {"elapsed_ms": 0.02}
        }
    """
```

**用途**：手动 Probe 面板的数据源。

**返回值详解**：
- `is_defined`：probe 值在该行定义域内（如 `x=1` 在 `(x-1)/(x-1)=1` 中为 `false`）
- `is_satisfied`：probe 值使该行等式成立（如 `x=0` 在 `x-1=0` 中为 `false`）

---

### 2.8 `get_capabilities`

返回 MathCore 的能力声明。

```python
def get_capabilities() -> dict:
    """
    Returns:
        {
            "ok": true,
            "result": {
                "version": "1.0.0",
                "variable": "x",
                "domain": "real",
                "max_degree": 2,
                "coefficient_type": "rational",
                "max_document_steps": 200,
                "max_ast_nodes_per_step": 10000,
                "supported_operations": [
                    "parse", "solve_linear", "solve_quadratic_rational_roots",
                    "domain_analysis", "equivalence_check", "probe",
                    "factor", "expand", "simplify",
                    "add_subtract_both_sides", "multiply_divide_both_sides",
                    "square_both_sides"
                ],
                "unsupported_operations": [
                    "solve_higher_degree", "trigonometry",
                    "logarithms", "calculus", "multivariable"
                ]
            },
            "metrics": {"elapsed_ms": 0.0}
        }
    """
```

**用途**：前端获取能力边界，用于禁用不支持的 UI、生成适当的工具提示。

---

## 3. 错误处理

所有 8 个方法的错误返回格式：

```json
{
    "ok": false,
    "error": {
        "code": "PARSE_ERROR",
        "message": "在第 2 行第 5 列解析错误：意外的字符 ')'",
        "details": {
            "line": 2,
            "column": 5,
            "expected": ["number", "variable", "("],
            "found": ")"
        }
    },
    "metrics": {"elapsed_ms": 0.003}
}
```

**错误代码枚举**：

| 错误代码 | 触发条件 |
|---|---|
| `PARSE_ERROR` | 表达式语法错误 |
| `EXCEEDED_MAX_STEPS` | 文档超过 200 步 |
| `EXCEEDED_AST_NODES` | 单步 AST 节点超过 10,000 |
| `EXCEEDED_DEPTH` | AST 嵌套超过 64 层 |
| `EXCEEDED_POLYNOMIAL_DEGREE` | 多项式次数超过 4 |
| `EXCEEDED_SOLVE_DEGREE` | 方程求解次数超过 2 |
| `DIVISION_BY_ZERO` | 运算中除零（非方程层面的定义域） |
| `INTEGER_OVERFLOW` | Rational 运算溢出 |
| `TIMEOUT` | 单次运算超过 500 ms |
| `INTERNAL_ERROR` | C++ 内部未预期错误 |

---

## 4. Python 调用示例

```python
from neomath.bridge import NeoMathCoreClient

client = NeoMathCoreClient()

# 运行丢根 Demo
doc = {"source": "x(x-1)=0\nx-1=0"}
trace = client.run_trace(doc)

if trace["ok"]:
    rf_idx = trace["result"]["root_fault_index"]
    if rf_idx >= 0:
        # 有错误！
        rel = trace["result"]["relations"][rf_idx]
        witness = rel["witness"]["value"]
        print(f"Root Fault at step {rf_idx}: {rel['diagnostic']}")
        print(f"Witness: x = {witness}")
        print(f"  前步结果: {rel['witness']['previous_result']}")
        print(f"  后步结果: {rel['witness']['next_result']}")

# Replay：修改第二步
doc_fixed = {"source": "x(x-1)=0\nx=0 or x=1"}
replay_result = client.replay(doc_fixed, changed_step=1)
print(f"Replay cache hits: {replay_result['result']['cache_hits']}")

# 语义补全
doc_comp = {"source": "x^2-4=0"}
completions = client.get_completions(doc_comp, step=0)
for c in completions["result"]["completions"]:
    print(f"  {c['label']}: {c['result']}")

# Probe 手动验证
probe_result = client.evaluate_probe(doc, "0")
for r in probe_result["result"]["results"]:
    print(f"  Step {r['index']}: defined={r['is_defined']}, "
          f"satisfied={r['is_satisfied']}")

# 能力查询
caps = client.get_capabilities()
print(f"MathCore version: {caps['result']['version']}")
print(f"Max degree: {caps['result']['max_degree']}")
```

---

## 5. Metrics 字段

每次 API 调用返回 `metrics: {"elapsed_ms": ...}`，记录 C++ 侧纯计算耗时（不含 pybind11 序列化）。

用于：
- 性能回归检测（benchmark 工具对比历史数据）
- 前端显示（XDLT 调试面板中的编译耗时）
- 监控（日志中的耗时统计）

---

## 6. 线程安全

- 每个方法调用期间**释放 GIL**（`py::gil_scoped_release`），允许 Python 侧其他线程运行
- **Trace 缓存**使用 `std::mutex` 保护，多线程安全
- 每个方法调用是**无副作用**的（输入 → 输出，无全局状态修改）
- 注意：pybind11 不保证跨线程的 Python 对象生命周期——调用方需确保 `NeoMathCoreClient` 实例在调用期间存活
