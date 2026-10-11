# NeoMath 桌面版

NeoMath 是面向中学生的一元实数代数推导调试器。它不把 AI 当作数学真值来源：
解集、定义域、相邻步骤关系、Probe 和变换证书均由本地 C++20 MathCore 精确计算。

**产品 UI** 是上级目录的 [`ui-mockups/`](../ui-mockups/README.md) Notebook（AOT 进
`src/neomath/ui/notebook/`）。本目录提供 C++ MathCore、HTTP 网关、pywebview 打包
与验收/提交链路。旧调试器壳仅 `--ui legacy` 逃生口。

## 开发运行

需要 Windows 10/11 x64、Python 3.11+ 和 Visual Studio C++ Build Tools。

```bat
bootstrap.bat
run.bat
```

`bootstrap.bat` 创建 `.venv` 并执行 `pip install -e .[dev]`，通过
scikit-build-core、CMake 和 pybind11 生成 `neomath_core.pyd`。

无窗口核心演示：

```bat
python run.py --demo lost-root --headless
python run.py --demo extraneous-root --headless
python run.py --demo domain-expansion --headless
python run.py --demo semantic-completion --headless
```

### AOT React Notebook（默认产品 UI）

先构建一次静态产物（需要本机 Node，**运行时不需要**）：

```bat
scripts\build_notebook_ui.bat
```

之后：

```bat
run.bat
python -m neomath --ui notebook
python -m neomath --serve
```

`run` / 桌面启动在检测到 `src/neomath/ui/notebook/index.html` 时默认打开
AOT Notebook。`--serve` 同时提供 `/api/*` 与静态页面。

## 验收与打包

```bat
scripts\verify_all.bat
python tools\make_release.py
python tools\make_submission.py
```

正式运行不依赖网络。可在应用「设置」中写入 API Key，或设置环境变量
`OPENAI_API_KEY`。未配置时 Explain 使用本地结构化诊断模板；配置后仅将 C++
已验证的诊断交给 AI 改写，AI 无权改变数学状态。

更多说明见 [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) 与
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

