from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import neomath_core

ROOT = Path(__file__).resolve().parents[2]

DEMOS = {
    "lost_root": "x(x - 1) = 0\nx - 1 = 0\nx = 1",
    "extraneous_root": ("sqrt(x) = x - 2\nx = (x - 2)^2\nx^2 - 5x + 4 = 0\nx = 1 or x = 4"),
    "domain_expansion": "(x - 1) / (x - 1) = 1\n1 = 1",
    "completion": "x^2 - 4 = 0",
}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * fraction))
    return ordered[index]


def measure(operation: Callable[[], Any], iterations: int = 600) -> dict[str, float]:
    for _ in range(20):
        operation()
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        operation()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "iterations": float(iterations),
        "meanMs": statistics.fmean(samples),
        "p50Ms": percentile(samples, 0.50),
        "p95Ms": percentile(samples, 0.95),
        "maxMs": max(samples),
    }


def main() -> int:
    twenty_lines = "\n".join(
        f"{coefficient}x + {coefficient} = {coefficient * 2}" for coefficient in range(1, 21)
    )
    replay_prefix = [
        f"{coefficient}x + {coefficient} = {coefficient * 2}"
        for coefficient in range(1, 200)
    ]
    replay_before = "\n".join([*replay_prefix, "x = 1"])
    replay_after = "\n".join([*replay_prefix, "x = 2"])
    neomath_core.run_trace({"source": replay_before})
    scenarios: dict[str, Callable[[], Any]] = {
        "parseSingleLine": lambda: neomath_core.parse_document("2x + 3 = 7"),
        "parse20Lines": lambda: neomath_core.parse_document(twenty_lines),
        "analyzeLinear": lambda: neomath_core.run_trace({"source": "2x + 3 = 7"}),
        "analyzeQuadratic": lambda: neomath_core.run_trace({"source": "x^2 - 5x + 4 = 0"}),
        "trace20Lines": lambda: neomath_core.run_trace({"source": twenty_lines}),
        "fourDemos": lambda: [
            neomath_core.run_trace({"source": source}) for source in DEMOS.values()
        ],
        "replay": lambda: neomath_core.replay({"source": DEMOS["extraneous_root"]}, 2),
        "fullTrace200": lambda: neomath_core.run_trace({"source": replay_after}),
        "incrementalReplay200": lambda: neomath_core.replay({"source": replay_after}, 199),
        "pybindCall": lambda: neomath_core.get_capabilities(),
    }
    results = {name: measure(operation) for name, operation in scenarios.items()}

    internal_samples: list[float] = []
    started = time.perf_counter_ns()
    for _ in range(1_000):
        sample = neomath_core.run_trace({"source": "x^2 - 5x + 4 = 0"})
        internal_samples.append(float(sample["metrics"]["durationMs"]))
    external_per_call = (time.perf_counter_ns() - started) / 1_000_000 / 1_000
    internal = statistics.median(internal_samples)
    overhead = max(0.0, external_per_call - internal)
    overhead_ratio = overhead / internal if internal else 0.0
    report = {
        "platform": "Windows x64",
        "iterationsPerScenario": 600,
        "results": results,
        "boundaryEstimate": {
            "sampleCoreAndConversionMs": internal,
            "externalPerCallMs": external_per_call,
            "estimatedPythonBoundaryMs": overhead,
            "estimatedOverheadRatio": overhead_ratio,
        },
        "targets": {
            "singleLineP95Ms": 2,
            "singleStepP95Ms": 10,
            "trace20LinesP95Ms": 100,
            "replayP95Ms": 150,
            "fullTrace200P95Ms": 100,
            "incrementalReplay200P95Ms": 100,
        },
    }
    report_dir = ROOT / "build" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    def row(label: str, key: str, target: str) -> str:
        value = results[key]["p95Ms"]
        passed = value < float(target.split()[1])
        return f"| {label} | {value:.3f} ms | {target} | {'通过' if passed else '未达标'} |"

    markdown = f"""# NeoMath 性能报告

本报告由 `python tools/benchmark/run_benchmarks.py` 在当前 Windows x64 机器上实测生成，
每项预热 20 次、采样 600 次。数据不是估算值。

| 场景 | P95 | 目标 | 结果 |
|---|---:|---:|---|
{row("单行解析", "parseSingleLine", "< 2 ms")}
{row("一次方程分析", "analyzeLinear", "< 10 ms")}
{row("二次方程分析", "analyzeQuadratic", "< 10 ms")}
{row("20 行 Trace", "trace20Lines", "< 100 ms")}
{row("4 步增量 Replay", "replay", "< 150 ms")}
{row("200 步全量 Trace", "fullTrace200", "< 100 ms")}
{row("200 步增量 Replay", "incrementalReplay200", "< 100 ms")}

四个 Demo 合并 P95：{results["fourDemos"]["p95Ms"]:.3f} ms。

边界估算：外部每次调用 {external_per_call:.4f} ms，C++ 计算及 dict 转换
{internal:.4f} ms，估算 Python 调用边界 {overhead:.4f} ms，
比率 {overhead_ratio:.1%}。该比率仅用于定位边界成本，不伪装成精确 profiler 数据。
完整原始数据见 `build/reports/benchmark.json`。

## 增量优化对比

针对 200 步文档修改最后一步的场景，全量 Trace P50 为
{results["fullTrace200"]["p50Ms"]:.3f} ms，增量 Replay P50 为
{results["incrementalReplay200"]["p50Ms"]:.3f} ms，复用 199 个状态，P50 加速约
{results["fullTrace200"]["p50Ms"] / results["incrementalReplay200"]["p50Ms"]:.2f} 倍。
该结果包含 pybind 转换完整响应的成本。
"""
    (ROOT / "docs").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "PERFORMANCE_REPORT.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
