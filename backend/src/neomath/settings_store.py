"""Local preference store under the user data directory.

Secrets stay off document files and out of logs; the API key may live only in
this settings file so the Settings dialog can enable Qwen without restarting
from a shell environment variable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SETTINGS_NAME = "settings.json"
ALLOWED_KEYS = frozenset({"qwen_api_key", "qwen_model", "autosave_seconds"})


def settings_path(data_dir: Path) -> Path:
    return data_dir / SETTINGS_NAME


def load_settings(data_dir: Path) -> dict[str, Any]:
    path = settings_path(data_dir)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {key: raw[key] for key in ALLOWED_KEYS if key in raw}


def save_settings(data_dir: Path, values: dict[str, Any]) -> dict[str, Any]:
    data_dir.mkdir(parents=True, exist_ok=True)
    current = load_settings(data_dir)
    for key in ALLOWED_KEYS:
        if key not in values:
            continue
        value = values[key]
        if value is None or value == "":
            current.pop(key, None)
        else:
            current[key] = value
    path = settings_path(data_dir)
    path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return current
