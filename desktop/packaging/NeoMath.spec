# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

import neomath_core
from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPEC).resolve().parents[1]
pyd_path = Path(neomath_core.__file__).resolve()
datas = collect_data_files("neomath", includes=["ui/**/*"])
datas.extend(
    [
        (str(project_root / "LICENSE"), "."),
        (str(project_root / "docs" / "USER_GUIDE.md"), "docs"),
        (str(project_root / "docs" / "THIRD_PARTY_NOTICES.md"), "docs"),
    ]
)

analysis = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root / "src")],
    binaries=[(str(pyd_path), ".")],
    datas=datas,
    hiddenimports=[
        "webview",
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
    ],
    excludes=[
        "sympy",
        "pytest",
        "ruff",
        "mypy",
        "catch2",
        "numpy",
        "PIL",
        "cryptography",
        "bcrypt",
        "chardet",
        "charset_normalizer",
        "pygments",
        "jinja2",
        "mako",
        "paste",
        "eventlet",
        "gevent",
        "psutil",
        "yaml",
        "webview.platforms.cef",
        "webview.platforms.cocoa",
        "webview.platforms.gtk",
        "webview.platforms.qt",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="NeoMath",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    version=str(project_root / "packaging" / "version_info.txt"),
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="NeoMath",
)
