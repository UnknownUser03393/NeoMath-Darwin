# NeoMath 性能报告

本报告由 `python tools/benchmark/run_benchmarks.py` 在当前 Windows x64 机器上实测生成，
每项预热 20 次、采样 600 次。数据不是估算值。

| 场景 | P95 | 目标 | 结果 |
|---|---:|---:|---|
| 单行解析 | 0.007 ms | < 2 ms | 通过 |
| 一次方程分析 | 0.017 ms | < 10 ms | 通过 |
| 二次方程分析 | 0.024 ms | < 10 ms | 通过 |
| 20 行 Trace | 0.307 ms | < 100 ms | 通过 |
| 4 步增量 Replay | 0.047 ms | < 150 ms | 通过 |
| 200 步全量 Trace | 2.820 ms | < 100 ms | 通过 |
| 200 步增量 Replay | 1.271 ms | < 100 ms | 通过 |

四个 Demo 合并 P95：0.171 ms。

边界估算：外部每次调用 0.0208 ms，C++ 计算及 dict 转换
0.0166 ms，估算 Python 调用边界 0.0042 ms，
比率 25.6%。该比率仅用于定位边界成本，不伪装成精确 profiler 数据。
完整原始数据见 `build/reports/benchmark.json`。

## 增量优化对比

针对 200 步文档修改最后一步的场景，全量 Trace P50 为
2.252 ms，增量 Replay P50 为
1.043 ms，复用 199 个状态，P50 加速约
2.16 倍。
该结果包含 pybind 转换完整响应的成本。
