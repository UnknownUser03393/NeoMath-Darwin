from __future__ import annotations

import json
from pathlib import Path

from neomath.app import DEMOS
from neomath.core_client import NeoMathCoreClient

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    client = NeoMathCoreClient()
    source = DEMOS["lost-root"]["source"]
    fixture = {
        "startup": {"demo": "lost-root", "demos": DEMOS},
        "trace": client.run_trace({"source": source}),
        "completions": client.get_completions({"source": source}, 2),
        "capabilities": client.get_capabilities(),
    }
    output = ROOT / "build" / "reports" / "ui_fixture.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
