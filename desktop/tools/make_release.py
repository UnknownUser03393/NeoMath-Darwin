from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def find_dumpbin() -> Path | None:
    roots = [
        Path(r"D:\Program\VisualStudio\VC\Tools\MSVC"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2019"),
    ]
    matches: list[Path] = []
    for root in roots:
        if root.exists():
            matches.extend(root.rglob("dumpbin.exe"))
    x64 = [
        path
        for path in matches
        if "hostx64" in str(path).lower() and "\\x64\\" in str(path).lower()
    ]
    return sorted(x64 or matches)[-1] if (x64 or matches) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    dist = ROOT / "dist" / "NeoMath"
    if not args.skip_build:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--clean",
                str(ROOT / "packaging" / "NeoMath.spec"),
            ],
            cwd=ROOT,
            check=True,
        )
    executable = dist / "NeoMath.exe"
    if not executable.exists():
        raise FileNotFoundError(executable)
    forbidden = ("sympy", "pytest", "catch2", "cmake", "ninja", "node_modules")
    found = [
        str(path.relative_to(dist))
        for path in dist.rglob("*")
        if any(token in path.name.lower() for token in forbidden)
    ]
    smoke = subprocess.run(
        [str(executable), "--demo", "lost-root", "--headless"],
        cwd=dist,
        timeout=30,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    gui_smoke_dir = ROOT / "build" / "package-gui-smoke"
    gui_smoke_env = os.environ.copy()
    gui_smoke_env["NEOMATH_DATA_DIR"] = str(gui_smoke_dir)
    gui_smoke = subprocess.run(
        [str(executable), "--demo", "lost-root", "--smoke-gui"],
        cwd=dist,
        env=gui_smoke_env,
        timeout=30,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    packaged_pyd = next(dist.rglob("neomath_core*.pyd"), None)
    dumpbin = find_dumpbin()
    dependencies: list[str] = []
    if packaged_pyd is not None and dumpbin is not None:
        inspected = subprocess.run(
            [str(dumpbin), "/dependents", str(packaged_pyd)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        dependencies = [
            line.strip()
            for line in inspected.stdout.splitlines()
            if line.strip().lower().endswith(".dll")
        ]
    # Windowed PyInstaller suppresses stdout, so the exit code is the smoke-test signal.
    gui_smoke_path = gui_smoke_dir / "ui_smoke.json"
    gui_smoke_result = (
        json.loads(gui_smoke_path.read_text(encoding="utf-8"))
        if gui_smoke_path.exists()
        else {}
    )
    report = {
        "ok": (
            smoke.returncode == 0
            and gui_smoke.returncode == 0
            and bool(gui_smoke_result.get("ok"))
            and not found
        ),
        "executable": str(executable),
        "sizeBytes": directory_size(dist),
        "forbiddenMatches": found,
        "smokeExitCode": smoke.returncode,
        "guiSmokeExitCode": gui_smoke.returncode,
        "guiSmoke": gui_smoke_result,
        "pyd": str(packaged_pyd) if packaged_pyd else None,
        "pydDependencies": dependencies,
    }
    report_dir = ROOT / "build" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "release.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
