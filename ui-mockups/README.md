# NeoMath Notebook UI（产品界面）

这是 NeoMath 的 **产品交互界面**：Jupyter 风格 Notebook + 单元格级诊断 / Witness。
正式数学真值来自仓库 [`desktop/`](../desktop/README.md) 的 C++20 MathCore。

```text
ui-mockups (React Notebook)
        │  HTTP  127.0.0.1:8765
        ▼
desktop  python -m neomath --serve
        │
        ▼
C++ MathCore (解集 / 定义域 / Probe / 证书)
```

## 本地开发

需要 Node.js `>=22.13.0`。

```bash
# 终端 1：启动真实内核网关
cd ../desktop
bootstrap.bat
python -m neomath --serve

# 终端 2：Notebook UI
cd ../ui-mockups
npm install
npm run dev
```

### 桌面 AOT 打包（推荐）

React 先编译成静态资源，Python 只负责托管 + MathCore，**运行期无 Node**：

```bash
npm run build:spa
# 产物写入 ../desktop/src/neomath/ui/notebook/
```

或从 desktop 目录：

```bat
scripts\build_notebook_ui.bat
python -m neomath --ui notebook
```

SPA 开发联调（Vite + 代理到 8765）：

```bash
# 终端 1
python -m neomath --serve
# 终端 2
npm run dev:spa
```

未启动内核时，UI 会自动落到离线演示运行时，四个内置 Demo 仍可走完主路径。

## 产品能力

| 能力 | 说明 |
|---|---|
| 四个 Demo | 丢根 / 平方增根 / 定义域扩大 / 语义补全，侧栏一键切换 |
| 首错即停 | 「全部运行」在第一处 root fault 停止并滚到诊断卡 |
| Witness | 诊断卡展示可代回的精确反例 |
| 手动 Probe | 变量面板输入有理数，检验分叉前后 |
| 修复动作 | 诊断卡「插入修复 Cell」 |
| 语义补全 | 选中方程后出现可验证的变形建议 |
| 侧栏 | Notebook / 变量 / 帮助 / 设置（无空壳入口） |

## 与 desktop 的关系

| 目录 | 角色 |
|---|---|
| `ui-mockups/` | **产品 UI**：Cell、诊断、Witness、Probe、Demo |
| `desktop/src/neomath/ui/notebook/` | AOT 构建产物（由 `build:spa` 写入） |
| `desktop/` 其余部分 | C++ 内核、pybind、打包、验收与提交 |
| `desktop/.../ui/index.html` | 旧调试器壳，仅 `--ui legacy` 逃生口 |

## 脚本

```bash
npm run dev       # 全栈 dev
npm run dev:spa   # SPA + 代理
npm run build:spa # 写入 desktop AOT 目录
npm test          # build + 节点测试
npm run lint
```
