# AI 接入与使用说明

> NeoMath 的 AI 集成架构、配置、安全边界和回退机制。

---

## 1. AI 的定位与边界

NeoMath 的 AI 功能是**可选增强层**，不是数学真值来源。

### 1.1 AI 能做的两件事

| 任务 | 输入 | 输出 | 验证 |
|---|---|---|---|
| 改写诊断措辞 | 结构化诊断数据（错误类型、解集差、Witness） | ≤ 120 字中文学生语言 | Schema 校验 |
| 编译自然语言 Intent | 自由文本指令 | 白名单枚举值（`factor` / `solve` / `expand` / ...） | Allowlist + C++ 执行 + 证书 |

### 1.2 AI 绝对不能做的事

AI **永远不会**被要求、也不被允许：
- 计算或修改任何 `MathState`（解集、定义域、等价性结论）
- 生成 Witness 或 Probe 值
- 判定数学等价性
- 生成变换证书
- 直接修改 `MathState` 或 AST
- 访问文件系统、设置或文档数据

### 1.3 边界强制执行方式

| 机制 | 作用 |
|---|---|
| **API 白名单**（`allowed_intents`） | AI 只能输出枚举值，不能自由生成操作名 |
| **Schema 校验** | 响应严格校验 JSON Schema，不合法直接丢弃 |
| **C++ 执行 + 证书** | 即使 AI 输出合法 Intent，也是 C++ 去执行并在证书中验证 |
| **独立回退** | 任何校验失败、超时、网络断开 → 回落本地模板 |

---

## 2. 技术架构

```text
用户请求（可选 AI 解释 / 自然语言命令）
        │
        ▼
┌───────────────────────┐
│  Python Orchestrator  │
│  ai/openai_client.py  │
│  ai/schemas.py        │  ← Schema 定义
│  ai/fallback.py       │  ← 本地模板
└───────┬───────────────┘
        │ OpenAI-compatible HTTP POST
        ▼
┌───────────────────────┐
│  AI Provider          │
│  默认：DashScope Qwen  │
│  兼容任何 OpenAI API   │
└───────────────────────┘
```

### 2.1 Prompt 架构

**诊断改写 Prompt**：

```
System: 你是一个数学助教。把下面的结构化诊断改写为中文学生语言。
        字数不超过 120 字。不要添加数学事实，不要给出新结论。
        以下是已知的数学事实：[诊断数据...]

User: [当前步骤的结构化诊断：错误类型、解集差集、Witness 值、定义域变化]
```

**Intent 编译 Prompt**：

```
System: 把用户的自然语言命令编译为白名单操作。
        可用操作：factor, solve, expand, simplify, substitute, ...
        只返回操作名，不返回其他内容。

User: [用户输入的自由文本，如 "把左边分解因式"]
```

### 2.2 Schema 校验

响应必须通过 Pydantic / JSON Schema 校验：

```python
# 诊断改写响应 schema
class ExplainResponse:
    explanation: str  # ≤ 120 字符
    tone: Literal["formal", "casual", "encouraging"]

# Intent 编译响应 schema
class IntentResponse:
    intent: Literal["factor", "solve", "expand", "simplify", "substitute",
                     "add_both_sides", "subtract_both_sides",
                     "multiply_both_sides", "divide_both_sides",
                     "square_both_sides", "sqrt_both_sides"]
    params: dict | None  # 可选附加参数
```

校验失败 → 直接丢弃，回落本地模板。

---

## 3. 配置

### 3.1 设置文件

路径：`%USERPROFILE%\.neomath\settings.json`

```json
{
  "ai": {
    "provider": "openai-compatible",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "sk-your-api-key-here",
    "model": "qwen-plus",
    "timeout_ms": 5000,
    "max_retries": 1,
    "enabled": true
  }
}
```

### 3.2 字段说明

| 字段 | 必需 | 默认值 | 说明 |
|---|---|---|---|
| `provider` | 否 | `openai-compatible` | 当前固定为此值 |
| `base_url` | 否 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | OpenAI 兼容端点 |
| `api_key` | 是（如启用 AI） | 无 | API 密钥 |
| `model` | 否 | `qwen-plus` | 模型名称 |
| `timeout_ms` | 否 | `5000` | 请求超时（毫秒） |
| `max_retries` | 否 | `1` | 失败重试次数 |
| `enabled` | 否 | `true`（有 Key 时）/ `false`（无 Key 时） | 是否启用 AI |

### 3.3 环境变量方式

桌面应用"设置"面板直接编辑 `settings.json`；也可以通过环境变量配置：

```bat
set OPENAI_API_KEY=sk-your-key
set OPENAI_BASE_URL=https://your-endpoint/v1
set OPENAI_MODEL=your-model
```

环境变量**不覆盖** `settings.json` 中显式设置的值（`settings.json` 优先）。

---

## 4. 允许的白名单 Intent

AI 可以输出以下 Intent 枚举值，不允许自由文本：

