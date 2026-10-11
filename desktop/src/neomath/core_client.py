from __future__ import annotations

from typing import Any, cast

import neomath_core


def _result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("C++ MathCore returned a non-object response")
    return cast(dict[str, Any], value)


class NeoMathCoreClient:
    """The only Python gateway to the coarse-grained C++ MathCore API."""

    def parse_document(self, source: str) -> dict[str, Any]:
        return _result(neomath_core.parse_document(source))

    def analyze_document(self, document: dict[str, Any]) -> dict[str, Any]:
        return _result(neomath_core.analyze_document(document))

    def run_trace(self, document: dict[str, Any]) -> dict[str, Any]:
        return _result(neomath_core.run_trace(document))

    def replay(self, document: dict[str, Any], changed_step: int) -> dict[str, Any]:
        return _result(neomath_core.replay(document, changed_step))

    def get_completions(self, document: dict[str, Any], step: int) -> dict[str, Any]:
        return _result(neomath_core.get_completions(document, step))

    def execute_transformation(
        self,
        document: dict[str, Any],
        step: int,
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        return _result(neomath_core.execute_transformation(document, step, intent))

    def evaluate_probe(
        self,
        document: dict[str, Any],
        probe: dict[str, Any],
    ) -> dict[str, Any]:
        return _result(neomath_core.evaluate_probe(document, probe))

    def get_capabilities(self) -> dict[str, Any]:
        return _result(neomath_core.get_capabilities())

    # Compatibility aliases matching the bridge design document.
    parseDocument = parse_document
    analyzeDocument = analyze_document
    runTrace = run_trace
    getCompletions = get_completions
    executeTransformation = execute_transformation
