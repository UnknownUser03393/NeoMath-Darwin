# 隐私与数据保护

> NeoMath 默认纯本地运行。本文档说明数据的存储位置、传输边界和保护措施。

---

## 1. 核心承诺

1. **数学核心无需联网**：C++ MathCore 在本地运行，所有解析、求解、验证不发送任何数据到网络。
2. **AI 可选且透明**：AI 功能需用户主动配置 API Key 才启用，启用时仅发送最小化结构数据。
3. **密钥不入文档**：API Key 仅存储在 `settings.json`，不进推导文档、不进日志、不进构建产物。
4. **用户完全控制**：文档数据在本地，可以随时删除、导出、迁移。

---

## 2. 数据存储位置

所有用户数据存放在 `%USERPROFILE%\.neomath\` 目录：

```text
%USERPROFILE%\.neomath\
├── settings.json           ← 用户设置（含 API Key）
├── documents\              ← 推导文档
│   ├── abc123.neomath.json
│   ├── def456.neomath.json
│   └── *.tmp               ← 临时文件（原子写中间产物）
└── logs\                   ← 应用日志（自动脱敏）
    └── neomath_2026-08.log
```

### 2.1 文档文件（`.neomath.json`）

内容：
- 推导步骤的数学表达式文本
- 文档元数据（标题、创建时间）
- 编辑状态（断点、折叠步骤、最近 Probe）
- **不包含**：API Key、密码、环境变量、网络配置

### 2.2 设置文件（`settings.json`）

内容：
- AI 配置（base_url、api_key、model、enabled）
- UI 偏好（主题、字体大小、自动保存间隔）
- **此文件包含 API Key，不应分享给他人**

### 2.3 日志文件

内容：
- 应用运行信息（启动、关闭、保存、加载）
- 错误和异常（脱敏后）
- 性能指标
- **不包含**：API Key、完整文档内容、本地路径

---

## 3. SecretFilter（日志脱敏引擎）

NeoMath 的日志系统内置 `SecretFilter`，在写入日志前自动脱敏：

### 3.1 脱敏策略

| 被检测模式 | 脱敏操作 |
|---|---|
| API Key 格式（`sk-...`、`org-...`） | 替换为 `[REDACTED_API_KEY]` |
| 完整路径（含盘符和用户目录） | 替换为 `[REDACTED_PATH]` |
| 环境变量值（含 `=`） | 替换为 `[REDACTED_ENV]` |
| Unicode/JWT token（长 Base64 串） | 替换为 `[REDACTED_TOKEN]` |

### 3.2 实现机制

```python
class SecretFilter(logging.Filter):
    def filter(self, record):
        record.msg = self._redact(record.msg)
        return True
```

脱敏发生在 `logging` 层，在 `emit` 之前，不在日志格式层。确保新增日志代码无需手动脱敏。

---

## 4. 网络传输

### 4.1 默认状态：零网络

不配置 AI 时，NeoMath **完全不产生网络流量**：
- 解析、求解、验证：C++ 本地计算
- 解释：本地确定性模板
- 保存/加载：本地文件系统
- UI：pywebview 本地 WebView

### 4.2 配置 AI 后的网络流量

仅当用户主动：
1. 在设置中填写 API Key
2. 将 `ai.enabled` 设为 `true`
3. 在应用中触发 AI 功能（如点击 AI 解释）

此时，以下**最小化结构数据**发送到配置的 API 端点：

| 发送内容 | 说明 |
|---|---|
| 结构化诊断数据 | 错误类型、解集差集、Witness 值、定义域变化 |
| 或自然语言 Intent 文本 | 用户的自然语言指令（如"分解因式"） |
| HTTP Header 中的 API Key | 仅用于认证 |

**明确不发送**：
- 完整文档内容或原始表达式
- 本地文件路径
- 文档历史或最近打开列表
- 环境变量
- 用户设置（API Key 之外的任何内容）
- 日志数据

### 4.3 网络流量可见性

- 默认端点：`https://dashscope.aliyuncs.com/compatible-mode/v1`（阿里云百炼）
- 可在设置中改为任何 OpenAI 兼容端点
- 所有请求为 HTTPS，传输层加密

---

## 5. 数据生命周期

### 5.1 创建
- 用户在 NeoMath 中创建推导文档
- 自动保存定时写入本地磁盘（原子写策略）

### 5.2 使用
- 文档被 C++ MathCore 读取进行数学分析
- 分析后的结构化结果在内存中传给 UI 渲染
- 全部在本地进程内完成

