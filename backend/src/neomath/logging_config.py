from __future__ import annotations

import logging
import re
from pathlib import Path


class SecretFilter(logging.Filter):
    _patterns = (
        re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
        re.compile(r"(DASHSCOPE_API_KEY\s*[=:]\s*)\S+", re.IGNORECASE),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(r"\1[REDACTED]" if pattern.groups else "[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True


def configure_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(data_dir / "neomath.log", encoding="utf-8")
    handler.addFilter(SecretFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
