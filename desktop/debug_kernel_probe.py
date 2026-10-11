"""Probe the notebook UI inside the real pywebview/WebView2 renderer.

Loads the AOT notebook exactly like `run_desktop` does (same-origin HTTP),
then reads back the kernel status text to see whether the UI ever leaves
the "checking" (正在连接 MathCore) state.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import webview

from neomath.bridge import NeoMathBridge
from neomath.config import AppConfig
from neomath.server import create_server

config = AppConfig.from_environment()
bridge = NeoMathBridge(config)
http_server, bridge, base_url = create_server("127.0.0.1", 0, bridge=bridge, serve_notebook=True)
threading.Thread(target=http_server.serve_forever, daemon=True).start()
ui_url = f"{base_url}/"
print(f"[probe] server at {ui_url}", flush=True)


def read_state() -> None:
    time.sleep(4)
    for _ in range(6):
        try:
            probe = window.evaluate_js(
                """(() => {
                    const el = document.querySelector('.kernel-caption');
                    const statusEl = document.querySelector('.status-pill');
                    return {
                        caption: el ? el.textContent : null,
                        statusPill: statusEl ? statusEl.textContent : null,
                        root: document.getElementById('root')?.children.length ?? -1,
                    };
                })()"""
            )
            print(f"[probe] state = {json.dumps(probe, ensure_ascii=False)}", flush=True)
            if probe and probe.get("caption") not in (None, "正在连接 MathCore"):
                break
        except Exception as exc:  # noqa: BLE001
            print(f"[probe] evaluate_js error: {exc}", flush=True)
        time.sleep(1)
    window.destroy()


window = webview.create_window(
    "NeoMath probe",
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
print("[probe] done", flush=True)
