# NeoMath — 启动指南

## 你需要

- **Windows 10/11 x64**
- **Visual Studio 2022 C++ Build Tools**（[下载](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)，安装时勾选"使用 C++ 的桌面开发"）
- **Python 3.11+**（[下载](https://www.python.org/downloads/)）

> React UI 已预编译在 `desktop/src/neomath/ui/notebook/`，无需安装 Node.js。

## 一键启动

```bat
cd desktop
bootstrap.bat
```

脚本自动完成：创建虚拟环境 → 安装 Python 依赖 → 编译 C++ 数学内核 → 启动应用。

## 手动安装

```powershell
cd desktop
python -m venv .venv
.venv\Scripts\activate
pip install -e .          # 自动编译 C++ 扩展 neomath_core.pyd
python run.py
```

## 运行 Demo

```powershell
# headless 模式（浏览器打开）
python run.py --demo lost-root --headless

# HTTP API 服务
python -m neomath --serve
```

## 故障排查

| 症状 | 检查 |
|---|---|
| `pip install -e .` 失败 | VS C++ Build Tools 是否安装？`cmake --version` 有输出吗？ |
| `import neomath_core` 失败 | C++ 扩展编译是否成功？查看 pip install 输出 |
| 启动白屏 | UI 是否预编译？检查 `src/neomath/ui/notebook/index.html` 存在 |

## 运行测试（可选）

```powershell
.venv\Scripts\activate
python -m pytest -q          # 258 个 Python 测试
```