```python
ALLOWED_INTENTS = {
    # 代数变换
    "factor",           # 因式分解
    "expand",           # 展开
    "simplify",         # 化简
    "solve",            # 求解
    "substitute",       # 代入

    # 等式操作
    "add_both_sides",       # 两边加
    "subtract_both_sides",  # 两边减
    "multiply_both_sides",  # 两边乘
    "divide_both_sides",    # 两边除

    # 高级操作
    "square_both_sides",    # 两边平方
    "sqrt_both_sides",      # 两边开方

    # 多项式操作
    "complete_square",      # 配方
    "difference_of_squares", # 差平方分解
}
```

任何不在白名单中的输出被静默忽略，并回退到本地建议。

---

## 5. 回退机制

### 5.1 回退触发条件

| 条件 | 行为 |
|---|---|
| `ai.enabled = false` | 所有请求使用本地模板 |
| API Key 未配置 | 同上 |
| 网络不可达 | 同上（request timeout 后回退） |
| HTTP 非 200 | 同上 |
| 响应 Schema 校验失败 | 同上 |
| 响应 intent 不在白名单 | 同上 |
| 响应包含非白名单字段 | 同上 |

### 5.2 本地模板

回退时使用确定性本地模板。模板根据诊断代码直接生成：

```python
# 示例：丢根模板
EXPLAIN_TEMPLATES = {
    DiagnosticCode.ROOT_LOST: (
        "方程求解中丢失了根 {lost_value}。"
        "原方程的解集为 {prev_solution_set}，"
        "变换后解集为 {next_solution_set}。"
        "请检查是否做了除法或开方操作，"
        "这些操作可能隐含了非零或非负的条件。"
    ),
    DiagnosticCode.ROOT_EXTRANEOUS: (
        "变换后新增了根 {extraneous_value}。"
        "代回原方程不成立，是增根。"
        "请检查是否做了平方操作，"
        "平方可能导致解集单向扩大。"
    ),
    DiagnosticCode.DOMAIN_EXPANDED: (
        "变换后定义域被扩大。"
        "值 {domain_value} 在原式中无定义，"
        "但在新式中被当作有效输入。"
        "请检查是否消去了分母或其他限制条件。"
    ),
}
```

模板是代码常量，**不依赖任何外部资源**，离线永远可用。

---

## 6. 安全与隐私

### 6.1 发送数据范围

AI 请求只发送：
- 当前步骤的**结构化诊断数据**（不含原文）
- 或用户输入的**自然语言意图文本**

AI 请求**不发送**：
- 完整文档内容
- 本地文件路径
- 文档历史
- 环境变量
- 用户设定
- API Key（Key 只在 HTTP Header 中）

### 6.2 密钥管理

- API Key **仅保存在** `%USERPROFILE%\.neomath\settings.json`
- 不进 `.neomath.json` 文档文件
- 不进日志（SecretFilter 自动脱敏）
- 不进 PyInstaller 打包产物
- 不进测试文件（测试默认无 Key）

### 6.3 测试隔离

测试**默认不访问真实 API**：

```python
# 测试中
def test_ai_explain():
    # 默认不调用真实 API，使用 mock 或本地模板
    result = client.explain(...)
    assert result.source == "local_template"

# 只有显式设置环境变量才做连通性检查
# NEOMATH_RUN_LIVE_AI_TESTS=1 python -m pytest tests/python/test_ai.py
```

---

## 7. 错误处理矩阵

| 错误场景 | 检测时机 | 处理 |
|---|---|---|
| API Key 未配置 | 请求前 | 不发送，直接用本地模板 |
| 网络超时 | HTTP 层 | 回退本地模板，日志记录 timeout |
| HTTP 4xx | HTTP 层 | 回退本地模板，日志记录状态码 |
| HTTP 5xx | HTTP 层 | 回退本地模板，日志记录状态码 |
| 响应 JSON 解析失败 | Schema 校验 | 回退本地模板，日志记录原始响应 |
| Schema 字段缺失 | Schema 校验 | 回退本地模板，日志记录缺失字段 |
| Schema 字段类型错误 | Schema 校验 | 回退本地模板 |
| Intent 不在白名单 | Allowlist 校验 | 回退本地模板，日志记录非法 intent |
| C++ 执行失败 | C++ 层 | 回退本地模板，变换不执行 |

**核心原则**：任何不可信或不合法的 AI 输出**立即丢弃**，不降级使用。

---

## 8. 扩展：添加新的 AI Provider

当前代码硬编码 OpenAI 兼容接口。如需添加其他 provider：

1. 在 `ai/openai_client.py` 中添加新 client 类，实现相同接口：
   ```python
   class AIBaseClient:
       def explain(self, diagnostic: dict) -> str: ...
       def compile_intent(self, text: str) -> IntentResponse: ...
   ```
2. 在 `settings.json` 中 `ai.provider` 注册新值
3. 在 `ai/client_factory.py` 中添加 provider 分发逻辑
4. 添加 provider 特定的 Schema 校验（如有差异）
5. 核心原则不变：**AI 只输出候选，C++ 执行并验证**

---

## 9. 快速验证

```bash
# 本地模板始终可用
python -m pytest tests/python/test_ai.py -q

# 真实 API 连通性检查（需要 Key）
NEOMATH_RUN_LIVE_AI_TESTS=1 python -m pytest tests/python/test_ai_live.py -q
```
