from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "openai_key": re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "assigned_api_key": re.compile(rb"OPENAI_API_KEY\s*=\s*[\"'][^\"']+[\"']"),
}
EXCLUDED = {".git", ".venv", "build", "dist", "__pycache__", ".pytest_cache"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=ROOT)
    args = parser.parse_args()
    findings: list[dict[str, str]] = []
    for path in args.path.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED for part in path.parts):
            continue
        if path.stat().st_size > 8 * 1024 * 1024:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append({"file": str(path.relative_to(args.path)), "pattern": name})
    report = {"ok": not findings, "findings": findings}
    report_dir = ROOT / "build" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "secret_scan.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
