from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from neomath.settings_store import load_settings


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    dashscope_base_url: str
    qwen_model: str
    qwen_api_key: str | None
    autosave_seconds: int = 15

    @classmethod
    def from_environment(cls) -> "AppConfig":
        data_dir = Path(os.environ.get("NEOMATH_DATA_DIR", Path.home() / ".neomath"))
        persisted = load_settings(data_dir)
        env_key = os.environ.get("DASHSCOPE_API_KEY") or None
        stored_key = persisted.get("qwen_api_key")
        if isinstance(stored_key, str) and stored_key.strip():
            env_key = stored_key.strip()
        model = os.environ.get("NEOMATH_QWEN_MODEL", "qwen-plus")
        stored_model = persisted.get("qwen_model")
        if isinstance(stored_model, str) and stored_model.strip():
            model = stored_model.strip()
        autosave = 15
        stored_autosave = persisted.get("autosave_seconds")
        if isinstance(stored_autosave, int) and 5 <= stored_autosave <= 600:
            autosave = stored_autosave
        return cls(
            data_dir=data_dir,
            dashscope_base_url=os.environ.get(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ).rstrip("/"),
            qwen_model=model,
            qwen_api_key=env_key,
            autosave_seconds=autosave,
        )

    def with_updates(
        self,
        *,
        qwen_api_key: str | None | object = ...,
        qwen_model: str | object = ...,
        autosave_seconds: int | object = ...,
    ) -> "AppConfig":
        updates: dict[str, object] = {}
        if qwen_api_key is not ...:
            updates["qwen_api_key"] = qwen_api_key
        if qwen_model is not ...:
            updates["qwen_model"] = qwen_model
        if autosave_seconds is not ...:
            updates["autosave_seconds"] = autosave_seconds
        return replace(self, **updates)  # type: ignore[arg-type]
