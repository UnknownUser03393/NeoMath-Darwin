# 录屏检查清单

- 使用 1440×900 主窗口，系统缩放 100% 或 125%。
- 关闭通知；不展示用户名、环境变量、API Key 或本地绝对路径。
- 录制前依次运行四个无窗口 Demo 与 `scripts\verify_all.bat`。
- 画面中实际点击 Run、Step、Replay、Probe、Completion、Explain、Save。
- AI 在线段落必须明确标注模型；网络失败时录制离线降级，不剪成假成功。
- 性能和测试数字只取当前 `build/reports`。
- 最终视频放入 `submission/` 后重新运行提交包体积检查。

