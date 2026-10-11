from __future__ import annotations

import logging
import re
import sys
from pathlib import Path


class SecretFilter(logging.Filter):
    _patterns = (
        re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
        re.compile(r"(OPENAI_API_KEY\s*[=:]\s*)\S+", re.IGNORECASE),
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
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    # Persistent audit log (kept filtered so secrets never hit disk).
    file_handler = logging.FileHandler(data_dir / "neomath.log", encoding="utf-8")
    file_handler.addFilter(SecretFilter())
    file_handler.setFormatter(formatter)
    # Mirror errors (including bridge tracebacks) to stderr so a server run in
    # a terminal surfaces failures instead of burying them in the log file.
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.addFilter(SecretFilter())
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(logging.ERROR)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stderr_handler)
