from __future__ import annotations

import argparse
import json
from typing import Literal, Sequence, cast

from neomath.app import DEMOS, run_desktop
from neomath.core_client import NeoMathCoreClient
from neomath.server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NeoMath - \u6570\u5b66\u52a8\u6001\u8c03\u8bd5\u73af\u5883"
    )
    parser.add_argument("--demo", choices=sorted(DEMOS), help="load a built-in demo")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="print the trace without opening a window",
    )
    parser.add_argument(
        "--smoke-ui",
        "--smoke-gui",
        dest="smoke_ui",
        action="store_true",
        help="verify the real pywebview UI and close it automatically",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="run the local HTTP core server (API + AOT notebook static UI)",
    )
    parser.add_argument(
        "--ui",
        choices=("auto", "notebook", "legacy"),
        default="auto",
        help="desktop shell: AOT React notebook (default when built) or legacy debugger",
    )
    parser.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8765, help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.serve:
        run_server(args.host, args.port)
        return 0
    if args.headless:
        source = DEMOS[args.demo or "lost-root"]["source"]
        result = NeoMathCoreClient().run_trace({"source": source})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    # Automated smoke still exercises the legacy shell selectors.
    ui = "legacy" if args.smoke_ui else str(args.ui)
    ui_mode = cast('Literal["auto", "notebook", "legacy"]', ui)
    return 0 if run_desktop(args.demo, smoke_ui=args.smoke_ui, ui=ui_mode) else 1


if __name__ == "__main__":
    raise SystemExit(main())

