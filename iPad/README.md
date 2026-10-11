# NeoMath Darwin · SwiftUI / iPadOS

打开 `NeoMathDarwin.xcodeproj`，选择 **NeoMathDarwin** scheme 和 iPad 模拟器。本工程开发基线为 iPadOS17+、Xcode16.4。

界面按GitHub Darwin原版恢复：Documents首页、默认Live Preview、Canvas/Steps、原生数学排版、关系与选择联动、双层画布工具、Overview/Evidence/Details检查器、自动检查、Witness/Probe与语义变换。设计token直接取自 `Reference/NEOMATH_DARWIN_UI_SPEC.md`。详细原版对照、实测记录与未完成差距见 [MIGRATION_PARITY.md](MIGRATION_PARITY.md)。

数学求解直接编译现有 `../desktop/cpp/` 四个源文件，Objective-C++桥接只序列化结果；UI不复制求解算法。PencilKit负责原生笔迹，`.nm`导入保留未知元数据与旧浏览器笔迹。持久化原子写入应用Documents目录。

原生数学排版使用 [SwiftMath](https://github.com/mgriebling/SwiftMath)，通过SwiftPM锁定提交 `1d2c90827e9c3908269d810d055fb03b7da5fd53`；第一次构建需要下载包与合法分发的数学字体。使用原生UIView组件，没有通过WebView包裹React。原有React、Python和C++文件均保留。

工程由 `scripts/generate_project.py` 生成，不需要XcodeGen或CocoaPods。工程依赖 `desktop/cpp`，单独拷贝iPad目录不足以构建。真机运行需在Signing & Capabilities选择自己的Team。

项目专用 CLI（可从任意目录调用）：

```sh
./iPad/scripts/neomath run                  # 生成、构建、安装并打开模拟器
./iPad/scripts/neomath verify               # 原生测试 + 模拟器 Debug + 真机 Release 无签名构建
./iPad/scripts/neomath backend              # 启动 backend/ 新版后端，使用隔离验收目录
./iPad/scripts/neomath screenshot /tmp/neomath.png
```

另外支持 `generate`、`test`、`build --device`、`run --no-build`。日志统一在 `/tmp/neomath-ipad-logs`；模拟器可通过 `NEOMATH_IPAD_SIMULATOR` 指定。安装保留现有应用数据。

Writing 工作位使用原版 XDLT 后端的编译、增量补丁、验证、执行、源码映射和保存接口。预览使用原 lockfile 锁定的 KaTeX 0.19.0；Live Preview 是原生单一文本 body，带光标候选、IME 暂停检查和依赖连接线。设置可启用后端 Notebook 检查、变换、同步及 AI 解释，解释展示实际来源。

新版完整后端来自 `origin/main` 的 `c269779`，已按根目录 `BACKEND_SETUP.md` 在 Mac 构建安装 Python/C++ 包及 SymPy。CLI 默认使用 `backend/.venv`，运行 `python -m neomath --serve --host 127.0.0.1 --port 8765`；验收工作区为 `/tmp/neomath-ipad-acceptance`。原生 App 在 Settings 启用后端检查、API URL 为 `http://127.0.0.1:8765/api`。Notebook 数学请求统一发送 `engine: "auto"` 和 `document.source`。

```sh
./iPad/scripts/neomath api health
./iPad/scripts/neomath test-backend   # Swift 原生客户端真实 HTTP 集成测试
./iPad/scripts/neomath accept-backend # CAS/Writing 真后端验收及 JSON 记录
```

`accept-backend` 的保存读回检查依赖已完成的模拟器 `CAS Writing Acceptance` 文档；详细步骤见验收记录。已实测完整无理根、参数变换、撤销重查、Unknown/输入错误/真实 CAS 超时，以及 Writing 编辑后的自动编译和保存后重开。本机原生离线 C++ 支持范围仍与连接后的新版后端不同，验收时使用连接后的 auto 路径。
