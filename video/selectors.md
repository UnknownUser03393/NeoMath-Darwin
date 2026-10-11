# NeoMath UI Selectors — 录制参考

真实 NeoMath UI (React SPA) 中可用于 Playwright 自动化的选择器。

## 布局

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| 应用外壳 | `.app-shell` | 根布局容器 |
| 工作区 | `.workbench` | 编辑区域 |
| Debug 工作区 | `.debug-workspace` | Canvas + Inspector |

## 导航

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| Activity Bar | `.activity-bar` | 左侧模式切换 |
| 侧边栏 | `.notebook-sidebar` | Demo 列表/文件浏览 |
| Tab 栏 | `.editor-tabs` | 标签页 |
| 状态栏 | `.status-bar` | 底部状态 |

## 工具栏

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| 工具栏 | `.debug-toolbar` | 顶部调试按钮 |
| Continue (F5) | `.debug-command.primary` | 运行全部 |
| Step (F10) | `.debug-command` (second) | 单步 |
| 状态文字 | `.session-state` | "已在步骤 X 暂停" |

## Notebook 步骤

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| 步骤容器 | `.step-sequence` | 所有步骤 |
| 单个步骤 | `.debug-step` / `article#cell-{id}` | |
| 选中步骤 | `.debug-step.selected` | |
| 断点步骤 | `.debug-step.breakpoint` | Root Fault (红) |
| 已验证 | `.debug-step.verified` | 等价 (绿) |
| 行号 | `.step-line-number` | "01", "02" |
| 编辑器 | `.math-editor` / `#editor-{id}` | textarea |
| 运行按钮 | `.step-run` | 单步运行 |
| 新建步骤 | `.append-step` | 底部"新建" |

## 输出

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| 数学输出 | `.math-output` | 解集 + 定义域 |
| 等价输出 | `.equivalence-output` | ✓ 等价变换 |
| 诊断输出 | `.diagnostic-output` | Root Fault 警告 |
| 诊断代码 | `.diagnostic-code` | "LOST ROOT" 等 |
| 解集对比 | `.set-diff` | 此前/此后解集 |
| Witness | `.witness-output` | 反例容器 |
| Witness 值 | `.witness-value` | x = 0 |
| Witness 校验 | `.witness-checks` | 原式/新式验证 |
| 代回按钮 | `button.witness-apply` | "一键代回 Witness" |
| Probe 结果 | `.witness-probe-summary` | 代回验证结果 |

## 补全

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| 补全栏 | `.completion-bar` | 语义补全浮层 |
| 补全项 | `.completion-chip` | 单个建议 |

## XDLT

| 元素 | CSS Selector | 说明 |
|------|-------------|------|
| 工作区 | `.xdlt-workspace` | XDLT 编辑+预览 |

## 推荐 Locator 策略

优先级（由高到低）：
1. `getByRole('button', { name: '...' })`
2. `getByText('...')`
3. `page.locator('.diagnostic-output')` (语义明确的 class)
4. `page.locator('#cell-step-1')` (ID)
5. CSS class (最后手段)

## 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| F5 | Continue (运行全部) |
| F10 | Step (单步) |
| Shift+Enter | 运行当前 Cell |
| Ctrl+Enter | 运行当前 Cell |
| Ctrl+S | 保存 |
