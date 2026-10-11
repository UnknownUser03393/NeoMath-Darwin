from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from neomath.settings_store import load_settings

# The single provider-specific default: DashScope's OpenAI-compatible endpoint.
# Everything else treats the backend as a generic OpenAI-compatible client.
DEFAULT_OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_OPENAI_MODEL = "qwen-plus"


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    openai_base_url: str
    openai_model: str
    openai_api_key: str | None
    autosave_seconds: int = 15

    @classmethod
    def from_environment(cls) -> "AppConfig":
        data_dir = Path(os.environ.get("NEOMATH_DATA_DIR", Path.home() / ".neomath"))
        persisted = load_settings(data_dir)
        env_key = os.environ.get("OPENAI_API_KEY") or None
        stored_key = persisted.get("openai_api_key")
        if isinstance(stored_key, str) and stored_key.strip():
            env_key = stored_key.strip()
        model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        stored_model = persisted.get("openai_model")
        if isinstance(stored_model, str) and stored_model.strip():
            model = stored_model.strip()
        autosave = 15
        stored_autosave = persisted.get("autosave_seconds")
        if isinstance(stored_autosave, int) and 5 <= stored_autosave <= 600:
            autosave = stored_autosave
        return cls(
            data_dir=data_dir,
            openai_base_url=os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).rstrip("/"),
            openai_model=model,
            openai_api_key=env_key,
            autosave_seconds=autosave,
        )

    def with_updates(
        self,
        *,
        openai_api_key: str | None | object = ...,
        openai_model: str | object = ...,
        autosave_seconds: int | object = ...,
    ) -> "AppConfig":
        updates: dict[str, object] = {}
        if openai_api_key is not ...:
            updates["openai_api_key"] = openai_api_key
        if openai_model is not ...:
            updates["openai_model"] = openai_model
        if autosave_seconds is not ...:
            updates["autosave_seconds"] = autosave_seconds
        return replace(self, **updates)  # type: ignore[arg-type]