### 5.3 存储
- 文档持久化在 `%USERPROFILE%\.neomath\documents\`
- 设置持久化在 `%USERPROFILE%\.neomath\settings.json`
- 日志持久化在 `%USERPROFILE%\.neomath\logs\`

### 5.4 删除
- 用户可以随时删除 `.neomath.json` 文档文件
- 用户可以随时删除整个 `.neomath\` 目录
- 卸载 NeoMath（删除 `desktop/` 目录）时，`.neomath\` 目录**不会自动删除**，需要手动清理

### 5.5 迁移
- 文档格式为开放 JSON，可以自由迁移到其他机器
- 复制 `documents\` 目录到另一台机器即可

---

## 6. 构建产物

### 6.1 PyInstaller 打包

`python -m PyInstaller` 产生的 `dist/` 目录中：
- 不包含 `settings.json` 或用户文档
- 不包含 API Key
- 不包含测试文件或开发工具配置

### 6.2 AOT UI 构建

`npm run build:spa` 产生的静态文件中：
- 无服务端代码
- 无 API Key
- 无本地文件路径引用

---

## 7. 第三方依赖

| 依赖 | 用途 | 数据接触范围 |
|---|---|---|
| pybind11 | C++ ↔ Python 绑定 | 无网络，纯本地 |
| SymPy | 通用符号推理（dev） | 本地计算 |
| pywebview | 桌面窗口 | 仅渲染 UI，不传输数据 |
| KaTeX | 公式渲染 | 本地 JS 库，无网络请求 |
| OpenAI Client | AI 通信 | 仅在启用 AI 时发送结构化诊断 |
| Catch2 | C++ 测试 | 仅构建期 |
| pytest | Python 测试 | 仅测试期 |

所有核心依赖均为**本地库**，不进行遥测或数据收集。

---

## 8. 安全检查清单

使用前确认：

- [ ] API Key 已妥善保管，未分享给他人
- [ ] 如果不需要 AI 功能，`ai.enabled` 设为 `false`（或保持默认）
- [ ] `.neomath\settings.json` 未提交到 Git 或其他版本控制
- [ ] `.neomath\` 目录未同步到不安全的云存储
- [ ] 分享 `.neomath.json` 文档前确认不包含隐私信息

开发者确认：

- [ ] 构建产物不含 `settings.json`
- [ ] SecretFilter 已注册到日志系统
- [ ] AI 请求函数确认不含完整路径或文档内容
- [ ] 测试默认不访问真实 API（`NEOMATH_RUN_LIVE_AI_TESTS` 未设置）

---

## 9. 合规声明

NeoMath 是一个**本地优先的桌面应用**。它：

- 不收集使用数据或遥测
- 不要求用户注册账号
- 不向开发者或第三方发送数据
- 不包含任何形式的广告或跟踪器
- AI 功能**完全可选**，且用户控制发送数据的端点

如使用默认 AI 提供商（阿里云百炼），AI 请求的数据处理受该提供商隐私政策约束。
用户可以选择其他 OpenAI 兼容提供商或完全禁用 AI 功能。

---

## 10. 常见问题

**Q: NeoMath 会不会把我的数学题上传到云端？**
A: 不会。C++ MathCore 在本地完成全部数学运算。AI 请求不包含题目文本，只包含结构化诊断（如"丢根，丢失值 x=0"）。

**Q: AI 解释会泄漏我的推导步骤吗？**
A: AI 请求只发送结构化诊断元数据（错误类型 + 数学差集值），不包含原始表达式文本。详见第 4.2 节。

**Q: 我不小心把 API Key 写入文档并保存了怎么办？**
A: 如果 API Key 出现在保存的文件中，SecretFilter 不会脱敏文档文件（只会脱敏日志）。请手动编辑 `.neomath.json` 删除 Key，或从应用内重新保存覆盖。

**Q: 卸载 NeoMath 后数据还在吗？**
A: 在。`%USERPROFILE%\.neomath\` 目录不会被 `desktop/` 的删除影响。需手动清理。

**Q: 可以把文档迁移到另一台电脑吗？**
A: 可以。直接复制 `%USERPROFILE%\.neomath\documents\` 目录即可。文档格式是开放 JSON。

**Q: 日志文件包含什么？会很大吗？**
A: 日志包含应用运行信息、错误诊断和性能数据（均脱敏）。按天轮转，每个文件通常不超过 1 MB。可以随时删除。
