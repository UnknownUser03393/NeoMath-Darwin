from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "build" / "reports"
VERIFY_BUILD = ROOT / "build" / "verify"


@dataclass
class PhaseResult:
    name: str
    ok: bool
    duration_seconds: float
    command: list[str] = field(default_factory=list)
    output_tail: str = ""


def run(command: list[str], *, name: str, timeout: int = 600) -> PhaseResult:
    print(f"\n=== {name} ===", flush=True)
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    if output:
        print(output, flush=True)
    return PhaseResult(
        name=name,
        ok=completed.returncode == 0,
        duration_seconds=time.perf_counter() - started,
        command=command,
        output_tail=output[-6000:],
    )


def formatter_path() -> Path | None:
    command = shutil.which("clang-format")
    if command:
        return Path(command)
    candidates = list(Path(r"D:\Program\VisualStudio").glob("VC/Tools/Llvm/**/clang-format.exe"))
    return sorted(candidates)[-1] if candidates else None


def check_cpp_format() -> PhaseResult:
    formatter = formatter_path()
    if formatter is None:
        return PhaseResult("C++ Format Check", False, 0, output_tail="clang-format not found")
    sources = sorted(
        path
        for path in (ROOT / "cpp").rglob("*")
        if path.suffix in {".cpp", ".hpp"} and "third_party" not in path.parts
    )
    return run(
        [str(formatter), "--dry-run", "--Werror", "--style=file", *map(str, sources)],
        name="C++ Format Check",
    )


def pybind11_cmake_dir() -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "pybind11", "--cmakedir"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return completed.stdout.strip()


def read_json(name: str) -> dict[str, Any]:
    path = REPORT_DIR / name
    if not path.exists():
        return {}
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def command_text(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except OSError:
        return "unavailable"
    return (completed.stdout or completed.stderr).strip()


def collect_python_count() -> int:
    text = command_text([sys.executable, "-m", "pytest", "--collect-only", "-q"])
    match = re.search(r"(\d+) tests? collected", text)
    if match:
        return int(match.group(1))
    return sum(int(value) for value in re.findall(r":\s*(\d+)\s*$", text, re.MULTILINE))


def collect_cpp_count() -> int:
    return sum(
        len(re.findall(r"\bTEST_CASE\s*\(", path.read_text(encoding="utf-8")))
        for path in (ROOT / "cpp" / "tests").glob("*.cpp")
    )


def collect_report(phases: list[PhaseResult], *, software_only: bool) -> dict[str, Any]:
    differential = read_json("differential.json")
    benchmark = read_json("benchmark.json")
    release = read_json("release.json")
    submission = read_json("submission.json") if not software_only else {}
    secret_scan = read_json("secret_scan.json")
    ppt = read_json("ppt_validation.json") if not software_only else {}
    commit = command_text(["git", "rev-parse", "HEAD"])
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit.strip()):
        commit = "NO_COMMIT"
    configure_output = next(
        (phase.output_tail for phase in phases if phase.name == "C++ Configure"),
        "",
    )
    compiler_match = re.search(r"compiler identification is (MSVC [\d.]+)", configure_output)
    compiler = compiler_match.group(1) if compiler_match else "unavailable"
    pyd = Path(str(release.get("pyd", "")))
    return {
        "ok": all(phase.ok for phase in phases),
        "softwareOnly": software_only,
        "generatedAt": datetime.now(UTC).isoformat(),
        "gitCommit": commit,
        "gitStatus": command_text(["git", "status", "--short"]),
        "platform": platform.platform(),
        "compiler": compiler,
        "cmake": command_text(["cmake", "--version"]).splitlines()[0],
        "ninja": command_text(["ninja", "--version"]),
        "python": sys.version,
        "cppTests": collect_cpp_count(),
        "pythonTests": collect_python_count(),
        "randomSeed": differential.get("seed"),
        "differential": {
            "requestedCases": differential.get("requestedCases"),
            "checkedCases": differential.get("checkedCases"),
            "skippedCases": differential.get("skippedCases"),
            "differenceCount": differential.get("differenceCount"),
            "differences": differential.get("differences", []),
        },
        "benchmark": benchmark,
        "pydSizeBytes": pyd.stat().st_size if pyd.is_file() else None,
        "releaseSizeBytes": release.get("sizeBytes"),
        "desktopUiSmoke": release.get("guiSmoke", {}),
        "submissionSizeBytes": submission.get("sizeBytes"),
        "openai": {
            "configured": bool(os.environ.get("OPENAI_API_KEY")),
            "liveTestsEnabled": os.environ.get("NEOMATH_RUN_LIVE_AI_TESTS") == "1",
            "offlineFallback": True,
        },
        "secretScan": secret_scan,
        "ppt": ppt,
        "knownLimitations": [
            "Exact Rational arithmetic uses checked int64 storage (63-bit positive magnitude).",
            "Quadratic equations return exact rational roots only; "
            "irrational roots are Unverified.",
            "Replay caching is bounded and process-local; a restart or unmatched "
            "prefix falls back to full recomputation.",
            "Stop is best-effort at operation boundaries; each core analysis "
            "also has a 500 ms limit.",
            "V1 supports one real variable (x), not multivariable, "
            "trigonometric, logarithmic, or calculus input.",
        ],
        "phases": [
            {
                **asdict(phase),
                "duration_seconds": round(phase.duration_seconds, 3),
            }
            for phase in phases
        ],
    }


