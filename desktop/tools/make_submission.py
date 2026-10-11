from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
OUTPUT = ROOT / "build" / "submission" / "NeoMath_submission.zip"
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "build",
    "dist",
    "submission",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
EXCLUDED_SUFFIXES = {".obj", ".o", ".pdb", ".pyc", ".log"}


def source_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if (
            path.is_file()
            and not any(part in EXCLUDED_PARTS for part in relative.parts)
            and path.suffix.lower() not in EXCLUDED_SUFFIXES
        ):
            files.append(path)
    return files


def main() -> int:
    release = ROOT / "dist" / "NeoMath"
    ppt = ROOT / "submission" / "NeoMath_作品说明.pptx"
    if not (release / "NeoMath.exe").exists():
        raise FileNotFoundError("run python tools/make_release.py first")
    if not ppt.exists():
        raise FileNotFoundError("run python tools/generate_ppt.py first")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in release.rglob("*"):
            if path.is_file():
                archive.write(path, Path("program") / path.relative_to(release))
        for path in source_files():
            archive.write(path, Path("source") / path.relative_to(ROOT))
        archive.write(PROJECT_ROOT / "README.md", "README.md")
        archive.write(ppt, Path("materials") / ppt.name)
        for pattern in ("*.mp4", "*.mov"):
            for video in (ROOT / "submission").glob(pattern):
                archive.write(video, Path("materials") / video.name)
    size = OUTPUT.stat().st_size
    report = {
        "ok": size < 100 * 1024 * 1024,
        "path": str(OUTPUT),
        "sizeBytes": size,
        "limitBytes": 100 * 1024 * 1024,
    }
    (ROOT / "build" / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "build" / "reports" / "submission.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
