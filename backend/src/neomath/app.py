from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from time import sleep
from typing import Any, Literal

from neomath.bridge import NeoMathBridge
from neomath.config import AppConfig
from neomath.logging_config import configure_logging
from neomath.server import create_server, notebook_available

DEMOS: dict[str, dict[str, str]] = {
    "lost-root": {
        "title": "Demo 1 \u00b7 \u4e22\u6839",
        "source": "x(x - 1) = 0\nx - 1 = 0\nx = 1",
    },
    "extraneous-root": {
        "title": "Demo 2 \u00b7 \u5e73\u65b9\u589e\u6839",
        "source": (
            "sqrt(x) = x - 2\n"
            "x = (x - 2)^2\n"
            "x^2 - 5x + 4 = 0\n"
            "x = 1 or x = 4"
        ),
    },
    "domain-expansion": {
        "title": "Demo 3 \u00b7 \u5b9a\u4e49\u57df\u6269\u5927",
        "source": "(x - 1) / (x - 1) = 1\n1 = 1",
    },
    "semantic-completion": {
        "title": "Demo 4 \u00b7 \u8bed\u4e49\u8865\u5168",
        "source": "x^2 - 4 = 0",
    },
}


UiMode = Literal["auto", "notebook", "legacy"]


def run_desktop(
    initial_demo: str | None = None,
    *,
    smoke_ui: bool = False,
    ui: UiMode = "auto",
) -> bool:
    import webview

    config = AppConfig.from_environment()
    configure_logging(config.data_dir)
    bridge = NeoMathBridge(config)
    # Smoke selectors target the legacy debugger shell; keep that path stable.
    prefer_notebook = (
        not smoke_ui
        and ui != "legacy"
        and (ui == "notebook" or (ui == "auto" and notebook_available()))
    )
    http_server = None
    base_url = ""
    if prefer_notebook:
        http_server, bridge, base_url = create_server(
            "127.0.0.1",
            0,
            bridge=bridge,
            serve_notebook=True,
        )
        Thread(target=http_server.serve_forever, daemon=True).start()
        ui_url = f"{base_url}/"
        background = "#14161a"
        mode = "notebook-aot"
    else:
        ui_path = Path(__file__).resolve().parent / "ui" / "index.html"
        ui_url = ui_path.as_uri()
        background = "#F3F0E8"
        mode = "legacy-pywebview"
    startup: dict[str, Any] = {
        "demo": initial_demo or "lost-root",
        "demos": DEMOS,
        "autosaveSeconds": config.autosave_seconds,
        "uiMode": mode,
        "coreBaseUrl": base_url,
    }
    smoke_result: dict[str, Any] = {
        "ok": not smoke_ui,
        "mode": mode,
        "demo": startup["demo"],
    }
    window = webview.create_window(
        "NeoMath \u00b7 \u6570\u5b66\u52a8\u6001\u8c03\u8bd5\u73af\u5883",
        url=ui_url,
        js_api=bridge,
        width=1440,
        height=900,
        min_size=(1100, 700),
        background_color=background,
        # WebView2 already supports Ctrl± / Ctrl+wheel; pywebview defaults this off.
        zoomable=True,
        text_select=True,
    )
    if window is None:
        raise RuntimeError("pywebview failed to create the NeoMath window")

    def verify_rendered_ui() -> None:
        last_error = "UI did not become ready within 10 seconds"
        baseline_ok = False
        for _ in range(40):
            sleep(0.25)
            try:
                rendered = window.evaluate_js(
                    """(() => ({
                        title: document.querySelector('#document-title')?.value || '',
                        editorLines: document.querySelector('#source-editor')?.value
                          .split(/\\r?\\n/).filter(Boolean).length || 0,
                        stepCards: document.querySelectorAll('.step-card').length,
                        rootFaultCards: document.querySelectorAll('.step-card.root_fault').length,
                        probeVisible: !document.querySelector('#probe-card')?.hidden,
                        coreStatus: document.querySelector('#core-status')?.textContent.trim() || ''
                    }))()"""
                )
                if isinstance(rendered, dict) and int(rendered.get("stepCards", 0)) >= 3:
                    smoke_result.update(rendered)
                    baseline_ok = (
                        int(rendered.get("editorLines", 0)) == 3
                        and int(rendered.get("rootFaultCards", 0)) == 1
                        and bool(rendered.get("probeVisible"))
                        and "C++ MathCore" in str(rendered.get("coreStatus", ""))
                    )
                    last_error = ""
                    break
            except Exception as error:
                last_error = str(error)
        if baseline_ok:
            window.evaluate_js(
                r"""(() => {
                    const result = {
                        done: false,
                        checks: {},
                        error: null
                    };
                    window.__NEOMATH_UI_SMOKE = result;
                    const click = (selector) => document.querySelector(selector).click();
                    const countLines = () => document.querySelector("#source-editor").value
                        .split(/\r?\n/).filter((line) => line.trim()).length;
                    const waitFor = async (predicate, label, timeout = 3000) => {
                        const started = Date.now();
                        while (!predicate()) {
                            if (Date.now() - started > timeout) {
                                throw new Error(`timeout: ${label}`);
                            }
                            await new Promise((resolve) => setTimeout(resolve, 50));
                        }
                    };
                    const check = (name, value) => {
                        result.checks[name] = Boolean(value);
                        if (!value) throw new Error(`check failed: ${name}`);
                    };
                    (async () => {
                        click("#step-button");
                        await waitFor(
                            () => document.querySelectorAll(".step-card").length === 1,
                            "single step"
                        );
                        check("step", true);

                        click("#continue-button");
                        check("continue", document.querySelectorAll(".step-card").length === 3);

                        click('[data-tab="trace"]');
                        check(
                            "traceTab",
                            document.querySelector('[data-tab="trace"]').classList.contains("active")
                        );
                        click("#probe-button");
                        check(
                            "probeButton",
                            document.querySelector('[data-tab="watch"]').classList.contains("active")
                        );

                        click("#replay-button");
                        await waitFor(
                            () => document.querySelectorAll(".step-card").length === 3,
                            "replay"
                        );
                        check("replay", true);

                        click('[data-demo="semantic-completion"]');
                        await waitFor(
                            () => countLines() === 1
                                && !document.querySelector("#completion-bar").hidden,
                            "semantic completion"
                        );
                        check("demoNavigation", true);
                        check(
                            "completion",
                            document.querySelectorAll("#completion-select option").length > 0
                        );

                        click("#apply-completion");
                        await waitFor(() => countLines() === 2, "apply completion");
                        check("applyCompletion", true);

                        document.dispatchEvent(new KeyboardEvent(
                            "keydown",
                            {key: "z", ctrlKey: true, bubbles: true}
                        ));
                        await waitFor(() => countLines() === 1, "undo");
                        check("undo", true);
                        document.dispatchEvent(new KeyboardEvent(
                            "keydown",
                            {key: "z", ctrlKey: true, shiftKey: true, bubbles: true}
                        ));
                        await waitFor(() => countLines() === 2, "redo");
                        check("redo", true);

                        click("#explain-button");
                        await waitFor(
                            () => document.querySelector("#explanation").textContent.length > 10
                                && document.querySelector('[data-tab="explain"]')
                                    .classList.contains("active"),
                            "explanation"
                        );
                        check("explain", true);

                        for (const selector of [
                            "#tutorial-button",
                            "#settings-button",
                            "#about-button"
                        ]) {
                            click(selector);
                            check(
                                selector.slice(1),
                                document.querySelector("#info-dialog").open
                            );
                            click(".dialog-close");
                        }

                        click("#stop-button");
                        await waitFor(
                            () => document.querySelector("#toast").textContent.length > 0,
                            "stop"
                        );
                        check("stop", true);

                        click("#new-document");
                        await waitFor(() => countLines() === 3, "new document");
                        check("newDocument", true);
                        click("#run-button");
                        await waitFor(
                            () => document.querySelectorAll(".step-card").length === 3,
                            "run"
                        );
                        check("run", true);

                        const editor = document.querySelector("#source-editor");
                        editor.value = "x^2 - 4 = 0";
                        editor.dispatchEvent(new Event("input", {bubbles: true}));
                        const command = document.querySelector("#ai-command");
                        command.value = "factor";
                        click("#run-ai-command");
                        await waitFor(() => countLines() === 2, "offline AI command");
                        check("aiCommand", true);

                        result.done = true;
                    })().catch((error) => {
                        result.error = String(error);
                        result.done = true;
                    });
                })()"""
            )
            for _ in range(60):
                sleep(0.25)
                interaction = window.evaluate_js("window.__NEOMATH_UI_SMOKE")
                if isinstance(interaction, dict) and interaction.get("done"):
                    smoke_result["interactions"] = interaction
                    smoke_result["ok"] = (
                        baseline_ok
                        and not interaction.get("error")
                        and all(interaction.get("checks", {}).values())
                    )
                    if interaction.get("error"):
                        last_error = str(interaction["error"])
                    break
            else:
                last_error = "UI interaction smoke did not finish within 15 seconds"
        if last_error or not baseline_ok:
            smoke_result["error"] = last_error
            smoke_result["ok"] = False
        config.data_dir.mkdir(parents=True, exist_ok=True)
        (config.data_dir / "ui_smoke.json").write_text(
            json.dumps(smoke_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        window.destroy()

    def inject_startup() -> None:
        # Keep injected JavaScript ASCII-only for every Windows WebView backend.
        window.evaluate_js(f"window.NEOMATH_STARTUP = {json.dumps(startup, ensure_ascii=True)};")
        window.evaluate_js("window.dispatchEvent(new Event('neomath-ready'));")
        if smoke_ui:
            Thread(target=verify_rendered_ui, daemon=True).start()

    window.events.loaded += inject_startup
    try:
        webview.start(debug=False)
    finally:
        if http_server is not None:
            http_server.shutdown()
            http_server.server_close()
    return bool(smoke_result["ok"])
