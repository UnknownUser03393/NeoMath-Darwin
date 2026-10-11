from __future__ import annotations

from typing import Any

ALLOWED_INTENTS = {
    "factor",
    "expand",
    "move_terms",
    "divide",
    "multiply",
    "square_both_sides",
    "solve",
    "verify",
}


def validate_intent(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("AI response must be a JSON object")
    intent = payload.get("intent")
    if intent not in ALLOWED_INTENTS:
        raise ValueError("AI intent is not on the allowlist")
    confidence = payload.get("confidence", 0)
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("AI confidence must be between 0 and 1")
    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("AI arguments must be an object")
    return {
        "intent": intent,
        "target": "current_expression",
        "confidence": float(confidence),
        "arguments": arguments,
    }
