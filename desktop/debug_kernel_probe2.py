"""Dump what the WebView2 renderer actually mounted + console errors."""
from __future__ import annotations

import threading
import time

import webview

from neomath.bridge import NeoMathBridge
from neomath.config import AppConfig
from neomath.server import create_server

config = AppConfig.from_environment()
bridge = NeoMathBridge(config)
http_server, bridge, base_url = create_server("127.0.0.1", 0, bridge=bridge, serve_notebook=True)
threading.Thread(target=http_server.serve_forever, daemon=True).start()
ui_url = f"{base_url}/"
print(f"[probe2] server at {ui_url}", flush=True)


def read_state() -> None:
    time.sleep(4)
    for _ in range(3):
        try:
            probe = window.evaluate_js(
                """(() => ({
                    rootHtml: (document.getElementById('root')?.innerHTML || '').slice(0, 800),
                    rootClass: document.getElementById('root')?.className || '',
                    bodyClass: document.body.className || '',
                    title: document.title,
                    url: location.href,
                }))()"""
            )
            print(f"[probe2] {probe}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[probe2] error: {exc}", flush=True)
        time.sleep(1)
    window.destroy()


window = webview.create_window(
    "NeoMath probe2",
    url=ui_url,
    width=1200,
    height=800,
    min_size=(900, 600),
    background_color="#14161a",
    text_select=True,
)
window.events.loaded += read_state
webview.start(debug=False)
http_server.shutdown()
http_server.server_close()
print("[probe2] done", flush=True)
