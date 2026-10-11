"""Local HTTP gateway: MathCore bridge API + optional AOT notebook static UI.

The desktop shell can talk through pywebview JS API *or* load the React
Notebook that was ahead-of-time compiled into ``ui/notebook/``. Runtime needs
no Node — only static files and the C++ core behind this process.
"""

from __future__ import annotations

import json
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from neomath.bridge import NeoMathBridge
from neomath.config import AppConfig
from neomath.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

EXPOSED_METHODS = frozenset({
    "analyzeDocument",
    "runTrace",
    "replay",
    "getCompletions",
    "executeTransformation",
    "evaluateProbe",
    "requestAiExplanation",
    "compileAiIntent",
    "parseContentEdl",
    "autosaveEdDocument",
    "getMathBackends",
    "validateStep",
    "validateDerivations",
    "derivationBlame",
    "exportDocument",
    "resolveContext",
    "inspectContext",
    "contextDiagnostics",
    "getCapabilities",
    "getRecentDocuments",
    "getSettings",
    "saveSettings",
    "stop",
    "parseXdltDocument",
    "renderXdltHtml",
    "buildXdltDocument",
    "createXdltSession",
    "updateXdltSession",
    "destroyXdltSession",
    "getXdltReferenceCss",
    "listNotebooks",
    "loadNotebook",
    "saveNotebook",
    "renameNotebook",
    "seedNotebooks",
    "listXdltDocuments",
    "loadXdltDocument",
    "saveXdltDocument",
    "renameXdltDocument",
    "seedXdltDocuments",
})
PAYLOADLESS_METHODS = frozenset({
    "getCapabilities",
    "getRecentDocuments",
    "getSettings",
    "stop",
    "listNotebooks",
    "seedNotebooks",
    "listXdltDocuments",
    "seedXdltDocuments",
})


def notebook_static_dir() -> Path:
    return Path(__file__).resolve().parent / "ui" / "notebook"


def notebook_available() -> bool:
    return (notebook_static_dir() / "index.html").is_file()


def _make_handler(
    bridge: NeoMathBridge,
    static_dir: Path | None,
) -> type[BaseHTTPRequestHandler]:
    class CoreRequestHandler(BaseHTTPRequestHandler):
        server_version = "NeoMathCore/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.address_string(), format % args)

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib naming
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802 - stdlib naming
            parsed = urlparse(self.path)
            path = unquote(parsed.path or "/")
            if path in ("/api/health", "/api"):
                capabilities = bridge.getCapabilities()
                result = capabilities.get("result", {})
                if isinstance(result, dict):
                    result = {
                        **result,
                        "server": "neomath-http",
                        "notebook": bool(static_dir and static_dir.is_dir()),
                    }
                else:
                    result = {"server": "neomath-http"}
                self._send_json(200, {"ok": True, "result": result})
                return
            if path.startswith("/api/"):
                self._send_json(404, {
                    "ok": False,
                    "error": {
                        "type": "not_found",
                        "code": "NOT_FOUND",
                        "message": f"unknown path: {path}",
                    },
                })
                return
            if static_dir is not None and static_dir.is_dir():
                self._serve_static(path)
                return
            self._send_json(404, {
                "ok": False,
                "error": {
                    "type": "not_found",
                    "code": "NOT_FOUND",
                    "message": (
                        f"unknown path: {path} "
                        "(build the notebook SPA with npm run build:spa)"
                    ),
                },
            })

        def _serve_static(self, path: str) -> None:
            assert static_dir is not None
            relative = path.lstrip("/")
            if not relative or relative.endswith("/"):
                relative = "index.html"
            candidate = (static_dir / relative).resolve()
            try:
                candidate.relative_to(static_dir.resolve())
            except ValueError:
                self._send_json(403, {
                    "ok": False,
                    "error": {
                        "type": "forbidden",
                        "code": "PATH_ESCAPE",
                        "message": "invalid static path",
                    },
                })
                return
            if candidate.is_dir():
                candidate = candidate / "index.html"
            if not candidate.is_file():
                # SPA fallback for client-side routes
                fallback = static_dir / "index.html"
                if fallback.is_file() and "." not in Path(relative).name:
                    candidate = fallback
                else:
                    self._send_bytes(404, b"Not found", "text/plain; charset=utf-8")
                    return
            content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            if candidate.suffix == ".js":
                content_type = "text/javascript; charset=utf-8"
            elif candidate.suffix == ".css":
                content_type = "text/css; charset=utf-8"
            elif candidate.suffix == ".svg":
                content_type = "image/svg+xml"
            elif candidate.suffix == ".html":
                content_type = "text/html; charset=utf-8"
            elif candidate.suffix == ".woff2":
                content_type = "font/woff2"
            elif candidate.suffix == ".woff":
                content_type = "font/woff"
            elif candidate.suffix == ".ttf":
                content_type = "font/ttf"
            body = candidate.read_bytes()
            self._send_bytes(200, body, content_type)

        def do_POST(self) -> None:  # noqa: N802 - stdlib naming
            path = urlparse(self.path).path.rstrip("/")
            if not path.startswith("/api/"):
                self._send_json(404, {
                    "ok": False,
                    "error": {
                        "type": "not_found",
                        "code": "NOT_FOUND",
                        "message": f"unknown path: {path}",
                    },
                })
                return
            method = path[len("/api/"):]
            if method not in EXPOSED_METHODS:
                self._send_json(404, {
                    "ok": False,
                    "error": {
                        "type": "not_found",
                        "code": "UNKNOWN_METHOD",
                        "message": f"unknown bridge method: {method}",
                    },
                })
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw.decode("utf-8") or "{}")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be a JSON object")
            except (ValueError, UnicodeDecodeError) as error:
                self._send_json(400, {
                    "ok": False,
                    "error": {
                        "type": "validation_error",
                        "code": "BAD_JSON",
                        "message": str(error),
                    },
                })
                return
            try:
                handler = getattr(bridge, method)
                result = (
                    handler()
                    if method in PAYLOADLESS_METHODS
                    else handler(payload)
                )
            except Exception as error:  # pragma: no cover - defensive boundary
                LOGGER.exception("Bridge method %s failed", method)
                self._send_json(500, {
                    "ok": False,
                    "error": {
                        "type": "server_error",
                        "code": "BRIDGE_EXCEPTION",
                        "message": str(error),
                    },
                })
                return
            self._send_json(200, result)

    return CoreRequestHandler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    bridge: NeoMathBridge | None = None,
    serve_notebook: bool = True,
) -> tuple[ThreadingHTTPServer, NeoMathBridge, str]:
    config = AppConfig.from_environment()
    configure_logging(config.data_dir)
    active_bridge = bridge or NeoMathBridge(config)
    static_dir = notebook_static_dir() if serve_notebook and notebook_available() else None
    server = ThreadingHTTPServer(
        (host, port),
        _make_handler(active_bridge, static_dir),
    )
    if port == 0:
        port = int(server.server_address[1])
    base_url = f"http://{host}:{port}"
    return server, active_bridge, base_url


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server, _bridge, base_url = create_server(host, port, serve_notebook=True)
    static = notebook_static_dir() if notebook_available() else None
    print(f"NeoMath MathCore HTTP server listening on {base_url}")
    if static is not None:
        print(f"Notebook AOT UI: {base_url}/  (from {static})")
    else:
        print("Notebook AOT UI not found — run: cd ui-mockups && npm run build:spa")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
