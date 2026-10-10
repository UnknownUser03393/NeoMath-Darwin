from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from neomath.ai.fallback import explain_diagnostic
from neomath.ai.schemas import validate_intent
from neomath.config import AppConfig

LOGGER = logging.getLogger(__name__)


class QwenClient:
    """Qwen may phrase or classify; C++ remains the mathematical authority."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @property
    def available(self) -> bool:
        return bool(self.config.qwen_api_key)

    def explain(self, trace: dict[str, Any]) -> dict[str, Any]:
        fallback = explain_diagnostic(trace)
        if not self.available:
            return {"ok": True, "text": fallback, "source": "local", "model": None}
        system = (
            "你是中学数学学习助手。只改写输入中的已验证诊断，不得新增解、改变定义域或"
            "声称未给出的数学结论。用不超过120字中文解释，并引用给定Probe。"
        )
        user = json.dumps(trace.get("result", trace), ensure_ascii=False)
        try:
            text = self._chat(system, user)
            return {
                "ok": True,
                "text": text,
                "source": "qwen",
                "model": self.config.qwen_model,
            }
        except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
            LOGGER.warning("Qwen explanation unavailable: %s", error)
            return {
                "ok": True,
                "text": fallback,
                "source": "local_fallback",
                "model": self.config.qwen_model,
            }

    def compile_intent(self, command: str) -> dict[str, Any]:
        if not self.available:
            lowered = command.strip().lower()
            local_rules = (
                (("因式", "factor"), "factor"),
                (("展开", "expand"), "expand"),
                (("移项", "move"), "move_terms"),
                (("除以", "divide"), "divide"),
                (("乘以", "multiply"), "multiply"),
                (("平方", "square"), "square_both_sides"),
                (("求解", "solve"), "solve"),
                (("验证", "verify"), "verify"),
            )
            local = next(
                (
                    intent
                    for keywords, intent in local_rules
                    if any(keyword in command or keyword in lowered for keyword in keywords)
                ),
                None,
            )
            if local is None:
                raise ValueError("离线命令无法安全映射到受支持的数学操作")
            arguments: dict[str, str] = {}
            if local in {"divide", "multiply"}:
                match = re.search(
                    r"(?:除以|乘以|divide(?:\s+by)?|multiply(?:\s+by)?)\s*(.+)$",
                    lowered,
                )
                if match:
                    arguments["expression"] = match.group(1).strip(" 。.!！")
            return validate_intent({"intent": local, "confidence": 0.7, "arguments": arguments})
        response = self._chat(
            "只输出JSON对象，字段为intent、target、confidence、arguments。"
            "intent只能是factor、expand、move_terms、divide、multiply、"
            "square_both_sides、solve、verify。除法或乘法的式子放在"
            "arguments.expression。不得输出数学结论。",
            command,
        )
        start = response.find("{")
        end = response.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Qwen did not return JSON")
        return validate_intent(json.loads(response[start : end + 1]))

    def _chat(self, system: str, user: str) -> str:
        payload = json.dumps(
            {
                "model": self.config.qwen_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.dashscope_base_url}/chat/completions",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.qwen_api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"]).strip()