def write_report(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "final_verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    status = "PASS" if report["ok"] else "FAIL"
    ui_checks = (
        report.get("desktopUiSmoke", {})
        .get("interactions", {})
        .get("checks", {})
    )
    lines = [
        "# NeoMath Software Verification Report",
        "",
        f"- Overall: **{status}**",
        f"- Scope: {'software only' if report['softwareOnly'] else 'full submission'}",
        f"- Git commit: `{report['gitCommit']}`",
        f"- Python: `{platform.python_version()}`",
        f"- C++ tests: {report['cppTests']}",
        f"- Python tests: {report['pythonTests']}",
        f"- Differential: {report['differential']['checkedCases']} checked / "
        f"{report['differential']['differenceCount']} differences",
        f"- Native extension: {report['pydSizeBytes']} bytes",
        f"- Release directory: {report['releaseSizeBytes']} bytes",
        f"- Desktop UI interactions: {sum(bool(value) for value in ui_checks.values())} passed",
        f"- Submission ZIP: {report['submissionSizeBytes'] or 'not in scope'}",
        f"- Secret scan: {'PASS' if report['secretScan'].get('ok') else 'FAIL'}",
        "",
        "## Phases",
        "",
    ]
    lines.extend(
        f"- [{'PASS' if phase['ok'] else 'FAIL'}] {phase['name']} "
        f"({phase['duration_seconds']:.3f}s)"
        for phase in report["phases"]
    )
    lines.extend(["", "## Known limitations", ""])
    lines.extend(f"- {item}" for item in report["knownLimitations"])
    markdown = "\n".join(lines) + "\n"
    (REPORT_DIR / "final_verification.md").write_text(markdown, encoding="utf-8")
    (ROOT / "docs" / "VALIDATION_REPORT.md").write_text(markdown, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the NeoMath verification pipeline.")
    parser.add_argument(
        "--software-only",
        action="store_true",
        help="Skip presentation and submission-material generation.",
    )
    args = parser.parse_args()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    phases: list[PhaseResult] = []

    def execute(action: Callable[[], PhaseResult]) -> bool:
        result = action()
        phases.append(result)
        if not result.ok:
            print(f"FAILED: {result.name}", flush=True)
        return result.ok

    if not execute(check_cpp_format):
        write_report(collect_report(phases, software_only=args.software_only))
        return 1

    configure = [
        "cmake",
        "-S",
        ".",
        "-B",
        str(VERIFY_BUILD),
        "--fresh",
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DNEOMATH_BUILD_TESTS=ON",
        f"-Dpybind11_DIR={pybind11_cmake_dir()}",
    ]
    commands: list[tuple[str, list[str], int]] = [
        ("C++ Configure", configure, 180),
        ("C++ Build", ["cmake", "--build", str(VERIFY_BUILD), "--parallel"], 300),
        (
            "C++ Unit Tests",
            ["ctest", "--test-dir", str(VERIFY_BUILD), "--output-on-failure"],
            120,
        ),
        (
            "Python Extension Build",
            [sys.executable, "-m", "pip", "install", "-e", ".", "--no-build-isolation"],
            300,
        ),
        ("Python Tests", [sys.executable, "-m", "pytest", "-q"], 180),
        ("Golden Tests", [sys.executable, "-m", "pytest", "tests/golden", "-q"], 120),
        (
            "Differential 10,000",
            [
                sys.executable,
                "tools/differential/run_differential.py",
                "--cases",
                "10000",
                "--seed",
                "20260724",
            ],
            300,
        ),
        ("Benchmark", [sys.executable, "tools/benchmark/run_benchmarks.py"], 180),
        ("Ruff", [sys.executable, "-m", "ruff", "check", "src", "tests", "tools", "scripts"], 120),
        ("Type Check", [sys.executable, "-m", "mypy", "src/neomath"], 120),
        ("Secret Scan", [sys.executable, "tools/scan_secrets.py"], 120),
        ("PyInstaller + Desktop UI Smoke", [sys.executable, "tools/make_release.py"], 600),
    ]
    if not args.software_only:
        commands.extend(
            [
                ("PPT Generation", [sys.executable, "tools/generate_ppt.py"], 180),
                ("PPT Validation", [sys.executable, "tools/validate_ppt.py"], 120),
                ("Submission Dry Run", [sys.executable, "tools/make_submission.py"], 300),
            ]
        )
    for name, command, timeout in commands:
        if not execute(lambda n=name, c=command, t=timeout: run(c, name=n, timeout=t)):
            write_report(collect_report(phases, software_only=args.software_only))
            return 1
    report = collect_report(phases, software_only=args.software_only)
    write_report(report)
    print(json.dumps({"ok": report["ok"], "report": str(REPORT_DIR)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
