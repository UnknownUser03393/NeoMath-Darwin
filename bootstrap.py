"""一键启动 NeoMath 前后端。

用法：
    python bootstrap.py

后端会启动 desktop 的 C++ MathCore HTTP 服务（默认 127.0.0.1:8765），
前端会启动 ui-mockups 的 Next.js 开发服务（默认 localhost:3000），
两个服务都 ready 后自动打开浏览器。
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "desktop"
FRONTEND_DIR = ROOT / "ui-mockups"
BACKEND_URL = "http://127.0.0.1:8765/api/health"
FRONTEND_URL = "http://localhost:3000/"


def log(level: str, message: str) -> None:
    prefix = {"info": "[INFO]", "ok": "[OK]", "warn": "[WARN]", "err": "[ERR]"}[level]
    print(f"{prefix} {message}", flush=True)


def wait_for(url: str, timeout: float = 60.0, interval: float = 0.4) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                return response.status == 200
        except Exception:
            time.sleep(interval)
    return False


def is_port_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def _python_executable() -> str:
    if sys.platform == "win32":
        venv_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = BACKEND_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _windows_popen_kwargs() -> dict[str, int]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {}


def start_backend() -> subprocess.Popen | None:
    if is_port_ready(BACKEND_URL):
        log("info", "MathCore HTTP 服务已在运行，复用中...")
        return None

    log("info", "启动 C++ MathCore 后端...")
    env = os.environ.copy()
    src_dir = str(BACKEND_DIR / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        [src_dir, env.get("PYTHONPATH", "")] if env.get("PYTHONPATH") else [src_dir]
    )
    proc = subprocess.Popen(
        [_python_executable(), "-m", "neomath", "--serve"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=None,
        stderr=None,
        text=True,
        **_windows_popen_kwargs(),
    )
    if wait_for(BACKEND_URL, timeout=30.0):
        log("ok", "MathCore 后端已就绪")
        return proc
    log("err", "后端在 30 秒内未就绪，请检查 desktop 环境")
    terminate(proc)
    return None


def start_frontend() -> subprocess.Popen | None:
    if is_port_ready(FRONTEND_URL):
        log("info", "前端 dev server 已在运行，复用中...")
        return None

    npm = shutil.which("npm")
    if npm is None:
        log("err", "找不到 npm，请确认 Node.js 已安装")
        return None

    log("info", "启动 Next.js 前端 dev server...")
    proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=FRONTEND_DIR,
        stdout=None,
        stderr=None,
        text=True,
        **_windows_popen_kwargs(),
    )
    if wait_for(FRONTEND_URL, timeout=90.0):
        log("ok", "前端已就绪：http://localhost:3000")
        return proc
    log("err", "前端在 90 秒内未就绪")
    proc.terminate()
    return None


def terminate(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def main() -> int:
    log("info", "正在拉起 NeoMath 前后端...")
    backend = start_backend()
    if backend is None and not is_port_ready(BACKEND_URL):
        return 1

    frontend = start_frontend()
    if frontend is None and not is_port_ready(FRONTEND_URL):
        terminate(backend)
        return 1

    log("ok", "全部就绪，正在打开浏览器...")
    webbrowser.open(FRONTEND_URL)

    print("\n按 Ctrl+C 停止前后端\n", flush=True)
    try:
        while True:
            if backend is not None and backend.poll() is not None:
                log("warn", f"后端已退出，code={backend.returncode}")
                break
            if frontend is not None and frontend.poll() is not None:
                log("warn", f"前端已退出，code={frontend.returncode}")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n", flush=True)
        log("info", "收到 Ctrl+C，正在关闭服务...")
    finally:
        terminate(frontend)
        terminate(backend)
        log("ok", "已退出")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
